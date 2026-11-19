using PricingHub.Domain.Pricing.CampaignAggregate;

namespace PricingHub.DomainTests.Pricing;

public class CampaignTests
{
    [Fact]
    public void RefuseUneDateDeFinAnterieureALaDateDeDebut()
    {
        var result = Campaign.Create(
            CampaignCode.Of("AMS"), "AMS", new DateOnly(2026, 6, 1), endDate: new DateOnly(2026, 1, 1));

        Assert.True(result.IsFailure);
    }

    [Fact]
    public void CouvreUneDateDansSaPeriode()
    {
        var campaign = Campaign.Create(
            CampaignCode.Of("AMS"), "AMS", new DateOnly(2026, 1, 1), new DateOnly(2026, 3, 31)).Value;

        Assert.True(campaign.Covers(new DateOnly(2026, 2, 15)));
        Assert.False(campaign.Covers(new DateOnly(2026, 4, 1)));
    }

    [Fact]
    public void SansDateDeFin_CouvreIndefiniment()
    {
        var campaign = Campaign.Create(CampaignCode.Of("RENEWAL"), "Renewal", new DateOnly(2026, 1, 1)).Value;

        Assert.True(campaign.Covers(new DateOnly(2030, 1, 1)));
    }

    [Fact]
    public void UneCampagneClotureeNeCouvrePlusRien()
    {
        var campaign = Campaign.Create(CampaignCode.Of("AMS"), "AMS", new DateOnly(2026, 1, 1)).Value;
        campaign.Close();

        Assert.False(campaign.Covers(new DateOnly(2026, 1, 15)));
    }
}
