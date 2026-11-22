import { useRef, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type TypeImport = "dry-lease-grille" | "budget-plan" | "flotte";

interface ResultatImport {
  nb_lignes_lues: number;
  nb_lignes_importees: number;
  nb_tranches_km_deduites?: number;
  erreurs: string[];
}

interface Props {
  type: TypeImport;
  brouillonNumero: number;
  emailKam: string;
  onImporte: () => void;
}

const TITRE: Record<TypeImport, string> = {
  "dry-lease-grille": "Grille Dry lease",
  "budget-plan": "Budget Plan (HM + OM)",
  "flotte": "Flotte",
};

const COLONNES_ATTENDUES: Record<TypeImport, string> = {
  "dry-lease-grille": "serie_code, duree_min_mois, duree_max_mois, loyer_mensuel",
  "budget-plan": "serie_code, km_min, km_max, bp_hm, bp_om, exercice",
  "flotte": "numero, produit, sous_serie, serie_code, homologations, mise_en_service, km_cumules, statut",
};

const EXEMPLE: Record<TypeImport, string> = {
  "dry-lease-grille": "VECTRON,12,36,20000",
  "budget-plan": "VECTRON,120000,139999,2000,1500,2026",
  "flotte": 'BR186-101,TRAXX,DC2,TRAXX,"PL;DE;AT",2021-01-15,650000,disponible',
};

export function ImportCSV({ type, brouillonNumero, emailKam, onImporte }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [resultat, setResultat] = useState<ResultatImport | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [remplacer, setRemplacer] = useState(false);

  async function importer(fichier: File) {
    if (!emailKam) {
      setErreur("Renseigne ton e-mail en haut de page avant d'importer.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    setResultat(null);
    try {
      const formData = new FormData();
      formData.append("fichier", fichier);
      const qs = type === "flotte" && remplacer ? "?remplacer=true" : "";
      const r = await fetch(
        `${BASE_URL}/api/v1/referentiel/brouillons/${brouillonNumero}/import/${type}${qs}`,
        { method: "POST", headers: { "X-Utilisateur": emailKam }, body: formData },
      );
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`HTTP ${r.status} : ${txt}`);
      }
      const res = (await r.json()) as ResultatImport;
      setResultat(res);
      if (res.nb_lignes_importees > 0) onImporte();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "Erreur d'import");
    } finally {
      setEnCours(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="import-csv">
      <div className="import-csv-ligne">
        <strong>Import {TITRE[type]}</strong>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importer(f);
          }}
          disabled={enCours}
        />
        {type === "flotte" && (
          <label className="import-csv-checkbox">
            <input type="checkbox" checked={remplacer} onChange={(e) => setRemplacer(e.target.checked)} />
            Remplacer toute la flotte
          </label>
        )}
      </div>
      <p className="import-csv-aide">
        Colonnes attendues : <code>{COLONNES_ATTENDUES[type]}</code>
        <br />Exemple de ligne : <code>{EXEMPLE[type]}</code>
      </p>

      {enCours && <p className="import-csv-statut">Import en cours…</p>}
      {erreur && <div className="erreur">{erreur}</div>}
      {resultat && (
        <div className={`import-csv-resultat ${resultat.erreurs.length > 0 ? "import-csv-mixte" : "import-csv-ok"}`}>
          <strong>
            {resultat.nb_lignes_importees} / {resultat.nb_lignes_lues} lignes importées
          </strong>
          {resultat.nb_tranches_km_deduites !== undefined && (
            <> · {resultat.nb_tranches_km_deduites} tranches de km déduites</>
          )}
          {resultat.erreurs.length > 0 && (
            <ul className="import-csv-erreurs">
              {resultat.erreurs.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
