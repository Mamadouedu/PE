// Adapte la réponse de l'API à ce qu'un KAM a le droit de voir (M3-07 : les
// coûts et marges ne sont jamais affichés). Tout ce qui n'est pas repris ici
// — `cout` par brique, `etapes_calcul`, `cout_reference_mensuel`, et le
// détail textuel des contrôles (qui peut mentionner un coût de référence,
// cf. le contrôle C7) — reste dans la réponse API mais n'atteint jamais
// l'écran du KAM.

import type { Brique, DetailOffreApi, StatutBrique } from "./types";
import { LIBELLE_BRIQUE as libelles } from "./types";

export interface LigneBriqueKam {
  brique: Brique;
  libelle: string;
  prixCatalogue: number;
  plancher: number;
  prixNegocie: number | null;
  prixRetenu: number;
  statut: StatutBrique;
}

export interface ControleKam {
  code: string;
  libelle: string;
  ok: boolean;
}

export const LIBELLE_NIVEAU: Record<number, string> = {
  0: "Niveau 0 — vous (KAM)",
  1: "Niveau 1 — Manager commercial",
  2: "Niveau 2 — Head of Pricing",
  3: "Niveau 3 — Direction",
};

export interface OffreKam {
  briques: LigneBriqueKam[];
  totalCatalogueMensuel: number;
  totalRetenuMensuel: number;
  totalPlancherMensuel: number;
  totalMensuel: number;
  totalContrat: number;
  remiseGlobale: number;
  prixKmSupplementaire: number;
  niveauValidation: number;
  libelleNiveau: string;
  envoiDirectPossible: boolean;
  controles: ControleKam[];
  tousControlesOk: boolean;
}

const ORDRE_BRIQUES: Brique[] = ["DL", "HM", "OM", "ASSURANCE"];

export function versVueKam(offre: DetailOffreApi): OffreKam {
  return {
    briques: ORDRE_BRIQUES.filter((b) => b in offre.par_brique).map((b) => {
      const d = offre.par_brique[b];
      return {
        brique: b,
        libelle: libelles[b],
        prixCatalogue: d.prix_catalogue,
        plancher: d.plancher,
        prixNegocie: d.prix_negocie,
        prixRetenu: d.prix_retenu,
        statut: d.statut,
      };
    }),
    totalCatalogueMensuel: offre.total_catalogue_par_loco_mensuel,
    totalRetenuMensuel: offre.total_retenu_par_loco_mensuel,
    totalPlancherMensuel: offre.total_plancher_par_loco_mensuel,
    totalMensuel: offre.total_retenu_mensuel,
    totalContrat: offre.total_retenu_contrat,
    remiseGlobale: offre.remise_globale,
    prixKmSupplementaire: offre.prix_km_supplementaire,
    niveauValidation: offre.niveau_validation,
    libelleNiveau: LIBELLE_NIVEAU[offre.niveau_validation] ?? `Niveau ${offre.niveau_validation}`,
    envoiDirectPossible: offre.niveau_validation === 0,
    controles: offre.controles.map((c) => ({ code: c.code, libelle: c.libelle, ok: c.ok })),
    tousControlesOk: offre.tous_controles_ok,
  };
}
