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

const PRODUITS_COURANTS = ["TRAXX", "VECTRON", "EURODUAL", "SMARTRON"];
const SOUS_SERIES_PAR_PRODUIT: Record<string, string[]> = {
  TRAXX: ["DC2", "DC3", "AC3", "MS2", "MS3", "P160", "P200", "F140"],
  VECTRON: ["AC", "DC", "MS", "DE"],
  EURODUAL: ["BiMode"],
  SMARTRON: ["AC"],
};
const PAYS_HOMOLOGATION = [
  { code: "DE", nom: "Allemagne" },
  { code: "AT", nom: "Autriche" },
  { code: "BE", nom: "Belgique" },
  { code: "BG", nom: "Bulgarie" },
  { code: "HR", nom: "Croatie" },
  { code: "DK", nom: "Danemark" },
  { code: "ES", nom: "Espagne" },
  { code: "FI", nom: "Finlande" },
  { code: "FR", nom: "France" },
  { code: "GR", nom: "Grèce" },
  { code: "HU", nom: "Hongrie" },
  { code: "IT", nom: "Italie" },
  { code: "LU", nom: "Luxembourg" },
  { code: "NL", nom: "Pays-Bas" },
  { code: "NO", nom: "Norvège" },
  { code: "PL", nom: "Pologne" },
  { code: "PT", nom: "Portugal" },
  { code: "CZ", nom: "République tchèque" },
  { code: "RO", nom: "Roumanie" },
  { code: "UK", nom: "Royaume-Uni" },
  { code: "SK", nom: "Slovaquie" },
  { code: "SI", nom: "Slovénie" },
  { code: "SE", nom: "Suède" },
  { code: "CH", nom: "Suisse" },
];

const VIDE: LocomotiveApi = {
  numero: "",
  serie_code: "",
  mise_en_service: new Date().toISOString().slice(0, 10),
  km_cumules: 0,
  statut: "disponible",
  produit: "",
  sous_serie: "",
  homologations: [],
};

export function FormulaireLocomotive({ initial, seriesDisponibles, onSauver, onAnnuler }: Props) {
  const [l, setL] = useState<LocomotiveApi>(
    initial ?? { ...VIDE, serie_code: seriesDisponibles[0] ?? "" }
  );

  function maj<K extends keyof LocomotiveApi>(champ: K, valeur: LocomotiveApi[K]) {
    setL((prev) => ({ ...prev, [champ]: valeur }));
  }

  function toggleHomologation(code: string) {
    const actuelles = l.homologations ?? [];
    if (actuelles.includes(code)) {
      maj("homologations", actuelles.filter((c) => c !== code));
    } else {
      maj("homologations", [...actuelles, code]);
    }
  }

  const sousSeries = SOUS_SERIES_PAR_PRODUIT[l.produit ?? ""] ?? [];

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
          Numéro de série (immatriculation)
          <input
            type="text"
            value={l.numero}
            disabled={!!initial}
            onChange={(e) => maj("numero", e.target.value.toUpperCase())}
            required
            maxLength={30}
            placeholder="ex. BR186-101, 193-901"
          />
        </label>

        <label>
          Produit (gamme constructeur)
          <input
            list="produits-list"
            value={l.produit ?? ""}
            onChange={(e) => maj("produit", e.target.value.toUpperCase())}
            placeholder="ex. TRAXX, VECTRON"
          />
          <datalist id="produits-list">
            {PRODUITS_COURANTS.map((p) => <option key={p} value={p} />)}
          </datalist>
        </label>

        <label>
          Sous-série (variante technique)
          <input
            list="sous-series-list"
            value={l.sous_serie ?? ""}
            onChange={(e) => maj("sous_serie", e.target.value.toUpperCase())}
            placeholder="ex. DC2, DC3, MS2"
          />
          <datalist id="sous-series-list">
            {sousSeries.map((s) => <option key={s} value={s} />)}
          </datalist>
        </label>

        <label>
          Série catalogue (pour le pricing)
          <select value={l.serie_code} onChange={(e) => maj("serie_code", e.target.value)} required>
            <option value="">— Choisir —</option>
            {seriesDisponibles.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        <div>
          <label style={{ marginBottom: 6 }}>
            Homologations
            <span style={{ fontSize: 11, color: "var(--fg-muted)", marginLeft: 8 }}>
              ({(l.homologations ?? []).length} pays sélectionné{(l.homologations ?? []).length > 1 ? "s" : ""})
            </span>
          </label>
          <div className="pays-grille">
            {PAYS_HOMOLOGATION.map((p) => {
              const actif = (l.homologations ?? []).includes(p.code);
              return (
                <button
                  key={p.code}
                  type="button"
                  className={`pastille-pays ${actif ? "pastille-pays-actif" : ""}`}
                  onClick={() => toggleHomologation(p.code)}
                  title={p.nom}
                >
                  {p.code}
                </button>
              );
            })}
          </div>
        </div>

        <label>
          Mise en service
          <input
            type="date"
            value={l.mise_en_service}
            onChange={(e) => maj("mise_en_service", e.target.value)}
            required
          />
        </label>

        <label>
          Km cumulés
          <input
            type="number"
            value={l.km_cumules}
            min={0}
            onChange={(e) => maj("km_cumules", Number(e.target.value))}
            required
          />
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
