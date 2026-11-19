namespace PricingHub.Domain.Sales.QuoteAggregate;

/// <summary>Cycle de vie d'une offre — n'existe pas dans le prototype
/// Python, qui recalculait à la volée sans conserver d'état entre les
/// appels.</summary>
public enum QuoteStatus
{
    Draft,
    Calculated,
    Submitted,
    Approved,
    Rejected,
}
