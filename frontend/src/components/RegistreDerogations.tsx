import { useEffect, useState } from "react";
import { ApiError, listerDerogations } from "../api/client";
import type { DerogationApi, StatutDerogation } from "../api/types";

const LIBELLE_STATUT: Record<StatutDerogation, string> = {
  en_attente: "En attente",
  approuvee: "Approuvée",
  rejetee: "Rejetée",
};

function formaterDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formaterMontant(n: number): string {
  return n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

export function RegistreDerogations() {
  const [derogations, setDerogations] = useState<DerogationApi[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const data = await listerDerogations();
      setDerogations(data.sort((a, b) => b.id - a.id));
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
          <h2>Registre central des dérogations</h2>
          <p className="registre-sous-titre">
            M4-05 : chaque demande hors règles est tracée ici — niveau et validateur recalculés côté serveur.
          </p>
        </div>
        <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
          {enCours ? "Chargement…" : "Rafraîchir"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {derogations && derogations.length === 0 && (
        <p className="registre-vide">Aucune dérogation enregistrée pour l'instant.</p>
      )}

      {derogations && derogations.length > 0 && (
        <table className="registre-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Demandeur</th>
              <th>Client</th>
              <th>Série</th>
              <th>Niveau</th>
              <th>Montant / mois</th>
              <th>Statut</th>
              <th>Validateur</th>
              <th>Justification</th>
            </tr>
          </thead>
          <tbody>
            {derogations.map((d) => (
              <tr key={d.id}>
                <td>#{d.id}</td>
                <td>{formaterDate(d.date_demande)}</td>
                <td>{d.demandeur}</td>
                <td>{d.client_code}</td>
                <td>{d.serie_code}</td>
                <td>N{d.niveau}</td>
                <td className="num">{formaterMontant(d.montant_mensuel_retenu)}</td>
                <td>
                  <span className={`badge-statut badge-${d.statut}`}>{LIBELLE_STATUT[d.statut]}</span>
                </td>
                <td>{d.validateur_email ?? "—"}</td>
                <td className="justification">{d.justification}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
