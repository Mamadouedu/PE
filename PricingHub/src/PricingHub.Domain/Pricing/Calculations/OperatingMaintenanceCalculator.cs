using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>
/// Coût OM mensuel = (part fixe + part variable × km annuel) ÷ 12 ×
/// coefficient de tranche ; catalogue = max(coût × (1 + marge OM), plancher
/// BP) — section 6.1, 12.3. Porté depuis le bloc Operation maintenance de
/// <c>engine.calculer_offre</c>.
/// </summary>
public static class OperatingMaintenanceCalculator
{
    public static PricedLine Calculate(
        Series series, Mileage annualMileage, MileageBracket mileageBracket, BudgetPlanEntry budgetPlan, Percentage margin)
    {
        var currency = series.OperatingMaintenanceFixedCost.Currency;
        var variableCost = Money.Of(series.OperatingMaintenanceVariableCostPerKilometer * annualMileage.Kilometers, currency);
        var monthlyCost = (series.OperatingMaintenanceFixedCost + variableCost)
            * (1m / 12m)
            * mileageBracket.OperatingMaintenanceCoefficient;

        var catalogPrice = (monthlyCost + monthlyCost * margin).Max(budgetPlan.OperatingMaintenanceFloor);
        return new PricedLine(PriceLine.OperatingMaintenance, monthlyCost, catalogPrice, budgetPlan.OperatingMaintenanceFloor);
    }
}
