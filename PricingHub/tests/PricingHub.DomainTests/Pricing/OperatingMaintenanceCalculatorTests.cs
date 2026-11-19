using PricingHub.Domain.Catalog.SeriesAggregate;
using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Pricing.PriceBookAggregate;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_om.py</c>.</summary>
public class OperatingMaintenanceCalculatorTests
{
    [Fact]
    public void BpOmBloqueLePrixCatalogue()
    {
        var priced = OperatingMaintenanceCalculator.Calculate(
            VectronFixture.Series, Mileage.FromKilometers(120_000m), VectronFixture.BracketA, VectronFixture.BudgetPlanA,
            VectronFixture.Parameters.OperatingMaintenanceMargin);

        var monthlyCost = (6_000m + 0.05m * 120_000m) / 12m * 1.0m;
        Assert.Equal(1_000.0m, monthlyCost, 6);
        Assert.True(monthlyCost * 1.12m < 1_500.0m);

        Assert.Equal(monthlyCost, priced.Cost.Amount, 6);
        Assert.Equal(1_500.0m, priced.CatalogPrice.Amount, 6);
        Assert.Equal(1_500.0m, priced.Floor.Amount, 6);
    }

    [Fact]
    public void CoutPlusMargeDomineQuandSuperieurAuBp()
    {
        // Isolé du cas BP-dominant par défaut : un OM/km élevé fait gagner le coût + marge.
        var series = Series.Create(
            SeriesCode.Of("S1"), "S1", Money.Eur(1_000_000m), serviceLifeYears: 30,
            endOfLifeResidualRate: Percentage.FromRatio(0.10m), referenceAnnualMileage: Mileage.FromKilometers(120_000m),
            heavyMaintenance8YearCost: Money.Eur(0m), heavyMaintenance16YearCost: Money.Eur(0m),
            operatingMaintenanceFixedCost: Money.Eur(0m), operatingMaintenanceVariableCostPerKilometer: 0.50m,
            annualInsuranceRate: Percentage.Zero).Value;

        var bracket = MileageBracket.Create(0m, null, 1.0m, 1.0m, 1.0m).Value;
        var budgetPlan = BudgetPlanEntry.Create(
            SeriesCode.Of("S1"), bracket, Money.Eur(0m), Money.Eur(100m), "2026").Value;

        var priced = OperatingMaintenanceCalculator.Calculate(
            series, Mileage.FromKilometers(120_000m), bracket, budgetPlan, Percentage.FromRatio(0.12m));

        var monthlyCost = (0m + 0.50m * 120_000m) / 12m * 1.0m;
        Assert.Equal(5_000.0m, monthlyCost, 6);

        var expectedCatalog = monthlyCost * 1.12m;
        Assert.True(expectedCatalog > 100.0m);
        Assert.Equal(expectedCatalog, priced.CatalogPrice.Amount, 6);
        Assert.Equal(100.0m, priced.Floor.Amount, 6);
    }
}
