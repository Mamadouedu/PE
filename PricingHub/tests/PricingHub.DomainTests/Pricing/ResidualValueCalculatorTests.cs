using PricingHub.Domain.Pricing.Calculations;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_vr.py</c> — VR(a, k), section 6.2.</summary>
public class ResidualValueCalculatorTests
{
    [Fact]
    public void SansExcesDeKmNiHmRealisee_EgaleLaFormuleAttendue()
    {
        var vr = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters,
            ageYears: 5m, cumulativeMileage: Mileage.FromKilometers(600_000m),
            heavyMaintenance8YearDone: false, heavyMaintenance16YearDone: false);

        var expected = VectronFixture.Series.NewValue.Amount * (1m - (1m - 0.10m) * (5m / 30m));
        Assert.Equal(expected, vr.Amount, 6);
        Assert.Equal(1_700_000.0m, vr.Amount, 2);
    }

    [Fact]
    public void PenaliseeParLeDepassementDeKilometrage()
    {
        var sansExces = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 5m, Mileage.FromKilometers(600_000m), false, false);
        var avecExces = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 5m, Mileage.FromKilometers(1_100_000m), false, false);

        var difference = sansExces.Amount - avecExces.Amount;
        Assert.Equal(500_000m * VectronFixture.Parameters.ValueLossPerKilometerOutOfReference, difference, 6);
    }

    [Fact]
    public void NeDescendJamaisSousLePlancher()
    {
        var vr = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 30m, Mileage.FromKilometers(4_100_000m), false, false);

        Assert.Equal(
            VectronFixture.Series.NewValue.Amount * VectronFixture.Parameters.ResidualValueFloorRate.Value, vr.Amount, 6);
    }

    [Fact]
    public void BonusHmRealiseeAugmenteLaVr()
    {
        var sansBonus = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 8m, Mileage.FromKilometers(960_000m), false, false);
        var avecBonus8 = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 8m, Mileage.FromKilometers(960_000m), true, false);

        var difference = avecBonus8.Amount - sansBonus.Amount;
        Assert.Equal(VectronFixture.Parameters.ResidualValueBonusHm8.Value * VectronFixture.Series.NewValue.Amount, difference, 6);
    }
}
