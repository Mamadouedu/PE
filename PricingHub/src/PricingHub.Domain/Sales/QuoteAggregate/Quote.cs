using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Common;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>
/// Une offre à chiffrer puis à faire approuver. Porte à la fois l'entrée
/// (équivalent du modèle Python <c>ConfigurationOffre</c>) et la sortie du
/// calcul (équivalent de <c>DetailOffre</c>), plus un cycle de vie —
/// Draft → Calculated → Submitted → Approved/Rejected — que le prototype
/// Python n'avait pas besoin de modéliser puisqu'il recalculait à la volée
/// sans conserver d'état entre deux appels.
///
/// <see cref="ApplyCalculation"/> ne recalcule rien lui-même : il combine
/// les <see cref="PricedLine"/> produits par <c>Pricing.Calculations</c>
/// avec les choix du KAM (briques incluses, prix négociés), exactement
/// comme la seconde moitié de <c>engine.calculer_offre</c> à partir de
/// <c>par_brique</c>.
/// </summary>
public sealed class Quote : AggregateRoot<QuoteId>
{
    public CustomerCode CustomerCode { get; private set; }
    public ModelCode ModelCode { get; private set; }
    public OpportunityId? OpportunityId { get; private set; }
    public QuoteStatus Status { get; private set; }

    public Mileage AnnualMileage { get; private set; }
    public Duration ContractDuration { get; private set; }
    public int Quantity { get; private set; }
    public DateOnly StartDate { get; private set; }
    public bool IsCampaign { get; private set; }

    /// <summary>Numéro de la locomotive de flotte affectée, ou <c>null</c>
    /// si l'âge et le kilométrage sont saisis manuellement (équivalent du
    /// cas <c>locomotive_numero is None</c> de <c>ConfigurationOffre</c>).</summary>
    public string? LocomotiveNumber { get; private set; }
    public decimal AgeAtStartYears { get; private set; }
    public Mileage CumulativeMileageAtStart { get; private set; }
    public bool HeavyMaintenance8Done { get; private set; }
    public bool HeavyMaintenance16Done { get; private set; }
    public bool HasFleetAssignment { get; private set; }

    private readonly HashSet<PriceLine> _includedLines;
    private readonly Dictionary<PriceLine, Money> _negotiatedPrices = new();

    public IReadOnlySet<PriceLine> IncludedLines => _includedLines;
    public IReadOnlyDictionary<PriceLine, Money> NegotiatedPrices => _negotiatedPrices;

    private readonly List<QuoteLine> _lines = new();
    public IReadOnlyList<QuoteLine> Lines => _lines.AsReadOnly();

    public PriceBookNumber? PriceBookNumber { get; private set; }
    public Money? ResidualValueAtStart { get; private set; }
    public Money? ResidualValueAtEnd { get; private set; }
    public Money? TotalValueLoss { get; private set; }
    public Money? MonthlyValueLoss { get; private set; }
    public decimal? AdditionalMileagePrice { get; private set; }
    public Money? TotalCatalogPerUnitMonthly { get; private set; }
    public Money? TotalRetainedPerUnitMonthly { get; private set; }
    public Money? TotalFloorPerUnitMonthly { get; private set; }
    public Money? TotalRetainedMonthly { get; private set; }
    public Money? TotalRetainedContract { get; private set; }
    public decimal? GlobalDiscount { get; private set; }
    public Money? MonthlyReferenceCost { get; private set; }
    public int ValidationLevel { get; private set; }

    private readonly List<string> _validationLevelReasons = new();
    public IReadOnlyList<string> ValidationLevelReasons => _validationLevelReasons.AsReadOnly();

#pragma warning disable CS8618
    private Quote()
    {
    }
#pragma warning restore CS8618

    private Quote(
        QuoteId id,
        CustomerCode customerCode,
        ModelCode modelCode,
        Mileage annualMileage,
        Duration contractDuration,
        int quantity,
        DateOnly startDate,
        bool isCampaign,
        IEnumerable<PriceLine> includedLines)
        : base(id)
    {
        CustomerCode = customerCode;
        ModelCode = modelCode;
        AnnualMileage = annualMileage;
        ContractDuration = contractDuration;
        Quantity = quantity;
        StartDate = startDate;
        IsCampaign = isCampaign;
        _includedLines = new HashSet<PriceLine>(includedLines);
        Status = QuoteStatus.Draft;
    }

    public static Result<Quote> CreateDraft(
        QuoteId id,
        CustomerCode customerCode,
        ModelCode modelCode,
        Mileage annualMileage,
        Duration contractDuration,
        int quantity,
        DateOnly startDate,
        bool isCampaign,
        IEnumerable<PriceLine>? includedLines = null)
    {
        if (quantity <= 0)
        {
            return Result.Failure<Quote>("La quantité doit être strictement positive.");
        }

        var lines = includedLines?.ToList() ?? new List<PriceLine>
        {
            PriceLine.DryLease, PriceLine.HeavyMaintenance, PriceLine.OperatingMaintenance, PriceLine.Insurance,
        };

        return Result.Success(new Quote(
            id, customerCode, modelCode, annualMileage, contractDuration, quantity, startDate, isCampaign, lines));
    }

    public void AssignLocomotive(
        string locomotiveNumber, decimal ageAtStartYears, Mileage cumulativeMileageAtStart,
        bool heavyMaintenance8Done, bool heavyMaintenance16Done)
    {
        LocomotiveNumber = locomotiveNumber;
        AgeAtStartYears = ageAtStartYears;
        CumulativeMileageAtStart = cumulativeMileageAtStart;
        HeavyMaintenance8Done = heavyMaintenance8Done;
        HeavyMaintenance16Done = heavyMaintenance16Done;
        HasFleetAssignment = true;
    }

