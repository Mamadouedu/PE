using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Common;
using PricingHub.Domain.Pricing;
using PricingHub.Domain.Pricing.CampaignAggregate;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.Domain.Sales.CustomerAggregate;
using PricingHub.Domain.Sales.OpportunityAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>
/// Une offre à chiffrer puis à faire approuver. Porte l'identité et la
/// configuration stable (client, modèle, km/durée/quantité, campagne), et
/// surtout l'historique complet de ses <see cref="QuoteVersion"/> : chaque
/// calcul figé est un instantané immuable, jamais écrasé.
///
/// Toute édition (négociation, affectation de flotte) après qu'une version
/// a été calculée ouvre automatiquement une nouvelle version, copiée depuis
/// la précédente — c'est ce qui implémente M4-04 (« une approbation devient
/// caduque dès que le KAM modifie quoi que ce soit ») : l'
/// <c>ApprovalRequest</c> référence un numéro de version précis, qui ne
/// change jamais de contenu sous ses pieds.
///
/// Les propriétés telles que <see cref="Status"/>, <see cref="Lines"/> ou
/// <see cref="ValidationLevel"/> sont des façades qui délèguent à
/// <see cref="CurrentVersion"/>, pour que lire l'état courant d'une offre
/// reste aussi simple qu'avant l'introduction du versionnement.
/// </summary>
public sealed class Quote : AggregateRoot<QuoteId>
{
    public CustomerCode CustomerCode { get; private set; }
    public ModelCode ModelCode { get; private set; }
    public OpportunityId? OpportunityId { get; private set; }
    public CampaignCode? CampaignCode { get; private set; }

    /// <summary>Vrai si l'offre est rattachée à une campagne commerciale
    /// (AMS, Renewal...) — contrôle C1, section 6.4.</summary>
    public bool IsCampaign => CampaignCode is not null;

    public Mileage AnnualMileage { get; private set; }
    public Duration ContractDuration { get; private set; }
    public int Quantity { get; private set; }
    public DateOnly StartDate { get; private set; }

    private readonly List<QuoteVersion> _versions = new();
    public IReadOnlyList<QuoteVersion> Versions => _versions.AsReadOnly();
    public QuoteVersion CurrentVersion => _versions[^1];
    public QuoteVersionNumber CurrentVersionNumber => CurrentVersion.Id;

