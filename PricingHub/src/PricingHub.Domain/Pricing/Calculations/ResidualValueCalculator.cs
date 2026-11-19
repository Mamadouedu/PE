using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// VR(âge, km) — section 6.2 du cahier des charges. Appelée deux fois par
/// offre (début et fin de contrat) ; la différence divisée par la durée
/// donne la perte de valeur mensuelle, base du Dry lease et du coût de
/// référence (contrôle C7).
///
/// Porté terme à terme depuis <c>engine.calculer_valeur_residuelle</c> :
/// <c>usure + bonus − perte_km</c>, plafonné en dessous par le plancher
/// <c>VN × plancher_vr_taux</c>.
/// </summary>
public static class ResidualValueCalculator
{
    public static Money Calculate(
        Series series,
        PricingParameters parameters,
        decimal ageYears,
        Mileage cumulativeMileage,
        bool heavyMaintenance8YearDone,
        bool heavyMaintenance16YearDone)
    {
        var newValue = series.NewValue;
        var floor = newValue * parameters.ResidualValueFloorRate;

        var agingRatio = Math.Min(1m, ageYears / series.ServiceLifeYears);
        var wearRatio = 1m - (1m - series.EndOfLifeResidualRate.Value) * agingRatio;
        var wear = newValue * wearRatio;

        var bonus = Money.Zero(newValue.Currency);
        if (heavyMaintenance8YearDone)
        {
            bonus += newValue * parameters.ResidualValueBonusHm8;
        }

        if (heavyMaintenance16YearDone)
        {
            bonus += newValue * parameters.ResidualValueBonusHm16;
        }

        var theoreticalMileage = series.ReferenceAnnualMileage.Kilometers * ageYears;
        var excessMileage = Math.Max(0m, cumulativeMileage.Kilometers - theoreticalMileage);
        var mileagePenalty = Money.Of(parameters.ValueLossPerKilometerOutOfReference * excessMileage, newValue.Currency);

        var baseValue = wear + bonus - mileagePenalty;
        return floor.Max(baseValue);
    }
}
