using PricingHub.Domain.Pricing.Calculations;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_hm.py</c>.</summary>
public class HeavyMaintenanceCalculatorTests
{
    [Fact]
    public void CoutHmParKm_EgaleLaFormule()
    {
        var expected = (150_000m + 200_000m) / (16m * 120_000m);
        Assert.Equal(expected, VectronFixture.Model.HeavyMaintenanceCostPerKilometer, 10);
    }

    [Fact]
    public void PrixCatalogueHmAuDessusDuBp()
    {
        var priced = HeavyMaintenanceCalculator.Calculate(
            VectronFixture.Model, Mileage.FromKilometers(120_000m), VectronFixture.BracketA, VectronFixture.BudgetPlanA,
            VectronFixture.Parameters.HeavyMaintenanceMargin);

        var monthlyCost = (150_000m + 200_000m) / (16m * 120_000m) * 120_000m / 12m * 1.0m;
        Assert.Equal(1822.9166666667m, monthlyCost, 6);

        var expectedCatalog = monthlyCost * 1.15m;
        Assert.Equal(monthlyCost, priced.Cost.Amount, 6);
        Assert.Equal(expectedCatalog, priced.CatalogPrice.Amount, 6);
        Assert.Equal(2_000.0m, priced.Floor.Amount, 6);
    }

    [Fact]
    public void PlancherHmBloqueLePrixCatalogueQuandLeBpEstPlusHaut()
    {
        // À 80 000 km/an (bas de la tranche A), le BP HM (2 000) dépasse le coût + marge.
        var priced = HeavyMaintenanceCalculator.Calculate(
            VectronFixture.Model, Mileage.FromKilometers(80_000m), VectronFixture.BracketA, VectronFixture.BudgetPlanA,
            VectronFixture.Parameters.HeavyMaintenanceMargin);

        var monthlyCost = (150_000m + 200_000m) / (16m * 120_000m) * 80_000m / 12m * 1.0m;
        Assert.True(monthlyCost * 1.15m < 2_000.0m);
        Assert.Equal(2_000.0m, priced.CatalogPrice.Amount, 6);
        Assert.Equal(2_000.0m, priced.Floor.Amount, 6);
    }
}
