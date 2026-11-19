namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>Équivalent de l'énumération Python <c>StatutBrique</c>.</summary>
public enum QuoteLineStatus
{
    Ok,
    Alert,
    BelowFloor,
    Excluded,
}
