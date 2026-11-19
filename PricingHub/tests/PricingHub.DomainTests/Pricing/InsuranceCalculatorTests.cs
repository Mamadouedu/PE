using PricingHub.Domain.Pricing.Calculations;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Pricing;

/// <summary>Porté depuis <c>tests/test_engine_assurance.py</c>.</summary>
public class InsuranceCalculatorTests
{
    [Fact]
    public void PrimeEtPrixCatalogueAssurance()
    {
        // VR début/fin pour config_base (âge 5→7 ans, km 600 000→840 000 sur 24 mois).
        var vrStart = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 5m, Mileage.FromKilometers(600_000m), false, false);
        var vrEnd = ResidualValueCalculator.Calculate(
            VectronFixture.Series, VectronFixture.Parameters, 7m, Mileage.FromKilometers(840_000m), false, false);
        var average = Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);

        var priced = InsuranceCalculator.Calculate(VectronFixture.Series, average, VectronFixture.Parameters.InsuranceMargin);

        var expectedPremium = average.Amount * 0.03m / 12m;
        Assert.Equal(expectedPremium, priced.Cost.Amount, 6);
        Assert.Equal(expectedPremium, priced.Floor.Amount, 6);
        Assert.Equal(expectedPremium * 1.05m, priced.CatalogPrice.Amount, 6);
    }

    [Fact]
    public void PrimeSuitLaValeurResidentielleMoyenne_BaisseQuandLeContratEstPlusLong()
    {
        Money AveragePour(decimal dureeAns)
        {
            var vrStart = ResidualValueCalculator.Calculate(
                VectronFixture.Series, VectronFixture.Parameters, 5m, Mileage.FromKilometers(600_000m), false, false);
            var vrEnd = ResidualValueCalculator.Calculate(
                VectronFixture.Series, VectronFixture.Parameters, 5m + dureeAns,
                Mileage.FromKilometers(600_000m + 120_000m * dureeAns), false, false);
            return Money.Eur((vrStart.Amount + vrEnd.Amount) / 2m);
        }

        var primeCourte = InsuranceCalculator.Calculate(VectronFixture.Series, AveragePour(1m), VectronFixture.Parameters.InsuranceMargin);
        var primeLongue = InsuranceCalculator.Calculate(VectronFixture.Series, AveragePour(5m), VectronFixture.Parameters.InsuranceMargin);

        Assert.True(primeLongue.Cost.Amount < primeCourte.Cost.Amount);
    }
}
