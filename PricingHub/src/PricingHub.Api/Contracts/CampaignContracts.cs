namespace PricingHub.Api.Contracts;

public sealed record CampaignResponse(string Code, string Name, int? MaxDurationMonths, DateOnly StartDate, DateOnly? EndDate);
