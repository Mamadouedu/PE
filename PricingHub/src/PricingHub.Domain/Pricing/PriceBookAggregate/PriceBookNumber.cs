namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Numéro de version du référentiel pricing — toute offre mémorise
/// la version utilisée pour son calcul (traçabilité, M1-03).</summary>
public readonly record struct PriceBookNumber
{
    public int Value { get; }

    private PriceBookNumber(int value) => Value = value;

    public static PriceBookNumber Of(int value)
    {
        if (value <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Le numéro de version doit être strictement positif.");
        }

        return new PriceBookNumber(value);
    }

    public override string ToString() => Value.ToString();
}
