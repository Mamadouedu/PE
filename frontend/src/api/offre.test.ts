import { describe, expect, it } from "vitest";
import type { DetailOffreApi } from "./types";
import { versVueKam } from "./offre";

// Fixture minimale mais réaliste : une réponse API complète, avec des coûts
// et des marges bien distincts des prix, pour que les assertions ci-dessous
// aient un sens (si `cout` valait la même chose que `prix_catalogue`, une
// fuite ne se verrait pas).
function offreApiDeTest(): DetailOffreApi {
  return {
    version_referentiel: 1,
    par_brique: {
      DL: {
        brique: "DL",
        cout: 15_000,
        prix_catalogue: 20_000,
        plancher: 18_000,
        prix_negocie: null,
        prix_retenu: 20_000,
        statut: "ok",
      },
      HM: {
        brique: "HM",
        cout: 1_822.91,
        prix_catalogue: 2_096.35,
        plancher: 2_000,
        prix_negocie: null,
        prix_retenu: 2_096.35,
        statut: "ok",
      },
      OM: {
        brique: "OM",
        cout: 1_000,
        prix_catalogue: 1_500,
        plancher: 1_500,
        prix_negocie: null,
        prix_retenu: 1_500,
        statut: "ok",
      },
      ASSURANCE: {
        brique: "ASSURANCE",
        cout: 4_100,
        prix_catalogue: 4_305,
        plancher: 4_100,
        prix_negocie: null,
        prix_retenu: 4_305,
        statut: "ok",
      },
    },
    etapes_calcul: [{ libelle: "Coût mensuel HM (avant marge)", valeur: 1_822.91 }],
    valeur_residuelle_debut: 1_700_000,
    valeur_residuelle_fin: 1_580_000,
    perte_valeur_totale: 120_000,
    perte_valeur_mensuelle: 5_000,
    prix_km_supplementaire: 0.29,
    total_catalogue_par_loco_mensuel: 27_901.35,
    total_retenu_par_loco_mensuel: 27_901.35,
    total_plancher_par_loco_mensuel: 25_600,
    total_retenu_mensuel: 27_901.35,
    total_retenu_contrat: 669_632.4,
    remise_globale: 0,
    cout_reference_mensuel: 11_922.91,
    niveau_validation: 0,
    motifs_niveau_validation: ["Dans les règles : validation KAM (niveau 0)"],
    controles: [{ code: "C1", libelle: "Durée ≤ durée maximale de campagne", ok: true, detail: "ok" }],
    tous_controles_ok: true,
  };
}

describe("versVueKam", () => {
  it("ne reprend aucun champ de coût ou de marge (M3-07)", () => {
    const vue = versVueKam(offreApiDeTest());
    const serialise = JSON.stringify(vue);

    // Les valeurs de coût de la fixture ne doivent apparaître nulle part :
    // ni le coût par brique, ni le coût de référence (Direction).
    expect(serialise).not.toContain("15000");
    expect(serialise).not.toContain("1822.91");
    expect(serialise).not.toContain("11922.91");

    // Et structurellement : aucune ligne de brique ne porte de champ `cout`.
    for (const ligne of vue.briques) {
      expect(ligne).not.toHaveProperty("cout");
    }
  });

  it("reprend les prix et le niveau de validation utiles au KAM", () => {
    const vue = versVueKam(offreApiDeTest());

    expect(vue.briques.map((b) => b.brique)).toEqual(["DL", "HM", "OM", "ASSURANCE"]);
    expect(vue.briques[0].prixRetenu).toBe(20_000);
    expect(vue.totalMensuel).toBe(27_901.35);
    expect(vue.niveauValidation).toBe(0);
    expect(vue.envoiDirectPossible).toBe(true);
    expect(vue.libelleNiveau).toBe("Niveau 0 — vous (KAM)");
  });

  it("signale qu'un envoi direct n'est pas possible dès que le niveau dépasse 0", () => {
    const api = offreApiDeTest();
    api.niveau_validation = 2;

    const vue = versVueKam(api);

    expect(vue.envoiDirectPossible).toBe(false);
    expect(vue.libelleNiveau).toBe("Niveau 2 — Head of Pricing");
  });
});
