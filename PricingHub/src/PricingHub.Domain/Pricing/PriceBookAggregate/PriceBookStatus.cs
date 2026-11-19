namespace PricingHub.Domain.Pricing.PriceBookAggregate;

/// <summary>Cycle de vie d'une version du référentiel — équivalent de
/// l'énumération Python <c>StatutVersion</c> (M1-03).</summary>
public enum PriceBookStatus
{
    Draft,
    Published,
    Archived,
}
