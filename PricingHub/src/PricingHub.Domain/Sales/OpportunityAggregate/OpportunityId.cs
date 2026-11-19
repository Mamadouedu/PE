namespace PricingHub.Domain.Sales.OpportunityAggregate;

public readonly record struct OpportunityId(Guid Value)
{
    public static OpportunityId New() => new(Guid.NewGuid());

    public static OpportunityId Of(Guid value) => new(value);

    public override string ToString() => Value.ToString();
}
