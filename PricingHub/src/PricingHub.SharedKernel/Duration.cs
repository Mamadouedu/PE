namespace PricingHub.SharedKernel;

/// <summary>Une durée de contrat, en mois — l'unité que le cahier des
/// charges utilise partout (grille Dry lease par tranche de durée, durée
/// maximale de campagne, etc.).</summary>
public readonly record struct Duration
{
    public int Months { get; }

    private Duration(int months) => Months = months;

    public static Duration FromMonths(int months)
    {
        if (months <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(months), months, "La durée doit être strictement positive.");
        }

        return new Duration(months);
    }

    /// <summary>Durée en années, utilisée par la valeur résiduelle
    /// (VR(a, k), section 6.2) — un <c>decimal</c>, pas un entier : 18 mois
    /// doit donner 1.5 an, pas 1.</summary>
    public decimal Years => Months / 12m;

    public static bool operator >(Duration left, Duration right) => left.Months > right.Months;
    public static bool operator <(Duration left, Duration right) => left.Months < right.Months;
    public static bool operator >=(Duration left, Duration right) => left.Months >= right.Months;
    public static bool operator <=(Duration left, Duration right) => left.Months <= right.Months;

    public override string ToString() => $"{Months} mois";
}