    // ---- Façade : lecture de l'état courant, déléguée à CurrentVersion ----
    public QuoteStatus Status => CurrentVersion.Status;
    public IReadOnlySet<PriceLine> IncludedLines => CurrentVersion.IncludedLines;
    public IReadOnlyDictionary<PriceLine, Money> NegotiatedPrices => CurrentVersion.NegotiatedPrices;
    public string? LocomotiveNumber => CurrentVersion.LocomotiveNumber;
    public decimal AgeAtStartYears => CurrentVersion.AgeAtStartYears;
    public Mileage CumulativeMileageAtStart => CurrentVersion.CumulativeMileageAtStart;
    public bool HeavyMaintenance8Done => CurrentVersion.HeavyMaintenance8Done;
    public bool HeavyMaintenance16Done => CurrentVersion.HeavyMaintenance16Done;
    public bool HasFleetAssignment => CurrentVersion.HasFleetAssignment;
    public IReadOnlyList<QuoteLine> Lines => CurrentVersion.Lines;
    public PriceBookNumber? PriceBookNumber => CurrentVersion.PriceBookNumber;
    public Money? ResidualValueAtStart => CurrentVersion.ResidualValueAtStart;
    public Money? ResidualValueAtEnd => CurrentVersion.ResidualValueAtEnd;
    public Money? TotalValueLoss => CurrentVersion.TotalValueLoss;
    public Money? MonthlyValueLoss => CurrentVersion.MonthlyValueLoss;
    public decimal? AdditionalMileagePrice => CurrentVersion.AdditionalMileagePrice;
    public Money? TotalCatalogPerUnitMonthly => CurrentVersion.TotalCatalogPerUnitMonthly;
    public Money? TotalRetainedPerUnitMonthly => CurrentVersion.TotalRetainedPerUnitMonthly;
    public Money? TotalFloorPerUnitMonthly => CurrentVersion.TotalFloorPerUnitMonthly;
    public Money? TotalRetainedMonthly => CurrentVersion.TotalRetainedMonthly;
    public Money? TotalRetainedContract => CurrentVersion.TotalRetainedContract;
    public decimal? GlobalDiscount => CurrentVersion.GlobalDiscount;
    public Money? MonthlyReferenceCost => CurrentVersion.MonthlyReferenceCost;
    public int ValidationLevel => CurrentVersion.ValidationLevel;
    public IReadOnlyList<string> ValidationLevelReasons => CurrentVersion.ValidationLevelReasons;
    // ----

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
        IEnumerable<PriceLine> includedLines)
        : base(id)
    {
        CustomerCode = customerCode;
        ModelCode = modelCode;
        AnnualMileage = annualMileage;
        ContractDuration = contractDuration;
        Quantity = quantity;
        StartDate = startDate;
        _versions.Add(new QuoteVersion(QuoteVersionNumber.First, includedLines));
    }

    public static Result<Quote> CreateDraft(
        QuoteId id,
        CustomerCode customerCode,
        ModelCode modelCode,
        Mileage annualMileage,
        Duration contractDuration,
        int quantity,
        DateOnly startDate,
        CampaignCode? campaignCode = null,
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

        var quote = new Quote(id, customerCode, modelCode, annualMileage, contractDuration, quantity, startDate, lines)
        {
            CampaignCode = campaignCode,
        };

        return Result.Success(quote);
    }

    /// <summary>Si la version courante est encore en brouillon, elle reste
    /// éditable en place. Sinon (déjà calculée, soumise, décidée), une
    /// nouvelle version est ouverte — copiée depuis la précédente — avant
    /// toute édition : c'est le mécanisme qui implémente M4-04.</summary>
    private QuoteVersion EnsureEditableVersion()
    {
        if (CurrentVersion.Status == QuoteStatus.Draft)
        {
            return CurrentVersion;
        }

        var next = new QuoteVersion(CurrentVersion.Id.Next(), CurrentVersion);
        _versions.Add(next);
        return next;
    }

    public void AssignLocomotive(
        string locomotiveNumber, decimal ageAtStartYears, Mileage cumulativeMileageAtStart,
        bool heavyMaintenance8Done, bool heavyMaintenance16Done) =>
        EnsureEditableVersion().AssignLocomotive(
            locomotiveNumber, ageAtStartYears, cumulativeMileageAtStart, heavyMaintenance8Done, heavyMaintenance16Done);

    /// <summary>Sans locomotive de flotte affectée : l'âge et le km cumulé
    /// sont saisis manuellement par le KAM.</summary>
    public void AssignManualFleetData(
        decimal ageAtStartYears, Mileage cumulativeMileageAtStart, bool heavyMaintenance8Done, bool heavyMaintenance16Done) =>
        EnsureEditableVersion().AssignManualFleetData(
            ageAtStartYears, cumulativeMileageAtStart, heavyMaintenance8Done, heavyMaintenance16Done);

    public void NegotiatePrice(PriceLine line, Money price) => EnsureEditableVersion().NegotiatePrice(line, price);

    public void LinkToOpportunity(OpportunityId opportunityId) => OpportunityId = opportunityId;

    public void LinkToCampaign(CampaignCode campaignCode) => CampaignCode = campaignCode;

    /// <summary>
    /// Combine les briques calculées avec les choix du KAM (briques
    /// incluses, prix négociés) sur la version courante, calcule les
    /// totaux et en déduit le niveau de validation.
    /// <paramref name="preSendControlsFailed"/> résume les contrôles C1 à
    /// C8 (section 6.4) : ils dépendent de Customer et de la flotte,
    /// évalués par un service applicatif, pas par l'agrégat lui-même.
    /// Refuse de recalculer une version déjà soumise ou décidée — il faut
    /// d'abord éditer l'offre (ce qui ouvre une nouvelle version).
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
        if (CurrentVersion.Status is QuoteStatus.Submitted or QuoteStatus.Approved or QuoteStatus.Rejected)
        {
            return Result.Failure(
                "Cette version a déjà été soumise ou décidée — modifiez l'offre pour ouvrir une nouvelle version avant de recalculer.");
        }

        var result = CurrentVersion.ApplyCalculation(
            priceBookNumber, parameters, residualValueAtStart, residualValueAtEnd, additionalMileagePrice, pricedLines,
            preSendControlsFailed, ContractDuration, Quantity);

        if (result.IsFailure)
        {
            return result;
        }

        Raise(new QuoteCalculated(Id, CurrentVersion.Id, CurrentVersion.ValidationLevel));
        return Result.Success();
    }

    public Result SubmitForApproval()
    {
        var result = CurrentVersion.Submit();
        if (result.IsFailure)
        {
            return result;
        }

        Raise(new QuoteSubmittedForApproval(Id, CurrentVersion.Id, CurrentVersion.ValidationLevel));
        return Result.Success();
    }

    public Result Approve(string approvedBy)
    {
        var result = CurrentVersion.ApproveDecision(approvedBy);
        if (result.IsFailure)
        {
            return result;
        }

        Raise(new QuoteApproved(Id, CurrentVersion.Id, approvedBy));
        return Result.Success();
    }

    public Result Reject(string reason)
    {
        var result = CurrentVersion.RejectDecision(reason);
        if (result.IsFailure)
        {
            return result;
        }

        Raise(new QuoteRejected(Id, CurrentVersion.Id, reason));
        return Result.Success();
    }
}
