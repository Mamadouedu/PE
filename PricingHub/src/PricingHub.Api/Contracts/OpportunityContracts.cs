using PricingHub.Domain.Sales.OpportunityAggregate;

namespace PricingHub.Api.Contracts;

public sealed record OpenOpportunityRequest(string CustomerCode, string Title);

public sealed record LinkQuoteRequest(Guid QuoteId);

public sealed record OpportunityResponse(
    Guid Id, string CustomerCode, string Title, OpportunityStatus Status, int? PipedriveDealId, IReadOnlyList<Guid> QuoteIds);
