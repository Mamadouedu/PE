import { useState } from "react";
import type { LocomotiveApi, StatutLocomotive } from "../../api/types";
import { PanneauDetail } from "../PanneauDetail";

interface Props {
  initial: LocomotiveApi | null;
  seriesDisponibles: string[];
  onSauver: (l: LocomotiveApi) => void;
  onAnnuler: () => void;
}

const STATUTS: { v: StatutLocomotive; l: string }[] = [
  { v: "disponible", l: "Disponible" },
  { v: "allouee", l: "Allouée" },
  { v: "maintenance", l: "Maintenance" },
  { v: "reformee", l: "Réformée" },
];

const VIDE: LocomotiveApi = {
  numero: "",
  serie_code: "",
  mise_en_service: new Date().toISOString().slice(0, 10),
  km_cumules: 0,
  statut: "disponible",
};

export function FormulaireLocomotive({ initial, seriesDisponibles, onSauver, onAnnuler }: Props) {
  const [l, setL] = useState<LocomotiveApi>(initial ?? { ...VIDE, serie_code: seriesDisponibles[0] ?? "" });

  function maj<K extends keyof LocomotiveApi>(champ: K, valeur: LocomotiveApi[K]) {
    setL((prev) => ({ ...prev, [champ]: valeur }));
  }

  return (
    <PanneauDetail
      titre={initial ? `Modifier la locomotive ${initial.numero}` : "Nouvelle locomotive"}
      onFermer={onAnnuler}
    >
      <form
        className="form-admin"
        onSubmit={(e) => {
          e.preventDefault();
          onSauver(l);
        }}
      >
        <label>
          Numéro
          <input type="text" value={l.numero} disabled={!!initial} onChange={(e) => maj("numero", e.target.value.toUpperCase())} required maxLength={30} />
        </label>
        <label>
          Série
          <select value={l.serie_code} onChange={(e) => maj("serie_code", e.target.value)} required>
            <option value="">— Choisir —</option>
            {seriesDisponibles.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Mise en service
          <input type="date" value={l.mise_en_service} onChange={(e) => maj("mise_en_service", e.target.value)} required />
        </label>
        <label>
          Km cumulés
          <input type="number" value={l.km_cumules} min={0} onChange={(e) => maj("km_cumules", Number(e.target.value))} required />
        </label>
        <label>
          Statut
          <select value={l.statut} onChange={(e) => maj("statut", e.target.value as StatutLocomotive)} required>
            {STATUTS.map((s) => (
              <option key={s.v} value={s.v}>{s.l}</option>
            ))}
          </select>
        </label>

        <div className="form-actions">
          <button type="button" className="bouton-secondaire" onClick={onAnnuler}>Annuler</button>
          <button type="submit" className="bouton-principal">Enregistrer</button>
        </div>
      </form>
    </PanneauDetail>
  );
}
