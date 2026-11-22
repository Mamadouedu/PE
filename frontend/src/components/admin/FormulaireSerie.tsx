import { useState } from "react";
import type { SerieApi } from "../../api/types";
import { PanneauDetail } from "../PanneauDetail";

interface Props {
  initial: SerieApi | null;
  onSauver: (s: SerieApi) => void;
  onAnnuler: () => void;
}

const VIDE: SerieApi = {
  code: "",
  valeur_neuve: 2_000_000,
  duree_vie_ans: 30,
  vr_fin_vie_taux: 0.10,
  km_reference_annuel: 120_000,
  cout_hm_8_ans: 150_000,
  cout_hm_16_ans: 200_000,
  om_fixe: 6_000,
  om_variable_eur_par_km: 0.05,
  taux_assurance_annuel: 0.03,
};

export function FormulaireSerie({ initial, onSauver, onAnnuler }: Props) {
  const [s, setS] = useState<SerieApi>(initial ?? VIDE);

  function maj<K extends keyof SerieApi>(champ: K, valeur: SerieApi[K]) {
    setS((prev) => ({ ...prev, [champ]: valeur }));
  }

  return (
    <PanneauDetail
      titre={initial ? `Modifier la série ${initial.code}` : "Nouvelle série"}
      onFermer={onAnnuler}
    >
      <form
        className="form-admin"
        onSubmit={(e) => {
          e.preventDefault();
          onSauver(s);
        }}
      >
        <label>
          Code (ex. VECTRON)
          <input
            type="text"
            value={s.code}
            disabled={!!initial}
            onChange={(e) => maj("code", e.target.value.toUpperCase())}
            required
            maxLength={30}
          />
        </label>
        <label>
          Valeur neuve (€)
          <input type="number" value={s.valeur_neuve} min={0} onChange={(e) => maj("valeur_neuve", Number(e.target.value))} required />
        </label>
        <label>
          Durée de vie (années)
          <input type="number" value={s.duree_vie_ans} min={1} onChange={(e) => maj("duree_vie_ans", Number(e.target.value))} required />
        </label>
        <label>
          VR fin de vie (taux, ex. 0.10)
          <input type="number" value={s.vr_fin_vie_taux} step="0.01" min={0} max={1} onChange={(e) => maj("vr_fin_vie_taux", Number(e.target.value))} required />
        </label>
        <label>
          Km référence / an
          <input type="number" value={s.km_reference_annuel} min={0} onChange={(e) => maj("km_reference_annuel", Number(e.target.value))} required />
        </label>
        <label>
          Coût HM à 8 ans (€)
          <input type="number" value={s.cout_hm_8_ans} min={0} onChange={(e) => maj("cout_hm_8_ans", Number(e.target.value))} required />
        </label>
        <label>
          Coût HM à 16 ans (€)
          <input type="number" value={s.cout_hm_16_ans} min={0} onChange={(e) => maj("cout_hm_16_ans", Number(e.target.value))} required />
        </label>
        <label>
          OM fixe mensuel (€)
          <input type="number" value={s.om_fixe} min={0} onChange={(e) => maj("om_fixe", Number(e.target.value))} required />
        </label>
        <label>
          OM variable (€/km)
          <input type="number" value={s.om_variable_eur_par_km} step="0.001" min={0} onChange={(e) => maj("om_variable_eur_par_km", Number(e.target.value))} required />
        </label>
        <label>
          Taux assurance annuel (ex. 0.03)
          <input type="number" value={s.taux_assurance_annuel} step="0.001" min={0} max={1} onChange={(e) => maj("taux_assurance_annuel", Number(e.target.value))} required />
        </label>

        <div className="form-actions">
          <button type="button" className="bouton-secondaire" onClick={onAnnuler}>Annuler</button>
          <button type="submit" className="bouton-principal">Enregistrer</button>
        </div>
      </form>
    </PanneauDetail>
  );
}
