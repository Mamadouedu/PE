// Adapte la réponse de l'API .NET à ce qu'un KAM a le droit de voir (M3-07 :
// les coûts et marges ne sont jamais affichés). Tout ce qui n'est pas repris
// ici — `lines[].cost`, et le détail textuel des contrôles (qui peut
// mentionner un coût de référence, cf. le contrôle C7) — reste dans la
// réponse API mais n'atteint jamais l'écran du KAM.

import type { PriceLine, QuoteLineStatus, QuoteResponse } from "./types";
import { LIBELLE_PRICE_LINE as libelles } from "./types";

// Les composants d'affichage (ResultatOffre, Comparateur, App.css) datent du
// prototype Python et utilisent ces 4 statuts comme classes CSS/clés de
// libellé ; on y ramène les valeurs `QuoteLineStatus` de l'API .NET ici,
// au même endroit que le reste du filtrage M3-07, plutôt que de les
// propager (et de réécrire CSS + composants) jusqu'à l'écran.
export type StatutBrique = "ok" | "alerte" | "sous_plancher" | "exclue";

const SLUG_STATUT: Record<QuoteLineStatus, StatutBrique> = {
  Ok: "ok",
  Alert: "alerte",
  BelowFloor: "sous_plancher",
  Excluded: "exclue",
};

export interface LigneBriqueKam {
  brique: PriceLine;
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
  quoteId: string;
  versionNumber: number;
  briques: LigneBriqueKam[];
  totalRetenuMensuel: number;
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

const ORDRE_BRIQUES: PriceLine[] = ["DryLease", "HeavyMaintenance", "OperatingMaintenance", "Insurance"];

export function versVueKam(offre: QuoteResponse): OffreKam {
  const parLigne = new Map(offre.lines.map((l) => [l.line, l]));
  return {
    quoteId: offre.quoteId,
    versionNumber: offre.versionNumber,
    briques: ORDRE_BRIQUES.filter((b) => parLigne.has(b)).map((b) => {
      const l = parLigne.get(b)!;
      return {
        brique: b,
        libelle: libelles[b],
        prixCatalogue: l.catalogPrice,
        plancher: l.floor,
        prixNegocie: l.negotiatedPrice,
        prixRetenu: l.retainedPrice,
        statut: SLUG_STATUT[l.status],
      };
    }),
    totalRetenuMensuel: offre.totalRetainedPerUnitMonthly,
    totalMensuel: offre.totalRetainedMonthly,
    totalContrat: offre.totalRetainedContract,
    remiseGlobale: offre.globalDiscount,
    prixKmSupplementaire: offre.additionalMileagePricePerKm,
    niveauValidation: offre.validationLevel,
    libelleNiveau: LIBELLE_NIVEAU[offre.validationLevel] ?? `Niveau ${offre.validationLevel}`,
    envoiDirectPossible: offre.validationLevel === 0,
    controles: offre.controls.map((c) => ({ code: c.code, libelle: c.label, ok: c.ok })),
    tousControlesOk: offre.allControlsOk,
  };
}
