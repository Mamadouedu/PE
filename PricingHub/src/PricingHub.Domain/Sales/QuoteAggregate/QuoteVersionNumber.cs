namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>Numéro de version d'une offre — commence à 1, incrémenté à
/// chaque nouvelle version ouverte par <see cref="Quote"/>.</summary>
public readonly record struct QuoteVersionNumber
{
    public int Value { get; }

    private QuoteVersionNumber(int value) => Value = value;

    public static QuoteVersionNumber Of(int value)
    {
        if (value <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Le numéro de version doit être strictement positif.");
        }

        return new QuoteVersionNumber(value);
    }

    public static QuoteVersionNumber First => Of(1);

    public QuoteVersionNumber Next() => Of(Value + 1);

    public override string ToString() => Value.ToString();
}
