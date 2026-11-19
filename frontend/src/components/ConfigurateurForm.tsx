import { useEffect, useState } from "react";
import { listerCampagnes, listerModeles } from "../api/client";
import type { CalculateQuoteRequest, CampaignResponse, ModelSummaryResponse, PriceLine } from "../api/types";
import { LIBELLE_PRICE_LINE } from "../api/types";

const TOUTES_LIGNES: PriceLine[] = ["DryLease", "HeavyMaintenance", "OperatingMaintenance", "Insurance"];

function aujourdHui(): string {
  return new Date().toISOString().slice(0, 10);
}

interface Props {
  enCours: boolean;
  onChiffrer: (requete: CalculateQuoteRequest) => void;
}

export function ConfigurateurForm({ enCours, onChiffrer }: Props) {
  const [modeles, setModeles] = useState<ModelSummaryResponse[]>([]);
  const [campagnes, setCampagnes] = useState<CampaignResponse[]>([]);
  const [chargementReferentiel, setChargementReferentiel] = useState(true);

  const [customerCode, setCustomerCode] = useState("CLIENTOK");
  const [modelCode, setModelCode] = useState("");
  const [ageDebutAns, setAgeDebutAns] = useState("5");
  const [kmCumulesDebut, setKmCumulesDebut] = useState("600000");
  const [hm8Realisee, setHm8Realisee] = useState(false);
  const [hm16Realisee, setHm16Realisee] = useState(false);
  const [kmAnnuel, setKmAnnuel] = useState("120000");
  const [dureeMois, setDureeMois] = useState("24");
  const [quantite, setQuantite] = useState("1");
  const [dateDebut, setDateDebut] = useState(aujourdHui());
  const [campagneCode, setCampagneCode] = useState("");
  const [lignesIncluses, setLignesIncluses] = useState<Set<PriceLine>>(new Set(TOUTES_LIGNES));
  const [prixNegocies, setPrixNegocies] = useState<Partial<Record<PriceLine, string>>>({});

  useEffect(() => {
    let annule = false;
    Promise.all([listerModeles(), listerCampagnes()])
      .then(([listeModeles, listeCampagnes]) => {
        if (annule) return;
        setModeles(listeModeles);
        setCampagnes(listeCampagnes);
        if (listeModeles.length > 0) setModelCode(listeModeles[0].modelCode);
      })
      .finally(() => {
        if (!annule) setChargementReferentiel(false);
      });
    return () => {
      annule = true;
    };
  }, []);

  function basculerLigne(ligne: PriceLine) {
    setLignesIncluses((courant) => {
      const suivant = new Set(courant);
      if (suivant.has(ligne)) {
        suivant.delete(ligne);
      } else {
        suivant.add(ligne);
      }
      return suivant;
    });
  }

  function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();

    const negocies: Partial<Record<PriceLine, number>> = {};
    for (const ligne of TOUTES_LIGNES) {
      const valeur = prixNegocies[ligne];
      if (valeur !== undefined && valeur.trim() !== "") {
        negocies[ligne] = Number(valeur);
      }
    }

    const requete: CalculateQuoteRequest = {
      customerCode: customerCode.trim(),
      modelCode,
      annualMileageKm: Number(kmAnnuel),
      durationMonths: Number(dureeMois),
      quantity: Number(quantite),
      startDate: dateDebut,
      ageAtStartYears: Number(ageDebutAns),
      cumulativeMileageAtStartKm: Number(kmCumulesDebut),
      heavyMaintenance8Done: hm8Realisee,
      heavyMaintenance16Done: hm16Realisee,
      includedLines: Array.from(lignesIncluses),
      negotiatedPrices: negocies,
      campaignCode: campagneCode.trim() === "" ? null : campagneCode,
    };

    onChiffrer(requete);
  }

  return (
    <form className="configurateur-form" onSubmit={soumettre}>
      <fieldset>
        <legend>Client et modèle</legend>

        <label>
          Client
          <input
            value={customerCode}
            onChange={(e) => setCustomerCode(e.target.value)}
            placeholder="ex. CLIENTOK"
            required
          />
        </label>

        <label>
          Modèle
          {modeles.length > 0 ? (
            <select value={modelCode} onChange={(e) => setModelCode(e.target.value)} required>
              {modeles.map((m) => (
                <option key={m.modelCode} value={m.modelCode}>
                  {m.name} ({m.modelCode})
                </option>
              ))}
            </select>
          ) : (
            <input
              value={modelCode}
              onChange={(e) => setModelCode(e.target.value)}
              placeholder="ex. VECTRON"
              disabled={chargementReferentiel}
              required
            />
          )}
        </label>

        <div className="sous-champs">
          <p className="aide">Âge et kilométrage de départ (saisis à la main).</p>
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

        <label>
          Campagne commerciale (optionnel)
          <select value={campagneCode} onChange={(e) => setCampagneCode(e.target.value)}>
            <option value="">Aucune</option>
            {campagnes.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </label>
      </fieldset>

      <fieldset>
        <legend>Briques incluses</legend>
        <div className="briques-incluses">
          {TOUTES_LIGNES.map((ligne) => (
            <label key={ligne} className="case-a-cocher">
              <input
                type="checkbox"
                checked={lignesIncluses.has(ligne)}
                onChange={() => basculerLigne(ligne)}
              />
              {LIBELLE_PRICE_LINE[ligne]}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Prix négociés (optionnel — vide = prix catalogue)</legend>
        <div className="prix-negocies">
          {TOUTES_LIGNES.map((ligne) => (
            <label key={ligne}>
              {LIBELLE_PRICE_LINE[ligne]}
              <input
                type="number"
                min="0"
                step="0.01"
                value={prixNegocies[ligne] ?? ""}
                onChange={(e) =>
                  setPrixNegocies((courant) => ({ ...courant, [ligne]: e.target.value }))
                }
                disabled={!lignesIncluses.has(ligne)}
                placeholder="catalogue"
              />
            </label>
          ))}
        </div>
      </fieldset>

      <button type="submit" disabled={enCours || chargementReferentiel || !modelCode}>
        {enCours ? "Calcul en cours…" : "Chiffrer"}
      </button>
    </form>
  );
}
