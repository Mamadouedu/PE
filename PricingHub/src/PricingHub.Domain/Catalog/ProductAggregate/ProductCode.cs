namespace PricingHub.Domain.Catalog.ProductAggregate;

/// <summary>Identité métier d'un produit (ex. <c>"LOCOMOTIVE"</c>).</summary>
public readonly record struct ProductCode
{
    public string Value { get; }

    private ProductCode(string value) => Value = value;

    public static ProductCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Le code produit ne peut pas être vide.", nameof(value));
        }

        return new ProductCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