    /// <summary>Sans locomotive de flotte affectée : l'âge et le km cumulé
    /// sont saisis manuellement par le KAM.</summary>
    public void AssignManualFleetData(
        decimal ageAtStartYears, Mileage cumulativeMileageAtStart, bool heavyMaintenance8Done, bool heavyMaintenance16Done)
    {
        LocomotiveNumber = null;
        AgeAtStartYears = ageAtStartYears;
        CumulativeMileageAtStart = cumulativeMileageAtStart;
        HeavyMaintenance8Done = heavyMaintenance8Done;
        HeavyMaintenance16Done = heavyMaintenance16Done;
        HasFleetAssignment = true;
    }

    public void NegotiatePrice(PriceLine line, Money price) => _negotiatedPrices[line] = price;

    public void LinkToOpportunity(OpportunityId opportunityId) => OpportunityId = opportunityId;

    /// <summary>
    /// Combine les briques calculées avec les choix du KAM (briques
    /// incluses, prix négociés), calcule les totaux et en déduit le niveau
    /// de validation. <paramref name="preSendControlsFailed"/> résume les
    /// contrôles C1 à C8 (section 6.4) : ils dépendent de Customer et de la
    /// flotte, évalués par un service applicatif, pas par l'agrégat lui-même.
    /// </summary>
    public Result ApplyCalculation(
        PriceBookNumber priceBookNumber,
        PricingParameters parameters,
        Money residualValueAtStart,
        Money residualValueAtEnd,
        decimal additionalMileagePrice,
        IReadOnlyDictionary<PriceLine, PricedLine> pricedLines,
        bool preSendControlsFailed)
    {
        if (!HasFleetAssignment)
        {
            return Result.Failure(
                "Impossible de calculer une offre sans affectation de flotte (locomotive ou âge/km manuels).");
        }

        _lines.Clear();
        foreach (var line in new[] { PriceLine.DryLease, PriceLine.HeavyMaintenance, PriceLine.OperatingMaintenance, PriceLine.Insurance })
        {
            var priced = pricedLines[line];
            if (_includedLines.Contains(line))
            {
                Money? negotiatedPrice = _negotiatedPrices.TryGetValue(line, out var price) ? price : null;
                _lines.Add(QuoteLine.Included(priced, negotiatedPrice));
            }
            else
            {
                _lines.Add(QuoteLine.Excluded(priced));
            }
        }

        PriceBookNumber = priceBookNumber;
        ResidualValueAtStart = residualValueAtStart;
        ResidualValueAtEnd = residualValueAtEnd;
        TotalValueLoss = residualValueAtStart - residualValueAtEnd;
        MonthlyValueLoss = TotalValueLoss.Value * (1m / ContractDuration.Months);
        AdditionalMileagePrice = additionalMileagePrice;

        var currency = residualValueAtStart.Currency;
        var totalCatalog = Money.Zero(currency);
        var totalFloor = Money.Zero(currency);
        var totalRetained = Money.Zero(currency);
        foreach (var line in _lines)
        {
            totalRetained += line.RetainedPrice;
            if (line.Status != QuoteLineStatus.Excluded)
            {
                totalCatalog += line.CatalogPrice;
                totalFloor += line.Floor;
            }
        }

        TotalCatalogPerUnitMonthly = totalCatalog;
        TotalRetainedPerUnitMonthly = totalRetained;
        TotalFloorPerUnitMonthly = totalFloor;
        TotalRetainedMonthly = totalRetained * Quantity;
        TotalRetainedContract = totalRetained * Quantity * ContractDuration.Months;
        GlobalDiscount = totalCatalog.Amount > 0m ? 1m - totalRetained.Amount / totalCatalog.Amount : 0m;

        var heavyMaintenanceCost = pricedLines[PriceLine.HeavyMaintenance].Cost;
        var operatingMaintenanceCost = pricedLines[PriceLine.OperatingMaintenance].Cost;
        var insuranceCost = pricedLines[PriceLine.Insurance].Cost;
        MonthlyReferenceCost = MonthlyValueLoss.Value + heavyMaintenanceCost + operatingMaintenanceCost + insuranceCost;

        var anyLineBelowFloor = _lines.Any(l => l.Status == QuoteLineStatus.BelowFloor);
        var (level, reasons) = ValidationLevelCalculator.Calculate(
            GlobalDiscount.Value,
            parameters.KamDiscountThreshold,
            anyLineBelowFloor,
            preSendControlsFailed,
            TotalRetainedPerUnitMonthly.Value,
            MonthlyReferenceCost.Value);

        ValidationLevel = level;
        _validationLevelReasons.Clear();
        _validationLevelReasons.AddRange(reasons);

        Status = QuoteStatus.Calculated;
        Raise(new QuoteCalculated(Id, ValidationLevel));
        return Result.Success();
    }

    public Result SubmitForApproval()
    {
        if (Status != QuoteStatus.Calculated)
        {
            return Result.Failure("Seule une offre calculée peut être soumise à validation.");
        }

        Status = QuoteStatus.Submitted;
        Raise(new QuoteSubmittedForApproval(Id, ValidationLevel));
        return Result.Success();
    }

    public Result Approve(string approvedBy)
    {
        if (Status != QuoteStatus.Submitted)
        {
            return Result.Failure("Seule une offre soumise peut être approuvée.");
        }

        Status = QuoteStatus.Approved;
        Raise(new QuoteApproved(Id, approvedBy));
        return Result.Success();
    }

    public Result Reject(string reason)
    {
        if (Status != QuoteStatus.Submitted)
        {
            return Result.Failure("Seule une offre soumise peut être rejetée.");
        }

        Status = QuoteStatus.Rejected;
        Raise(new QuoteRejected(Id, reason));
        return Result.Success();
    }
}
