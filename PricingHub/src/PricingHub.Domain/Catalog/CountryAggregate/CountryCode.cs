namespace PricingHub.Domain.Catalog.CountryAggregate;

/// <summary>Code pays ISO 3166-1 alpha-2 (ex. <c>"FR"</c>, <c>"DE"</c>).</summary>
public readonly record struct CountryCode
{
    public string Value { get; }

    private CountryCode(string value) => Value = value;

    public static CountryCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Trim().Length != 2)
        {
            throw new ArgumentException("Le code pays doit comporter exactement 2 lettres (ISO 3166-1 alpha-2).", nameof(value));
        }

        return new CountryCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
