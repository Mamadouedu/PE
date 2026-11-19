using PricingHub.Domain.Sales.QuoteAggregate;

namespace PricingHub.Domain.Sales.ScenarioComparisonAggregate;

/// <summary>Une offre, avec son libellé, au sein d'un comparateur (ex.
/// "Agressif", "Standard", "Prudent"). Référence une version précise de
/// l'offre — pas seulement son identité — pour que le comparateur reste
/// cohérent même si le KAM continue ensuite à éditer l'une des offres
/// comparées (ce qui ouvrirait une nouvelle <c>QuoteVersion</c>).</summary>
public sealed record ScenarioEntry(string Label, QuoteId QuoteId, QuoteVersionNumber QuoteVersion);
