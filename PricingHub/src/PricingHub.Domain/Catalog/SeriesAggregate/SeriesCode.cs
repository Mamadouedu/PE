namespace PricingHub.Domain.Catalog.SeriesAggregate;

/// <summary>Identité métier d'une série (ex. <c>"VECTRON"</c>) — le code que
/// le KAM choisit dans le configurateur, pas un GUID technique.</summary>
public readonly record struct SeriesCode
{
    public string Value { get; }

    private SeriesCode(string value) => Value = value;

    public static SeriesCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Le code série ne peut pas être vide.", nameof(value));
        }

        return new SeriesCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
