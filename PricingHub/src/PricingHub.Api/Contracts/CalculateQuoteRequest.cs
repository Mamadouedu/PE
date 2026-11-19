using PricingHub.Domain.Pricing;

namespace PricingHub.Api.Contracts;

/// <summary>
/// Entrée du calcul d'offre — équivalent de <c>ConfigurationOffre</c> côté
/// Python, limité pour l'instant au cas "sans locomotive de flotte
/// affectée" (âge et km saisis manuellement par le KAM), le même cas que
/// les tests de bout en bout du moteur de prix.
/// </summary>
public sealed record CalculateQuoteRequest(
    string CustomerCode,
    string ModelCode,
    decimal AnnualMileageKm,
    int DurationMonths,
    int Quantity,
    DateOnly StartDate,
    decimal AgeAtStartYears,
    decimal CumulativeMileageAtStartKm,
    bool HeavyMaintenance8Done,
    bool HeavyMaintenance16Done,
    IReadOnlyList<PriceLine>? IncludedLines,
    IReadOnlyDictionary<PriceLine, decimal>? NegotiatedPrices,
    string? CampaignCode);
