import { describe, expect, it } from "vitest";
import { libelleScenario } from "./scenario";
import type { ConfigurationOffre } from "./api/types";

function configurationDeTest(partiel: Partial<ConfigurationOffre> = {}): ConfigurationOffre {
  return {
    client_code: "CLIENTOK",
    serie_code: "VECTRON",
    km_annuel: 120_000,
    duree_mois: 24,
    quantite: 1,
    date_debut: "2026-01-01",
    briques_incluses: ["DL", "HM", "OM", "ASSURANCE"],
    prix_negocies: {},
    ...partiel,
  };
}

// toLocaleString("fr-FR") sépare les milliers par une espace fine
// insécable (U+202F), pas une espace ordinaire — on la reproduit ici plutôt
// que de deviner le bon caractère dans une chaîne attendue écrite à la main.
const km = (n: number) => n.toLocaleString("fr-FR");

describe("libelleScenario", () => {
  it("résume la série, la durée et le kilométrage", () => {
    expect(libelleScenario(configurationDeTest())).toBe(`VECTRON · 24 mois · ${km(120_000)} km/an`);
  });

  it("suit les changements de configuration", () => {
    const config = configurationDeTest({ serie_code: "TRAXX", duree_mois: 36, km_annuel: 160_000 });
    expect(libelleScenario(config)).toBe(`TRAXX · 36 mois · ${km(160_000)} km/an`);
  });
});
