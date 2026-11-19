using PricingHub.Domain.Pricing.Calculations;
using PricingHub.DomainTests.Fixtures;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_dry_lease.py</c>.</summary>
public class DryLeaseCalculatorTests
{
    [Fact]
    public void PrixCatalogueEtPlancher()
    {
        var priced = DryLeaseCalculator.Calculate(
            VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount);

        Assert.Equal(20_000.0m, priced.CatalogPrice.Amount, 6);
        Assert.Equal(20_000.0m * 0.90m, priced.Floor.Amount, 6);
    }

    [Fact]
    public void CoefficientDlChangeSelonLaTrancheDeKm()
    {
        var priced = DryLeaseCalculator.Calculate(
            VectronFixture.DryLeaseGrid, VectronFixture.BracketB, VectronFixture.Parameters.MaximumDiscount);

        // tranche B : coefficient_dl = 1.05
        Assert.Equal(20_000.0m * 1.05m, priced.CatalogPrice.Amount, 6);
    }
}
