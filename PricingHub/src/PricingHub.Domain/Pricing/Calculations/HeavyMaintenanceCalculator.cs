using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Coût HM mensuel = coût HM/km de la série × km annuel ÷ 12 × coefficient
/// de tranche ; catalogue = max(coût × (1 + marge HM), plancher BP) — le
/// prix ne descend jamais sous le Budget Plan (section 6.1, 12.3). Porté
/// depuis le bloc Heavy maintenance de <c>engine.calculer_offre</c>
/// ("atelier" dans la terminologie Excel d'Akiem).
/// </summary>
public static class HeavyMaintenanceCalculator
{
    public static PricedLine Calculate(
        Series series, Mileage annualMileage, MileageBracket mileageBracket, BudgetPlanEntry budgetPlan, Percentage margin)
    {
        var currency = budgetPlan.HeavyMaintenanceFloor.Currency;
        var monthlyCost = Money.Of(
            series.HeavyMaintenanceCostPerKilometer * annualMileage.Kilometers / 12m * mileageBracket.HeavyMaintenanceCoefficient,
            currency);

        var catalogPrice = (monthlyCost + monthlyCost * margin).Max(budgetPlan.HeavyMaintenanceFloor);
        return new PricedLine(PriceLine.HeavyMaintenance, monthlyCost, catalogPrice, budgetPlan.HeavyMaintenanceFloor);
    }
}
