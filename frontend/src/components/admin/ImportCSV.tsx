import { useRef, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

interface ResultatImport {
  type_detecte: "dry-lease-grille" | "budget-plan" | "flotte" | null;
  nb_lignes_lues: number;
  nb_lignes_importees: number;
  nb_tranches_km_deduites?: number;
  erreurs: string[];
}

interface Props {
  brouillonNumero: number;
  emailKam: string;
  onImporte: () => void;
}

const LIBELLE_TYPE: Record<string, string> = {
  "dry-lease-grille": "Grille Dry lease",
  "budget-plan": "Budget Plan (HM + OM)",
  "flotte": "Flotte",
};

export function ImportCSV({ brouillonNumero, emailKam, onImporte }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [resultat, setResultat] = useState<ResultatImport | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [remplacerFlotte, setRemplacerFlotte] = useState(false);
  const [nomFichier, setNomFichier] = useState<string | null>(null);

  async function importer(fichier: File) {
    if (!emailKam) {
      setErreur("Renseigne ton e-mail en haut de page avant d'importer.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    setResultat(null);
    setNomFichier(fichier.name);
    try {
      const formData = new FormData();
      formData.append("fichier", fichier);
      const qs = remplacerFlotte ? "?remplacer=true" : "";
      const r = await fetch(
        `${BASE_URL}/api/v1/referentiel/brouillons/${brouillonNumero}/import/auto${qs}`,
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
      <h3 style={{ marginBottom: 12, fontSize: 15 }}>Import CSV automatique</h3>
      <p className="registre-sous-titre" style={{ marginBottom: 14 }}>
        Dépose un CSV — la plateforme reconnaît automatiquement s'il s'agit de la grille Dry lease, du Budget Plan ou de la flotte, d'après ses colonnes.
      </p>

      <div className="import-csv-ligne">
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
        <label className="import-csv-checkbox">
          <input type="checkbox" checked={remplacerFlotte} onChange={(e) => setRemplacerFlotte(e.target.checked)} />
          Remplacer toute la flotte (si CSV flotte)
        </label>
      </div>

      <details className="import-csv-help">
        <summary>Colonnes reconnues et astuces Excel</summary>
        <table className="import-csv-help-table">
          <thead>
            <tr><th>Type détecté quand on voit…</th><th>Colonnes complètes attendues</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Grille Dry lease</strong><br/><code>serie_code</code>, <code>duree_min_mois</code>, <code>loyer_mensuel</code></td>
              <td><code>serie_code, duree_min_mois, duree_max_mois, loyer_mensuel</code></td>
            </tr>
            <tr>
              <td><strong>Budget Plan</strong><br/><code>serie_code</code>, <code>bp_hm</code>, <code>bp_om</code></td>
              <td><code>serie_code, km_min, km_max, bp_hm, bp_om, exercice</code></td>
            </tr>
            <tr>
              <td><strong>Flotte</strong><br/><code>numero</code>, <code>produit</code>, <code>homologations</code></td>
              <td><code>numero, produit, sous_serie, serie_code, homologations, mise_en_service, km_cumules, statut</code></td>
            </tr>
          </tbody>
        </table>
        <ul className="import-csv-help-list">
          <li>Encodage <strong>UTF-8</strong>. Excel ajoute un BOM : accepté sans problème.</li>
          <li>Séparateur <strong><code>,</code> ou <code>;</code></strong> — le platform détecte automatiquement. Excel en français sauve en <code>;</code> par défaut.</li>
          <li>Séparateur décimal <code>.</code> ou <code>,</code> — les deux marchent (<code>1800,5</code> = <code>1800.5</code>).</li>
          <li>Pour la flotte, les <strong>homologations</strong> vont dans une seule cellule séparées par <code>;</code> : <code>PL;DE;AT</code>.</li>
          <li>Les dates doivent être au format <code>YYYY-MM-DD</code> (Excel : « Format de cellule → Personnalisée → aaaa-mm-jj »).</li>
          <li>Depuis Excel : <code>Fichier → Enregistrer sous → CSV UTF-8 (délimité par séparateur de liste)</code>.</li>
        </ul>
      </details>

      {nomFichier && !enCours && (
        <p className="import-csv-statut" style={{ color: "var(--fg-muted)", fontSize: 12 }}>Fichier : {nomFichier}</p>
      )}

      {enCours && <p className="import-csv-statut">Analyse et import en cours…</p>}
      {erreur && <div className="erreur">{erreur}</div>}

      {resultat && (
        <div className={`import-csv-resultat ${resultat.type_detecte === null ? "erreur" : resultat.erreurs.length > 0 ? "import-csv-mixte" : "import-csv-ok"}`}>
          {resultat.type_detecte === null ? (
            <div>
              <strong>Type de CSV non reconnu.</strong>
              <br />
              Vérifie que ton en-tête contient au moins les colonnes de l'un des 3 types listés plus haut.
            </div>
          ) : (
            <>
              <strong>
                ✓ Type détecté : {LIBELLE_TYPE[resultat.type_detecte]}
              </strong>
              <br />
              {resultat.nb_lignes_importees} / {resultat.nb_lignes_lues} lignes importées
              {resultat.nb_tranches_km_deduites !== undefined && (
                <> · {resultat.nb_tranches_km_deduites} tranches de km déduites</>
              )}
              {resultat.erreurs.length > 0 && (
                <ul className="import-csv-erreurs">
                  {resultat.erreurs.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
