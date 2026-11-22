import { useEffect, useState } from "react";
import { ApiError, obtenirJournalReferentiel, obtenirVersionPubliee } from "../api/client";
import type { JournalEntryApi, VersionPublieeApi } from "../api/types";

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function VueReferentiel() {
  const [version, setVersion] = useState<VersionPublieeApi | null>(null);
  const [journal, setJournal] = useState<JournalEntryApi[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const [v, j] = await Promise.all([obtenirVersionPubliee(), obtenirJournalReferentiel()]);
      setVersion(v);
      setJournal(j.sort((a, b) => b.horodatage.localeCompare(a.horodatage)));
    } catch (e) {
      const message = e instanceof ApiError ? `${e.status} : ${e.message}` : "Impossible de joindre l'API.";
      setErreur(message);
    } finally {
      setEnCours(false);
    }
  }

  useEffect(() => {
    void rafraichir();
  }, []);

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <h2>Référentiel publié</h2>
          <p className="registre-sous-titre">
            M1 : la version active sur laquelle le moteur chiffre, et son journal complet (qui, quand, pourquoi).
          </p>
        </div>
        <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
          {enCours ? "Chargement…" : "Rafraîchir"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      <div className="cartes-kpi">
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{version ? `v${version.numero}` : "—"}</div>
          <div className="carte-kpi-libelle">Version active</div>
          {version && <div className="carte-kpi-detail">publiée le {formaterDate(version.date_publication)}</div>}
          {version && <div className="carte-kpi-detail">par {version.publie_par}</div>}
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{version?.nb_series ?? "—"}</div>
          <div className="carte-kpi-libelle">Séries catalogue</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{version?.nb_clients ?? "—"}</div>
          <div className="carte-kpi-libelle">Clients référencés</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{version?.nb_locomotives ?? "—"}</div>
          <div className="carte-kpi-libelle">Locomotives en flotte</div>
        </div>
      </div>

      <h3 className="sous-titre-journal">Journal des modifications</h3>
      {journal.length === 0 ? (
        <p className="registre-vide">Aucune entrée dans le journal.</p>
      ) : (
        <table className="registre-table">
          <thead>
            <tr>
              <th>Horodatage</th>
              <th>Version</th>
              <th>Utilisateur</th>
              <th>Table</th>
              <th>Action</th>
              <th>Raison</th>
              <th>Validé par</th>
            </tr>
          </thead>
          <tbody>
            {journal.map((e, i) => (
              <tr key={`${e.horodatage}-${i}`}>
                <td className="mono">{formaterDate(e.horodatage)}</td>
                <td className="num">v{e.version_numero}</td>
                <td>{e.utilisateur}</td>
                <td className="mono">{e.table}</td>
                <td className="mono">{e.action}</td>
                <td>{e.raison}</td>
                <td>{e.valide_par ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
