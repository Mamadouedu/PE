using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Prix du km supplémentaire (au-delà du km annuel contractuel) — section
/// 6.1 : (coût HM/km × coefficient HM + coût OM variable/km × coefficient
/// OM) × (1 + majoration km supplémentaire). Un taux €/km, pas un
/// <see cref="Money"/> : il reste à multiplier par le km réellement
/// dépassé, une donnée de facturation que <see cref="Money"/>, exprimé en
/// devise, ne porterait pas correctement en tant que taux unitaire. Porté
/// depuis le bloc "Km supplémentaire" de <c>engine.calculer_offre</c>.
/// </summary>
public static class AdditionalMileageCalculator
{
    public static decimal CalculatePerKilometerPrice(Series series, MileageBracket mileageBracket, Percentage surcharge)
    {
        var baseRate = series.HeavyMaintenanceCostPerKilometer * mileageBracket.HeavyMaintenanceCoefficient
            + series.OperatingMaintenanceVariableCostPerKilometer * mileageBracket.OperatingMaintenanceCoefficient;
        return baseRate * (1m + surcharge.Value);
    }
}
