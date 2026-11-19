namespace PricingHub.Domain.Workflow.ApprovalRequestAggregate;

/// <summary>Numéro séquentiel au registre central des dérogations (M4-05).</summary>
public readonly record struct ApprovalRequestId
{
    public int Value { get; }

    private ApprovalRequestId(int value) => Value = value;

    public static ApprovalRequestId Of(int value)
    {
        if (value <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Le numéro de dérogation doit être strictement positif.");
        }

        return new ApprovalRequestId(value);
    }

    public override string ToString() => Value.ToString();
}
