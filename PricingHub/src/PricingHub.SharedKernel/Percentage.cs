namespace PricingHub.SharedKernel;

/// <summary>
/// Un ratio (marge, remise, taux) — 0.15m représente 15 %. Remplace les
/// floats "nus" du prototype Python (<c>marge_hm = 0.15</c>) par un type qui
/// porte sa propre règle (jamais négatif) et son propre formatage.
/// </summary>
public readonly record struct Percentage
{
    public decimal Value { get; }

    private Percentage(decimal value) => Value = value;

    public static readonly Percentage Zero = new(0m);

    public static Percentage FromRatio(decimal value)
    {
        if (value < 0m)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Un pourcentage ne peut pas être négatif.");
        }

        return new Percentage(value);
    }

    public static Percentage FromPercent(decimal percent) => FromRatio(percent / 100m);

    public decimal ApplyTo(decimal amount) => amount * Value;

    /// <summary>1 - x, utilisé par exemple pour le plancher Dry lease
    /// (catalogue × (1 - remise maximale)).</summary>
    public Percentage Complement()
    {
        if (Value > 1m)
        {
            throw new InvalidOperationException("Le complément (1 − x) n'a de sens que pour un pourcentage ≤ 100 %.");
        }

        return new Percentage(1m - Value);
    }

    public static Percentage operator +(Percentage left, Percentage right) => new(left.Value + right.Value);

    public static bool operator >(Percentage left, Percentage right) => left.Value > right.Value;
    public static bool operator <(Percentage left, Percentage right) => left.Value < right.Value;
    public static bool operator >=(Percentage left, Percentage right) => left.Value >= right.Value;
    public static bool operator <=(Percentage left, Percentage right) => left.Value <= right.Value;

    public override string ToString() => Value.ToString("P1");
}
