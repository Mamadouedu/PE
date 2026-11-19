namespace PricingHub.Domain.Sales.ScenarioComparisonAggregate;

public readonly record struct ScenarioComparisonId(Guid Value)
{
    public static ScenarioComparisonId New() => new(Guid.NewGuid());

    public static ScenarioComparisonId Of(Guid value) => new(value);

    public override string ToString() => Value.ToString();
}
