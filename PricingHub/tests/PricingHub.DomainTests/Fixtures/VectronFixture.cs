using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Fixtures;

/// <summary>
/// Jeu de données de référence VECTRON — porté terme à terme depuis
/// <c>tests/conftest.py</c> (Python) pour que les deux suites de tests
/// comparent exactement les mêmes chiffres (filet de sécurité du portage).
/// </summary>
public static class VectronFixture
{
    public static readonly Series Series = Series.Create(
        SeriesCode.Of("VECTRON"),
        "Vectron",
        newValue: Money.Eur(2_000_000m),
        serviceLifeYears: 30,
        endOfLifeResidualRate: Percentage.FromRatio(0.10m),
        referenceAnnualMileage: Mileage.FromKilometers(120_000m),
        heavyMaintenance8YearCost: Money.Eur(150_000m),
        heavyMaintenance16YearCost: Money.Eur(200_000m),
        operatingMaintenanceFixedCost: Money.Eur(6_000m),
        operatingMaintenanceVariableCostPerKilometer: 0.05m,
        annualInsuranceRate: Percentage.FromRatio(0.03m)).Value;

    public static readonly MileageBracket BracketA = MileageBracket.Create(
        minKilometers: 80_000m, maxKilometers: 149_999m,
        dryLeaseCoefficient: 1.0m, heavyMaintenanceCoefficient: 1.0m, operatingMaintenanceCoefficient: 1.0m).Value;

    public static readonly MileageBracket BracketB = MileageBracket.Create(
        minKilometers: 150_000m, maxKilometers: 200_000m,
        dryLeaseCoefficient: 1.05m, heavyMaintenanceCoefficient: 1.1m, operatingMaintenanceCoefficient: 1.05m).Value;

    public static readonly DryLeaseGridEntry DryLeaseGrid = DryLeaseGridEntry.Create(
        SeriesCode.Of("VECTRON"), DurationBracket.Create(0, null).Value, Money.Eur(20_000m)).Value;

    public static readonly BudgetPlanEntry BudgetPlanA = BudgetPlanEntry.Create(
        SeriesCode.Of("VECTRON"), BracketA, Money.Eur(2_000m), Money.Eur(1_500m), "2026").Value;

    public static readonly BudgetPlanEntry BudgetPlanB = BudgetPlanEntry.Create(
        SeriesCode.Of("VECTRON"), BracketB, Money.Eur(2_400m), Money.Eur(1_800m), "2026").Value;

    public static readonly PricingParameters Parameters = PricingParameters.Defaults(Currency.Eur);
}
