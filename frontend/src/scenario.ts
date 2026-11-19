import type { OffreKam } from "./api/offre";
import type { ConfigurationOffre } from "./api/types";

// M3-04 : comparateur de 3 scénarios côte à côte. Un scénario est un
// instantané (figé au moment de l'ajout) d'une configuration déjà chiffrée
// et de son résultat déjà filtré pour le KAM (`OffreKam`, sans coût ni marge).
export interface ScenarioComparaison {
  id: string;
  label: string;
  configuration: ConfigurationOffre;
  offre: OffreKam;
}

export const MAX_SCENARIOS = 3;

export function libelleScenario(configuration: ConfigurationOffre): string {
  const km = configuration.km_annuel.toLocaleString("fr-FR");
  return `${configuration.serie_code} · ${configuration.duree_mois} mois · ${km} km/an`;
}
