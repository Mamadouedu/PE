using PricingHub.Domain.Pricing.Calculations;
using PricingHub.DomainTests.Fixtures;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_km_supplementaire.py</c>.</summary>
public class AdditionalMileageCalculatorTests
{
    [Fact]
    public void PrixKmSupplementaire()
    {
        var rate = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            VectronFixture.Model, VectronFixture.BracketA, VectronFixture.Parameters.AdditionalMileageSurcharge);

        var costHmPerKm = (150_000m + 200_000m) / (16m * 120_000m);
        var expected = (costHmPerKm * 1.0m + 0.05m * 1.0m) * 1.25m;
        Assert.Equal(expected, rate, 8);
    }

    [Fact]
    public void SuitLesCoefficientsDeTranche()
    {
        var rateA = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            VectronFixture.Model, VectronFixture.BracketA, VectronFixture.Parameters.AdditionalMileageSurcharge);
        var rateB = AdditionalMileageCalculator.CalculatePerKilometerPrice(
            VectronFixture.Model, VectronFixture.BracketB, VectronFixture.Parameters.AdditionalMileageSurcharge);

        // Tranche B : coefficients HM/OM plus élevés (1.1 / 1.05) => km supp plus cher.
        Assert.True(rateB > rateA);
    }
}
