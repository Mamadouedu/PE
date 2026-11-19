namespace PricingHub.Api.Contracts;

public sealed record ModelSummaryResponse(string ModelCode, string SeriesCode, string Name, decimal NewValue);
