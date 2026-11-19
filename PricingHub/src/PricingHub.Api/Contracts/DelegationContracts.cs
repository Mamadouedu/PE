namespace PricingHub.Api.Contracts;

public sealed record CreateDelegationRequest(int Level, string Name, string Email, string? AlternateEmail);

public sealed record DelegationResponse(int Level, string Name, string Email, string? AlternateEmail);
