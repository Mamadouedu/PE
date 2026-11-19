namespace PricingHub.Domain.Sales.QuoteAggregate;

public readonly record struct QuoteId(Guid Value)
{
    public static QuoteId New() => new(Guid.NewGuid());

    public static QuoteId Of(Guid value) => new(value);

    public override string ToString() => Value.ToString();
}
