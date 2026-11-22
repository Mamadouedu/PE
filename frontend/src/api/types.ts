// Types côté KAM : un sous-ensemble volontairement restreint de ce que
// l'API renvoie. `DetailOffre` (back-end) porte aussi `cout`, `etapes_calcul`
// et `cout_reference_mensuel` — jamais importés ici : les coûts et marges ne
// sont pas visibles des KAM (M3-07). Voir `offre.ts` pour l'adaptation.

export type Brique = "DL" | "HM" | "OM" | "ASSURANCE";

export const LIBELLE_BRIQUE: Record<Brique, string> = {
  DL: "Dry lease",
  HM: "Heavy maintenance",
  OM: "Operation maintenance",
  ASSURANCE: "Assurance",
};

export type StatutBrique = "ok" | "alerte" | "sous_plancher" | "exclue";

export interface ConfigurationOffre {
  client_code: string;
  serie_code: string;
  locomotive_numero?: string | null;
  km_annuel: number;
  duree_mois: number;
  quantite: number;
  date_debut: string;
  briques_incluses: Brique[];
  prix_negocies: Partial<Record<Brique, number>>;
  age_debut_ans?: number | null;
  km_cumules_debut?: number | null;
  hm_8_realisee?: boolean;
  hm_16_realisee?: boolean;
  campagne?: boolean;
}

export interface DetailBriqueApi {
  brique: Brique;
  cout: number;
  prix_catalogue: number;
  plancher: number;
  prix_negocie: number | null;
  prix_retenu: number;
  statut: StatutBrique;
}

export interface ResultatControleApi {
  code: string;
  libelle: string;
  ok: boolean;
  detail: string;
}

export interface DetailOffreApi {
  version_referentiel: number;
  par_brique: Record<Brique, DetailBriqueApi>;
  etapes_calcul: { libelle: string; valeur: number }[];
  valeur_residuelle_debut: number;
  valeur_residuelle_fin: number;
  perte_valeur_totale: number;
  perte_valeur_mensuelle: number;
  prix_km_supplementaire: number;
  total_catalogue_par_loco_mensuel: number;
  total_retenu_par_loco_mensuel: number;
  total_plancher_par_loco_mensuel: number;
  total_retenu_mensuel: number;
  total_retenu_contrat: number;
  remise_globale: number;
  cout_reference_mensuel: number;
  niveau_validation: number;
  motifs_niveau_validation: string[];
  controles: ResultatControleApi[];
  tous_controles_ok: boolean;
}

export interface ErreurApi {
  detail: unknown;
}

export type StatutDerogation = "en_attente" | "approuvee" | "rejetee";

export interface DerogationApi {
  id: number;
  statut: StatutDerogation;
  niveau: number;
  demandeur: string;
  justification: string;
  configuration: ConfigurationOffre;
  version_referentiel: number;
  client_code: string;
  serie_code: string;
  montant_mensuel_retenu: number;
  validateur_email: string | null;
  date_demande: string;
  date_decision: string | null;
  decideur: string | null;
  commentaire_decision: string | null;
}
