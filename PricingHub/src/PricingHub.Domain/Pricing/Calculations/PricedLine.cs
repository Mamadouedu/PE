using PricingHub.SharedKernel;

namespace PricingHub.Domain.Pricing.Calculations;

/// <summary>Sortie brute d'un calculateur de brique : coût, prix catalogue
/// et plancher — avant toute décision commerciale (prix négocié, brique
/// exclue). Cette décision est portée par <c>Sales.Quote</c>, qui combine
/// un <see cref="PricedLine"/> avec le choix du KAM.</summary>
public sealed record PricedLine(PriceLine Line, Money Cost, Money CatalogPrice, Money Floor);
