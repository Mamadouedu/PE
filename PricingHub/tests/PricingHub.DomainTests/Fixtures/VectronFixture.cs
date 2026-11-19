using PricingHub.Domain.Catalog.ModelAggregate;
using PricingHub.Domain.Catalog.ProductAggregate;
using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Fixtures;

/// <summary>
/// Jeu de données de référence VECTRON — porté terme à terme depuis
/// <c>tests/conftest.py</c> (Python) pour que les deux suites de tests
/// comparent exactement les mêmes chiffres (filet de sécurité du portage).
///
/// Product "Locomotive" → Series "Vectron" (groupement) → Model "VECTRON"
/// (la variante technique qui porte les données de prix — équivalent 1:1
/// du <c>Serie</c> Python). Le code VECTRON est repris tel quel au niveau
/// Model, puisque c'est lui qui remplace l'onglet « Models » du Price
/// Configurator Excel.
/// </summary>
public static class VectronFixture
{
    public static readonly Product Product = PricingHub.Domain.Catalog.ProductAggregate.Product.Create(
        ProductCode.Of("LOCOMOTIVE"), "Locomotive").Value;

    public static readonly Series Series = PricingHub.Domain.Catalog.SeriesAggregate.Series.Create(
        SeriesCode.Of("VECTRON"), Product.Id, "Vectron").Value;

    public static readonly Model Model = PricingHub.Domain.Catalog.ModelAggregate.Model.Create(
        ModelCode.Of("VECTRON"),
        Series.Id,
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
        ModelCode.Of("VECTRON"), DurationBracket.Create(0, null).Value, Money.Eur(20_000m)).Value;

    public static readonly BudgetPlanEntry BudgetPlanA = BudgetPlanEntry.Create(
        ModelCode.Of("VECTRON"), BracketA, Money.Eur(2_000m), Money.Eur(1_500m), "2026").Value;

    public static readonly BudgetPlanEntry BudgetPlanB = BudgetPlanEntry.Create(
        ModelCode.Of("VECTRON"), BracketB, Money.Eur(2_400m), Money.Eur(1_800m), "2026").Value;

    public static readonly PricingParameters Parameters = PricingParameters.Defaults(Currency.Eur);
}
