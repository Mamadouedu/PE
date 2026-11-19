using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Loyer Dry lease catalogue pour un modèle × tranche de durée —
/// avant application du coefficient de tranche de km. Équivalent du modèle
/// Python <c>GrilleDryLeaseEntry</c>, porté au niveau Model (le référentiel
/// catalogue le plus fin) plutôt que Series.</summary>
public sealed class DryLeaseGridEntry
{
    public ModelCode ModelCode { get; }
    public DurationBracket DurationBracket { get; }
    public Money MonthlyRent { get; }

    private DryLeaseGridEntry(ModelCode modelCode, DurationBracket durationBracket, Money monthlyRent)
    {
        ModelCode = modelCode;
        DurationBracket = durationBracket;
        MonthlyRent = monthlyRent;
    }

    public static Result<DryLeaseGridEntry> Create(ModelCode modelCode, DurationBracket durationBracket, Money monthlyRent)
    {
        if (monthlyRent.Amount <= 0m)
        {
            return Result.Failure<DryLeaseGridEntry>("Le loyer catalogue doit être strictement positif.");
        }

        return Result.Success(new DryLeaseGridEntry(modelCode, durationBracket, monthlyRent));
    }
}
