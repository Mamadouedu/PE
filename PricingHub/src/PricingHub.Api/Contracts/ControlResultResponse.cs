namespace PricingHub.Api.Contracts;

/// <summary>Équivalent de <c>ResultatControle</c> côté Python — un des 8
/// contrôles avant envoi (section 6.4).</summary>
public sealed record ControlResultResponse(string Code, string Label, bool Ok, string Detail);
