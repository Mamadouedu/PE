using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Loyer Dry lease catalogue pour une série × tranche de durée —
/// avant application du coefficient de tranche de km. Équivalent du modèle
/// Python <c>GrilleDryLeaseEntry</c>.</summary>
public sealed class DryLeaseGridEntry
{
    public SeriesCode SeriesCode { get; }
    public DurationBracket DurationBracket { get; }
    public Money MonthlyRent { get; }

    private DryLeaseGridEntry(SeriesCode seriesCode, DurationBracket durationBracket, Money monthlyRent)
    {
        SeriesCode = seriesCode;
        DurationBracket = durationBracket;
        MonthlyRent = monthlyRent;
    }

    public static Result<DryLeaseGridEntry> Create(SeriesCode seriesCode, DurationBracket durationBracket, Money monthlyRent)
    {
        if (monthlyRent.Amount <= 0m)
        {
            return Result.Failure<DryLeaseGridEntry>("Le loyer catalogue doit être strictement positif.");
        }

        return Result.Success(new DryLeaseGridEntry(seriesCode, durationBracket, monthlyRent));
    }
}
