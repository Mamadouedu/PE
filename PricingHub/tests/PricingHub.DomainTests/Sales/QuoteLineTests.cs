using PricingHub.Domain.Pricing.Calculations;
using PricingHub.Domain.Sales.QuoteAggregate;
using PricingHub.DomainTests.Fixtures;
using PricingHub.SharedKernel;

namespace PricingHub.DomainTests.Sales;

/// <summary>Porté depuis les deux derniers cas de <c>tests/test_engine_dry_lease.py</c>
/// (décision commerciale, pas calcul catalogue).</summary>
public class QuoteLineTests
{
    private static readonly PricedLine DryLeaseAtBracketA =
        DryLeaseCalculator.Calculate(VectronFixture.DryLeaseGrid, VectronFixture.BracketA, VectronFixture.Parameters.MaximumDiscount);

    [Fact]
    public void PrixNegocieSousPlancherEstSignale()
    {
        var line = QuoteLine.Included(DryLeaseAtBracketA, Money.Eur(17_000m));

        Assert.Equal(17_000.0m, line.RetainedPrice.Amount, 6);
        Assert.True(line.RetainedPrice < line.Floor);
        Assert.Equal(QuoteLineStatus.BelowFloor, line.Status);
    }

    [Fact]
    public void BriqueExclueVautZero()
    {
        var line = QuoteLine.Excluded(DryLeaseAtBracketA);

        Assert.Equal(0.0m, line.RetainedPrice.Amount);
        Assert.Equal(QuoteLineStatus.Excluded, line.Status);
    }
}
