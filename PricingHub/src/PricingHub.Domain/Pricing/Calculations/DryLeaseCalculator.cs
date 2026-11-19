using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Prix catalogue Dry lease = loyer de grille × coefficient de la tranche
/// de km ; plancher = catalogue × (1 − remise maximale KAM) — section 6.1
/// et délégation de remise (12.1). Porté depuis le bloc Dry lease de
/// <c>engine.calculer_offre</c>.
/// </summary>
public static class DryLeaseCalculator
{
    public static PricedLine Calculate(DryLeaseGridEntry gridEntry, MileageBracket mileageBracket, Percentage maximumDiscount)
    {
        var catalogPrice = gridEntry.MonthlyRent * mileageBracket.DryLeaseCoefficient;
        var floor = catalogPrice * maximumDiscount.Complement();
        return new PricedLine(PriceLine.DryLease, Cost: gridEntry.MonthlyRent, CatalogPrice: catalogPrice, Floor: floor);
    }
}
