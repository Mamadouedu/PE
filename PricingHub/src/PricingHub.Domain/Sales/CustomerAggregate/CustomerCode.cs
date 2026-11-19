namespace PricingHub.Domain.Sales.CustomerAggregate;

/// <summary>Identité métier d'un client (ex. code tiers Akiem), pas un GUID
/// technique.</summary>
public readonly record struct CustomerCode
{
    public string Value { get; }

    private CustomerCode(string value) => Value = value;

    public static CustomerCode Of(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Le code client ne peut pas être vide.", nameof(value));
        }

        return new CustomerCode(value.Trim().ToUpperInvariant());
    }

    public override string ToString() => Value;
}
