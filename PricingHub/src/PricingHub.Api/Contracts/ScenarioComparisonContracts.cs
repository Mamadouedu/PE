namespace PricingHub.Api.Contracts;

public sealed record CreateScenarioComparisonRequest(string CustomerCode, string Name, string CreatedBy);

public sealed record AddScenarioRequest(string Label, Guid QuoteId, int QuoteVersion);

public sealed record ScenarioEntryResponse(string Label, Guid QuoteId, int QuoteVersion);

public sealed record ScenarioComparisonResponse(
    Guid Id, string CustomerCode, string Name, string CreatedBy, DateTimeOffset CreatedAt,
    IReadOnlyList<ScenarioEntryResponse> Scenarios);
