import { useState } from "react";
import type { Brique, ConfigurationOffre } from "../api/types";
import { LIBELLE_BRIQUE } from "../api/types";

const TOUTES_BRIQUES: Brique[] = ["DL", "HM", "OM", "ASSURANCE"];

function aujourdHui(): string {
  return new Date().toISOString().slice(0, 10);
}

interface Props {
  enCours: boolean;
  onChiffrer: (config: ConfigurationOffre) => void;
}

export function ConfigurateurForm({ enCours, onChiffrer }: Props) {
  const [clientCode, setClientCode] = useState("CLIENTOK");
  const [serieCode, setSerieCode] = useState("VECTRON");
  const [locomotiveNumero, setLocomotiveNumero] = useState("");
  const [ageDebutAns, setAgeDebutAns] = useState("5");
  const [kmCumulesDebut, setKmCumulesDebut] = useState("600000");
  const [hm8Realisee, setHm8Realisee] = useState(false);
  const [hm16Realisee, setHm16Realisee] = useState(false);
  const [kmAnnuel, setKmAnnuel] = useState("120000");
  const [dureeMois, setDureeMois] = useState("24");
  const [quantite, setQuantite] = useState("1");
  const [dateDebut, setDateDebut] = useState(aujourdHui());
  const [campagne, setCampagne] = useState(false);
  const [briquesIncluses, setBriquesIncluses] = useState<Set<Brique>>(
    new Set(TOUTES_BRIQUES),
  );
  const [prixNegocies, setPrixNegocies] = useState<Partial<Record<Brique, string>>>({});

  const aLocomotive = locomotiveNumero.trim().length > 0;

  function basculerBrique(brique: Brique) {
    setBriquesIncluses((courant) => {
      const suivant = new Set(courant);
      if (suivant.has(brique)) {
        suivant.delete(brique);
      } else {
        suivant.add(brique);
      }
      return suivant;
    });
  }

  function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();

    const negocies: Partial<Record<Brique, number>> = {};
    for (const brique of TOUTES_BRIQUES) {
      const valeur = prixNegocies[brique];
      if (valeur !== undefined && valeur.trim() !== "") {
        negocies[brique] = Number(valeur);
      }
    }

    const config: ConfigurationOffre = {
      client_code: clientCode.trim(),
      serie_code: serieCode.trim(),
      locomotive_numero: aLocomotive ? locomotiveNumero.trim() : null,
      km_annuel: Number(kmAnnuel),
      duree_mois: Number(dureeMois),
      quantite: Number(quantite),
      date_debut: dateDebut,
      briques_incluses: Array.from(briquesIncluses),
      prix_negocies: negocies,
      campagne,
      ...(aLocomotive
        ? {}
        : {
            age_debut_ans: Number(ageDebutAns),
            km_cumules_debut: Number(kmCumulesDebut),
            hm_8_realisee: hm8Realisee,
            hm_16_realisee: hm16Realisee,
          }),
    };

    onChiffrer(config);
  }

  return (
    <form className="configurateur-form" onSubmit={soumettre}>
      <fieldset>
        <legend>Client et série</legend>

        <label>
          Client
          <input
            value={clientCode}
            onChange={(e) => setClientCode(e.target.value)}
            placeholder="ex. CLIENTOK"
            required
          />
        </label>

        <label>
          Série
          <input
            value={serieCode}
            onChange={(e) => setSerieCode(e.target.value)}
            placeholder="ex. VECTRON"
            required
          />
        </label>

        <label>
          Locomotive de la flotte (optionnel)
          <input
            value={locomotiveNumero}
            onChange={(e) => setLocomotiveNumero(e.target.value)}
            placeholder="numéro, ou laisser vide"
          />
        </label>

        {!aLocomotive && (
          <div className="sous-champs">
            <p className="aide">
              Sans locomotive affectée : âge et kilométrage de départ saisis à la main.
            </p>
            <label>
              Âge au début (années)
              <input
                type="number"
                step="0.1"
                min="0"
                value={ageDebutAns}
                onChange={(e) => setAgeDebutAns(e.target.value)}
                required
              />
            </label>
            <label>
              Km cumulés au début
              <input
                type="number"
                min="0"
                value={kmCumulesDebut}
                onChange={(e) => setKmCumulesDebut(e.target.value)}
                required
              />
            </label>
            <label className="case-a-cocher">
              <input
                type="checkbox"
                checked={hm8Realisee}
                onChange={(e) => setHm8Realisee(e.target.checked)}
              />
              HM 8 ans déjà réalisée
            </label>
            <label className="case-a-cocher">
              <input
                type="checkbox"
                checked={hm16Realisee}
                onChange={(e) => setHm16Realisee(e.target.checked)}
              />
              HM 16 ans déjà réalisée
            </label>
          </div>
        )}
      </fieldset>

      <fieldset>
        <legend>Configuration</legend>

        <label>
          Kilométrage annuel
          <input
            type="number"
            min="80000"
            max="200000"
            step="1000"
            value={kmAnnuel}
            onChange={(e) => setKmAnnuel(e.target.value)}
            required
          />
        </label>

        <label>
          Durée (mois)
          <input
            type="number"
            min="1"
            value={dureeMois}
            onChange={(e) => setDureeMois(e.target.value)}
            required
          />
        </label>

        <label>
          Quantité (nombre de locos)
          <input
            type="number"
            min="1"
            value={quantite}
            onChange={(e) => setQuantite(e.target.value)}
            required
          />
        </label>

        <label>
          Date de début
          <input
            type="date"
            value={dateDebut}
            onChange={(e) => setDateDebut(e.target.value)}
            required
          />
        </label>

        <label className="case-a-cocher">
          <input
            type="checkbox"
            checked={campagne}
            onChange={(e) => setCampagne(e.target.checked)}
          />
          Offre rattachée à une campagne commerciale
        </label>
      </fieldset>

      <fieldset>
        <legend>Briques incluses</legend>
        <div className="briques-incluses">
          {TOUTES_BRIQUES.map((brique) => (
            <label key={brique} className="case-a-cocher">
              <input
                type="checkbox"
                checked={briquesIncluses.has(brique)}
                onChange={() => basculerBrique(brique)}
              />
              {LIBELLE_BRIQUE[brique]}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Prix négociés (optionnel — vide = prix catalogue)</legend>
        <div className="prix-negocies">
          {TOUTES_BRIQUES.map((brique) => (
            <label key={brique}>
              {LIBELLE_BRIQUE[brique]}
              <input
                type="number"
                min="0"
                step="0.01"
                value={prixNegocies[brique] ?? ""}
                onChange={(e) =>
                  setPrixNegocies((courant) => ({ ...courant, [brique]: e.target.value }))
                }
                disabled={!briquesIncluses.has(brique)}
                placeholder="catalogue"
              />
            </label>
          ))}
        </div>
      </fieldset>

      <button type="submit" disabled={enCours}>
        {enCours ? "Calcul en cours…" : "Chiffrer"}
      </button>
    </form>
  );
}
