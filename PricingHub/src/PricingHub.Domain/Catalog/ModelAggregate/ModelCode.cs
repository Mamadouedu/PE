namespace PricingHub.Domain.Catalog.ModelAggregate;

/// <summary>Identité métier d'un modèle (ex. <c>"VECTRON_MS"</c>) — la
/// variante technique précise que le KAM choisit dans le configurateur.</summary>
public readonly record struct ModelCode
{
    public string Value { get; }

    private ModelCode(string value) => Value = value;

    public static ModelCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Le code modèle ne peut pas être vide.", nameof(value));
        }

        return new ModelCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
