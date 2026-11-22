import { useState } from "react";
import type { ClientRefApi } from "../../api/types";
import { PanneauDetail } from "../PanneauDetail";

interface Props {
  initial: ClientRefApi | null;
  onSauver: (c: ClientRefApi) => void;
  onAnnuler: () => void;
}

const VIDE: ClientRefApi = {
  code: "",
  nom: "",
  rating: 5,
  paiement_avance: false,
  cash_deposit: 0,
};

export function FormulaireClient({ initial, onSauver, onAnnuler }: Props) {
  const [c, setC] = useState<ClientRefApi>(initial ?? VIDE);

  function maj<K extends keyof ClientRefApi>(champ: K, valeur: ClientRefApi[K]) {
    setC((prev) => ({ ...prev, [champ]: valeur }));
  }

  return (
    <PanneauDetail
      titre={initial ? `Modifier le client ${initial.code}` : "Nouveau client"}
      onFermer={onAnnuler}
    >
      <form
        className="form-admin"
        onSubmit={(e) => {
          e.preventDefault();
          onSauver(c);
        }}
      >
        <label>
          Code client
          <input type="text" value={c.code} disabled={!!initial} onChange={(e) => maj("code", e.target.value.toUpperCase())} required maxLength={30} />
        </label>
        <label>
          Nom
          <input type="text" value={c.nom} onChange={(e) => maj("nom", e.target.value)} required />
        </label>
        <label>
          Rating financier (1 à 10)
          <input type="number" value={c.rating} min={1} max={10} onChange={(e) => maj("rating", Number(e.target.value))} required />
        </label>
        <label className="checkbox-ligne">
          <input type="checkbox" checked={c.paiement_avance ?? false} onChange={(e) => maj("paiement_avance", e.target.checked)} />
          Paiement d'avance
        </label>
        <label>
          Cash deposit (€)
          <input type="number" value={c.cash_deposit ?? 0} min={0} onChange={(e) => maj("cash_deposit", Number(e.target.value))} />
        </label>
        <p className="form-aide">
          Un rating &gt; 7 impose durée courte + paiement d'avance (contrôle C3 du moteur).
        </p>

        <div className="form-actions">
          <button type="button" className="bouton-secondaire" onClick={onAnnuler}>Annuler</button>
          <button type="submit" className="bouton-principal">Enregistrer</button>
        </div>
      </form>
    </PanneauDetail>
  );
}
