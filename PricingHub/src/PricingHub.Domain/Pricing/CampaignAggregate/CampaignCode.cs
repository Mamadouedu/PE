namespace PricingHub.Domain.Pricing.CampaignAggregate;

/// <summary>Identité métier d'une campagne commerciale (ex. <c>"AMS_2026"</c>).</summary>
public readonly record struct CampaignCode
{
    public string Value { get; }

    private CampaignCode(string value) => Value = value;

    public static CampaignCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Le code campagne ne peut pas être vide.", nameof(value));
        }

        return new CampaignCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
