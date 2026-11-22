import { useEffect, useState } from "react";
import { ApiError, listerOffresGenerees } from "../api/client";
import type { OffreGenereeApi } from "../api/types";

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

export function RegistreOffres() {
  const [offres, setOffres] = useState<OffreGenereeApi[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const data = await listerOffresGenerees();
      setOffres(data.sort((a, b) => b.sequence - a.sequence));
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
          <h2>Offres PDF émises</h2>
          <p className="registre-sous-titre">
            M3-06 : chaque PDF numéroté <code>AK-XXXXXX</code> envoyé au client est tracé ici. La numérotation n'est jamais remise à zéro.
          </p>
        </div>
        <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
          {enCours ? "Chargement…" : "Rafraîchir"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {offres && offres.length === 0 && (
        <p className="registre-vide">Aucune offre PDF n'a encore été générée.</p>
      )}

      {offres && offres.length > 0 && (
        <table className="registre-table">
          <thead>
            <tr>
              <th>N° offre</th>
              <th>Date</th>
              <th>KAM</th>
              <th>Client</th>
              <th>Série</th>
              <th>Durée</th>
              <th>Km/an</th>
              <th>Montant / mois</th>
              <th>Niveau</th>
              <th>Réf. v</th>
            </tr>
          </thead>
          <tbody>
            {offres.map((o) => (
              <tr key={o.sequence}>
                <td className="mono">{o.numero}</td>
                <td>{formaterDate(o.date_generation)}</td>
                <td>{o.utilisateur}</td>
                <td>{o.client_code}</td>
                <td>{o.serie_code}</td>
                <td className="num">{o.configuration.duree_mois} mois</td>
                <td className="num">{o.configuration.km_annuel.toLocaleString("fr-FR")}</td>
                <td className="num">{formaterMontant(o.montant_mensuel_retenu)}</td>
                <td>
                  {o.niveau_validation === 0 ? (
                    <span className="badge-statut badge-approuvee">KAM</span>
                  ) : (
                    <span className="badge-statut badge-en_attente">N{o.niveau_validation}</span>
                  )}
                </td>
                <td className="num">v{o.version_referentiel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
