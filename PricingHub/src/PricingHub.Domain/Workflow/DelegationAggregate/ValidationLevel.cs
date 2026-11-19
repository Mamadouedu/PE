namespace PricingHub.Domain.Workflow.DelegationAggregate;

/// <summary>Niveau de validation (1 à 3, section 6.3) — le niveau 0
/// (« dans les règles ») n'a pas de délégation : aucun validateur n'est
/// requis.</summary>
public readonly record struct ValidationLevel
{
    public int Value { get; }

    private ValidationLevel(int value) => Value = value;

    public static ValidationLevel Of(int value)
    {
        if (value is < 1 or > 3)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Le niveau de validation délégué doit être compris entre 1 et 3.");
        }

        return new ValidationLevel(value);
    }

    public override string ToString() => Value.ToString();
}
