namespace PricingHub.SharedKernel;

/// <summary>Un kilométrage — annuel, inclus, cumulé ou supplémentaire
/// selon le contexte. Toujours positif ou nul.</summary>
public readonly record struct Mileage
{
    public decimal Kilometers { get; }

    private Mileage(decimal kilometers) => Kilometers = kilometers;

    public static readonly Mileage Zero = new(0m);

    public static Mileage FromKilometers(decimal kilometers)
    {
        if (kilometers < 0m)
        {
            throw new ArgumentOutOfRangeException(nameof(kilometers), kilometers, "Un kilométrage ne peut pas être négatif.");
        }

        return new Mileage(kilometers);
    }

    public static Mileage operator +(Mileage left, Mileage right) => new(left.Kilometers + right.Kilometers);
    public static Mileage operator *(Mileage mileage, decimal factor) => FromKilometers(mileage.Kilometers * factor);

    public static bool operator >(Mileage left, Mileage right) => left.Kilometers > right.Kilometers;
    public static bool operator <(Mileage left, Mileage right) => left.Kilometers < right.Kilometers;
    public static bool operator >=(Mileage left, Mileage right) => left.Kilometers >= right.Kilometers;
    public static bool operator <=(Mileage left, Mileage right) => left.Kilometers <= right.Kilometers;

    public override string ToString() => $"{Kilometers:N0} km";
}
