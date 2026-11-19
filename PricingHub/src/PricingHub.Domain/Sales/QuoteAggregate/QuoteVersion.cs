using PricingHub.Domain.Common;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>
/// Un instantané figé d'une offre : la configuration (briques incluses,
/// prix négociés, affectation de flotte) et, une fois calculée, le
/// résultat complet du chiffrage. Entité enfant de <see cref="Quote"/> —
/// jamais adressée seule, toujours à travers l'agrégat.
///
/// Immuable par construction une fois décidée : <see cref="Quote"/> n'édite
/// jamais une version Submitted/Approved/Rejected en place — toute
/// modification ouvre une nouvelle version (copiée depuis la précédente),
/// ce qui implémente directement M4-04 (« une approbation devient caduque
/// dès que le KAM modifie quoi que ce soit ») : le numéro de version
/// change, l'ancienne approbation reste valable pour l'ancien numéro,
/// périmée pour le nouveau.
/// </summary>
public sealed class QuoteVersion : Entity<QuoteVersionNumber>
{
    public QuoteStatus Status { get; private set; }

    private readonly HashSet<PriceLine> _includedLines;
    private readonly Dictionary<PriceLine, Money> _negotiatedPrices = new();
    public IReadOnlySet<PriceLine> IncludedLines => _includedLines;
    public IReadOnlyDictionary<PriceLine, Money> NegotiatedPrices => _negotiatedPrices;

    public string? LocomotiveNumber { get; private set; }
    public decimal AgeAtStartYears { get; private set; }
    public Mileage CumulativeMileageAtStart { get; private set; }
    public bool HeavyMaintenance8Done { get; private set; }
    public bool HeavyMaintenance16Done { get; private set; }
    public bool HasFleetAssignment { get; private set; }

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

    public DateTimeOffset CreatedAt { get; }
    public DateTimeOffset? DecidedAt { get; private set; }
    public string? DecidedBy { get; private set; }
    public string? DecisionComment { get; private set; }

#pragma warning disable CS8618
    private QuoteVersion()
    {
    }
#pragma warning restore CS8618

    /// <summary>Première version d'une offre, à la création.</summary>
    internal QuoteVersion(QuoteVersionNumber number, IEnumerable<PriceLine> includedLines) : base(number)
    {
        _includedLines = new HashSet<PriceLine>(includedLines);
        Status = QuoteStatus.Draft;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    /// <summary>Nouvelle version ouverte à partir de la précédente (même
    /// briques incluses, prix négociés et affectation de flotte ; le
    /// résultat calculé n'est PAS recopié — il faut recalculer).</summary>
    internal QuoteVersion(QuoteVersionNumber number, QuoteVersion previous) : base(number)
    {
        _includedLines = new HashSet<PriceLine>(previous._includedLines);
        foreach (var (line, price) in previous._negotiatedPrices)
        {
            _negotiatedPrices[line] = price;
        }

        LocomotiveNumber = previous.LocomotiveNumber;
        AgeAtStartYears = previous.AgeAtStartYears;
        CumulativeMileageAtStart = previous.CumulativeMileageAtStart;
        HeavyMaintenance8Done = previous.HeavyMaintenance8Done;
        HeavyMaintenance16Done = previous.HeavyMaintenance16Done;
        HasFleetAssignment = previous.HasFleetAssignment;
        Status = QuoteStatus.Draft;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    internal void AssignLocomotive(
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

    internal void AssignManualFleetData(
        decimal ageAtStartYears, Mileage cumulativeMileageAtStart, bool heavyMaintenance8Done, bool heavyMaintenance16Done)
    {
        LocomotiveNumber = null;
        AgeAtStartYears = ageAtStartYears;
        CumulativeMileageAtStart = cumulativeMileageAtStart;
        HeavyMaintenance8Done = heavyMaintenance8Done;
        HeavyMaintenance16Done = heavyMaintenance16Done;
        HasFleetAssignment = true;
    }

    internal void NegotiatePrice(PriceLine line, Money price) => _negotiatedPrices[line] = price;

    internal Result ApplyCalculation(
        PriceBookNumber priceBookNumber,
        PricingParameters parameters,
        Money residualValueAtStart,
        Money residualValueAtEnd,
        decimal additionalMileagePrice,
        IReadOnlyDictionary<PriceLine, PricedLine> pricedLines,
        bool preSendControlsFailed,
        Duration contractDuration,
        int quantity)
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
        MonthlyValueLoss = TotalValueLoss.Value * (1m / contractDuration.Months);
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
        TotalRetainedMonthly = totalRetained * quantity;
        TotalRetainedContract = totalRetained * quantity * contractDuration.Months;
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
        return Result.Success();
    }

    internal Result Submit()
    {
        if (Status != QuoteStatus.Calculated)
        {
            return Result.Failure("Seule une offre calculée peut être soumise à validation.");
        }

        Status = QuoteStatus.Submitted;
        return Result.Success();
    }

    internal Result ApproveDecision(string approvedBy)
    {
        if (Status != QuoteStatus.Submitted)
        {
            return Result.Failure("Seule une offre soumise peut être approuvée.");
        }

        Status = QuoteStatus.Approved;
        DecidedBy = approvedBy;
        DecidedAt = DateTimeOffset.UtcNow;
        return Result.Success();
    }

    internal Result RejectDecision(string reason)
    {
        if (Status != QuoteStatus.Submitted)
        {
            return Result.Failure("Seule une offre soumise peut être rejetée.");
        }

        Status = QuoteStatus.Rejected;
        DecisionComment = reason;
        DecidedAt = DateTimeOffset.UtcNow;
        return Result.Success();
    }
}
