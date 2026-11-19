import { describe, expect, it } from "vitest";
import type { QuoteResponse } from "./types";
import { versVueKam } from "./offre";

// Fixture minimale mais réaliste : une réponse API complète, avec des coûts
// et des marges bien distincts des prix, pour que les assertions ci-dessous
// aient un sens (si `cost` valait la même chose que `catalogPrice`, une
// fuite ne se verrait pas).
function offreApiDeTest(): QuoteResponse {
  return {
    quoteId: "dd6de88a-e33d-4da8-9af0-7dda4ac25d26",
    versionNumber: 1,
    status: "Calculated",
    priceBookNumber: 1,
    lines: [
      { line: "DryLease", cost: 15_000, catalogPrice: 20_000, floor: 18_000, negotiatedPrice: null, retainedPrice: 20_000, status: "Ok" },
      { line: "HeavyMaintenance", cost: 1_822.91, catalogPrice: 2_096.35, floor: 2_000, negotiatedPrice: null, retainedPrice: 2_096.35, status: "Ok" },
      { line: "OperatingMaintenance", cost: 1_000, catalogPrice: 1_500, floor: 1_500, negotiatedPrice: null, retainedPrice: 1_500, status: "Ok" },
      { line: "Insurance", cost: 4_100, catalogPrice: 4_305, floor: 4_100, negotiatedPrice: null, retainedPrice: 4_305, status: "Ok" },
    ],
    residualValueAtStart: 1_700_000,
    residualValueAtEnd: 1_580_000,
    monthlyValueLoss: 5_000,
    additionalMileagePricePerKm: 0.29,
    totalCatalogPerUnitMonthly: 27_901.35,
    totalRetainedPerUnitMonthly: 27_901.35,
    totalRetainedMonthly: 27_901.35,
    totalRetainedContract: 669_632.4,
    globalDiscount: 0,
    monthlyReferenceCost: 11_922.91,
    validationLevel: 0,
    validationLevelReasons: ["Dans les règles : validation KAM (niveau 0)"],
    controls: [{ code: "C1_DUREE_CAMPAGNE", label: "Durée ≤ durée maximale de campagne", ok: true, detail: "ok" }],
    allControlsOk: true,
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

    // Et structurellement : aucune ligne de brique ne porte de champ `cost`.
    for (const ligne of vue.briques) {
      expect(ligne).not.toHaveProperty("cost");
    }
  });

  it("reprend les prix et le niveau de validation utiles au KAM", () => {
    const vue = versVueKam(offreApiDeTest());

    expect(vue.briques.map((b) => b.brique)).toEqual(["DryLease", "HeavyMaintenance", "OperatingMaintenance", "Insurance"]);
    expect(vue.briques[0].prixRetenu).toBe(20_000);
    expect(vue.totalMensuel).toBe(27_901.35);
    expect(vue.niveauValidation).toBe(0);
    expect(vue.envoiDirectPossible).toBe(true);
    expect(vue.libelleNiveau).toBe("Niveau 0 — vous (KAM)");
  });

  it("signale qu'un envoi direct n'est pas possible dès que le niveau dépasse 0", () => {
    const api = offreApiDeTest();
    api.validationLevel = 2;

    const vue = versVueKam(api);

    expect(vue.envoiDirectPossible).toBe(false);
    expect(vue.libelleNiveau).toBe("Niveau 2 — Head of Pricing");
  });
});
