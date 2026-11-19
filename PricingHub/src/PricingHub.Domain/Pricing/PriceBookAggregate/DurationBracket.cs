using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Tranche de durée (en mois) utilisée par la grille Dry lease.
/// Équivalent du modèle Python <c>TrancheDuree</c>.</summary>
public sealed class DurationBracket
{
    public int MinMonths { get; }
    public int? MaxMonths { get; }

    private DurationBracket(int minMonths, int? maxMonths)
    {
        MinMonths = minMonths;
        MaxMonths = maxMonths;
    }

    public static Result<DurationBracket> Create(int minMonths, int? maxMonths)
    {
        if (minMonths < 0)
        {
            return Result.Failure<DurationBracket>("La durée minimale ne peut pas être négative.");
        }

        if (maxMonths is { } max && max < minMonths)
        {
            return Result.Failure<DurationBracket>("La durée maximale ne peut pas être inférieure à la durée minimale.");
        }

        return Result.Success(new DurationBracket(minMonths, maxMonths));
    }

    public bool Contains(int months) => months >= MinMonths && (MaxMonths is null || months <= MaxMonths);
}
