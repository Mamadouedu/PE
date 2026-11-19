using PricingHub.Domain.Pricing;
using PricingHub.Domain.Sales.QuoteAggregate;

namespace PricingHub.Api.Contracts;

public sealed record QuoteLineResponse(
    PriceLine Line,
    decimal Cost,
    decimal CatalogPrice,
    decimal Floor,
    decimal? NegotiatedPrice,
    decimal RetainedPrice,
    QuoteLineStatus Status);

/// <summary>Sortie du calcul d'offre — équivalent de <c>DetailOffre</c>
/// côté Python, plus l'identité et la version de l'offre persistée.</summary>
public sealed record QuoteResponse(
    Guid QuoteId,
    int VersionNumber,
    QuoteStatus Status,
    int PriceBookNumber,
    IReadOnlyList<QuoteLineResponse> Lines,
    decimal ResidualValueAtStart,
    decimal ResidualValueAtEnd,
    decimal MonthlyValueLoss,
    decimal AdditionalMileagePricePerKm,
    decimal TotalCatalogPerUnitMonthly,
    decimal TotalRetainedPerUnitMonthly,
    decimal TotalRetainedMonthly,
    decimal TotalRetainedContract,
    decimal GlobalDiscount,
    decimal MonthlyReferenceCost,
    int ValidationLevel,
    IReadOnlyList<string> ValidationLevelReasons,
    IReadOnlyList<ControlResultResponse> Controls,
    bool AllControlsOk);
