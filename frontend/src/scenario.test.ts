import { describe, expect, it } from "vitest";
import { libelleScenario } from "./scenario";
import type { CalculateQuoteRequest } from "./api/types";

function requeteDeTest(partiel: Partial<CalculateQuoteRequest> = {}): CalculateQuoteRequest {
  return {
    customerCode: "CLIENTOK",
    modelCode: "VECTRON",
    annualMileageKm: 120_000,
    durationMonths: 24,
    quantity: 1,
    startDate: "2026-01-01",
    ageAtStartYears: 5,
    cumulativeMileageAtStartKm: 600_000,
    heavyMaintenance8Done: false,
    heavyMaintenance16Done: false,
    includedLines: ["DryLease", "HeavyMaintenance", "OperatingMaintenance", "Insurance"],
    negotiatedPrices: {},
    campaignCode: null,
    ...partiel,
  };
}

// toLocaleString("fr-FR") sépare les milliers par une espace fine
// insécable (U+202F), pas une espace ordinaire — on la reproduit ici plutôt
// que de deviner le bon caractère dans une chaîne attendue écrite à la main.
const km = (n: number) => n.toLocaleString("fr-FR");

describe("libelleScenario", () => {
  it("résume le modèle, la durée et le kilométrage", () => {
    expect(libelleScenario(requeteDeTest())).toBe(`VECTRON · 24 mois · ${km(120_000)} km/an`);
  });

  it("suit les changements de requête", () => {
    const requete = requeteDeTest({ modelCode: "TRAXX", durationMonths: 36, annualMileageKm: 160_000 });
    expect(libelleScenario(requete)).toBe(`TRAXX · 36 mois · ${km(160_000)} km/an`);
  });
});
