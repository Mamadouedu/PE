import type { OffreKam } from "./api/offre";
import type { CalculateQuoteRequest } from "./api/types";

// M3-04 : comparateur de 3 scénarios côte à côte. Un scénario est un
// instantané (figé au moment de l'ajout) d'une requête de calcul déjà
// envoyée et de son résultat déjà filtré pour le KAM (`OffreKam`, sans coût
// ni marge). Reste volontairement côté client, jamais persisté : la
// `ScenarioComparison` persistée côté .NET est une fonctionnalité distincte
// (comparaisons nommées et durables entre plusieurs KAM), pas ce comparateur
// éphémère de brouillon.
export interface ScenarioComparaison {
  id: string;
  label: string;
  requete: CalculateQuoteRequest;
  offre: OffreKam;
}

export const MAX_SCENARIOS = 3;

export function libelleScenario(requete: CalculateQuoteRequest): string {
  const km = requete.annualMileageKm.toLocaleString("fr-FR");
  return `${requete.modelCode} · ${requete.durationMonths} mois · ${km} km/an`;
}
