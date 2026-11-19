using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Common;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>
/// Une version du référentiel pricing : tranches de km, grille Dry lease,
/// Budget Plan et paramètres globaux — tout ce dont les calculateurs ont
/// besoin pour chiffrer une offre sur un modèle donné. Équivalent du
/// modèle Python <c>VersionReferentiel</c> (hors produits, séries, modèles,
/// clients et flotte, qui vivent dans leurs propres contextes — Catalog et
/// Sales).
///
/// Racine d'agrégat : les tranches, la grille et le BP ne se modifient
/// qu'à travers elle, jamais directement.
/// </summary>
public sealed class PriceBook : AggregateRoot<PriceBookNumber>
{
    public PriceBookStatus Status { get; private set; } = PriceBookStatus.Draft;
    public DateTimeOffset CreatedAt { get; private set; }
    public DateTimeOffset? PublishedAt { get; private set; }
    public string? PublishedBy { get; private set; }
    public PricingParameters Parameters { get; private set; }

    private readonly List<MileageBracket> _mileageBrackets = new();
    private readonly List<DryLeaseGridEntry> _dryLeaseGrid = new();
    private readonly List<BudgetPlanEntry> _budgetPlan = new();

    public IReadOnlyList<MileageBracket> MileageBrackets => _mileageBrackets.AsReadOnly();
    public IReadOnlyList<DryLeaseGridEntry> DryLeaseGrid => _dryLeaseGrid.AsReadOnly();
    public IReadOnlyList<BudgetPlanEntry> BudgetPlan => _budgetPlan.AsReadOnly();

#pragma warning disable CS8618
    private PriceBook()
    {
    }
#pragma warning restore CS8618

    private PriceBook(PriceBookNumber number, PricingParameters parameters) : base(number)
    {
        Parameters = parameters;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    public static PriceBook CreateDraft(PriceBookNumber number, PricingParameters parameters) =>
        new(number, parameters);

    /// <summary>Repart d'un brouillon identique à cette version (même
    /// tranches, grille, BP, paramètres) — équivalent de
    /// <c>copier_brouillon</c>, utilisé pour ouvrir une nouvelle version à
    /// partir de la version publiée.</summary>
    public PriceBook CopyAsDraft(PriceBookNumber newNumber)
    {
        var copy = new PriceBook(newNumber, Parameters);
        copy._mileageBrackets.AddRange(_mileageBrackets);
        copy._dryLeaseGrid.AddRange(_dryLeaseGrid);
        copy._budgetPlan.AddRange(_budgetPlan);
        return copy;
    }

    public void AddMileageBracket(MileageBracket bracket) => _mileageBrackets.Add(bracket);

    public void AddDryLeaseGridEntry(DryLeaseGridEntry entry) => _dryLeaseGrid.Add(entry);

    public void AddBudgetPlanEntry(BudgetPlanEntry entry) => _budgetPlan.Add(entry);

    public void ReplaceParameters(PricingParameters parameters) => Parameters = parameters;

    public Result<MileageBracket> MileageBracketFor(decimal annualMileage)
    {
        var bracket = _mileageBrackets.FirstOrDefault(b => b.Contains(annualMileage));
        return bracket is not null
            ? Result.Success(bracket)
            : Result.Failure<MileageBracket>($"Aucune tranche de km ne couvre {annualMileage} km/an.");
    }

    public Result<DryLeaseGridEntry> DryLeaseGridEntryFor(ModelCode modelCode, int durationMonths)
    {
        var entry = _dryLeaseGrid.FirstOrDefault(e => e.ModelCode == modelCode && e.DurationBracket.Contains(durationMonths));
        return entry is not null
            ? Result.Success(entry)
            : Result.Failure<DryLeaseGridEntry>($"Aucune grille Dry lease pour {modelCode} à {durationMonths} mois.");
    }

    public Result<BudgetPlanEntry> BudgetPlanEntryFor(ModelCode modelCode, decimal annualMileage)
    {
        var entry = _budgetPlan.FirstOrDefault(e => e.ModelCode == modelCode && e.MileageBracket.Contains(annualMileage));
        return entry is not null
            ? Result.Success(entry)
            : Result.Failure<BudgetPlanEntry>($"Aucun BP pour le modèle {modelCode} à {annualMileage} km/an.");
    }

    /// <summary>Publication — bloquée si une anomalie bloquante du contrôle
    /// qualité subsiste (M1-04). Le contrôle qualité lui-même (références
    /// croisées avec Catalog/Sales, chevauchements de tranches, etc.) est un
    /// service applicatif, pas une méthode d'agrégat : il traverse plusieurs
    /// bounded contexts que <see cref="PriceBook"/> ne connaît pas.</summary>
    public void Publish(string publishedBy)
    {
        Status = PriceBookStatus.Published;
        PublishedAt = DateTimeOffset.UtcNow;
        PublishedBy = publishedBy;
    }

    public void Archive() => Status = PriceBookStatus.Archived;
}
