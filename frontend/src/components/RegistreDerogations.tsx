import { useEffect, useMemo, useState } from "react";
import { ApiError, listerDerogations } from "../api/client";
import type { DerogationApi, StatutDerogation } from "../api/types";
import { BarreFiltres } from "./BarreFiltres";
import { LigneDetail, PanneauDetail } from "./PanneauDetail";

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
  const [recherche, setRecherche] = useState("");
  const [filtreStatut, setFiltreStatut] = useState("");
  const [filtreNiveau, setFiltreNiveau] = useState("");
  const [detail, setDetail] = useState<DerogationApi | null>(null);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const data = await listerDerogations();
      setDerogations(data.sort((a, b) => b.id - a.id));
    } catch (e) {
      setErreur(e instanceof ApiError ? `${e.status} : ${e.message}` : "Impossible de joindre l'API.");
    } finally {
      setEnCours(false);
    }
  }

  useEffect(() => {
    void rafraichir();
  }, []);

  const niveaux = useMemo(
    () => (derogations ? Array.from(new Set(derogations.map((d) => d.niveau))).sort() : []),
    [derogations],
  );

  const derogationsFiltrees = useMemo(() => {
    if (!derogations) return [];
    const q = recherche.trim().toLowerCase();
    return derogations.filter((d) => {
      if (filtreStatut && d.statut !== filtreStatut) return false;
      if (filtreNiveau && String(d.niveau) !== filtreNiveau) return false;
      if (q && !`${d.id} ${d.client_code} ${d.serie_code} ${d.demandeur} ${d.justification}`.toLowerCase().includes(q))
        return false;
      return true;
    });
  }, [derogations, recherche, filtreStatut, filtreNiveau]);

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <h2>Registre central des dérogations</h2>
          <p className="registre-sous-titre">
            M4-05 : chaque demande hors règles est tracée ici — niveau et validateur recalculés côté serveur. Clic sur une ligne pour le détail complet.
          </p>
        </div>
        <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
          {enCours ? "Chargement…" : "Rafraîchir"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {derogations && (
        <BarreFiltres
          recherche={recherche}
          surRecherche={setRecherche}
          placeholderRecherche="ID, client, série, demandeur, justification…"
          filtres={[
            {
              libelle: "Statut",
              valeur: filtreStatut,
              options: [
                { valeur: "en_attente", libelle: "En attente" },
                { valeur: "approuvee", libelle: "Approuvée" },
                { valeur: "rejetee", libelle: "Rejetée" },
              ],
              onChange: setFiltreStatut,
            },
            {
              libelle: "Niveau",
              valeur: filtreNiveau,
              options: niveaux.map((n) => ({ valeur: String(n), libelle: `Niveau ${n}` })),
              onChange: setFiltreNiveau,
            },
          ]}
          nbResultats={derogationsFiltrees.length}
          nbTotal={derogations.length}
        />
      )}

      {derogations && derogations.length === 0 && (
        <p className="registre-vide">Aucune dérogation enregistrée pour l'instant.</p>
      )}
      {derogations && derogations.length > 0 && derogationsFiltrees.length === 0 && (
        <p className="registre-vide">Aucun résultat ne correspond aux filtres.</p>
      )}

      {derogationsFiltrees.length > 0 && (
        <table className="registre-table clickable">
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
            </tr>
          </thead>
          <tbody>
            {derogationsFiltrees.map((d) => (
              <tr key={d.id} onClick={() => setDetail(d)}>
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
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {detail && (
        <PanneauDetail
          titre={`Dérogation #${detail.id}`}
          sousTitre={`Demandée le ${formaterDate(detail.date_demande)} par ${detail.demandeur}`}
          onFermer={() => setDetail(null)}
        >
          <h3 className="panneau-section">Statut</h3>
          <LigneDetail
            libelle="Statut"
            valeur={<span className={`badge-statut badge-${detail.statut}`}>{LIBELLE_STATUT[detail.statut]}</span>}
          />
          <LigneDetail libelle="Niveau requis" valeur={`Niveau ${detail.niveau}`} />
          <LigneDetail libelle="Validateur" valeur={detail.validateur_email ?? "—"} />
          {detail.date_decision && (
            <>
              <LigneDetail libelle="Décision le" valeur={formaterDate(detail.date_decision)} />
              <LigneDetail libelle="Décideur" valeur={detail.decideur ?? "—"} />
              {detail.commentaire_decision && (
                <LigneDetail libelle="Commentaire" valeur={<em>« {detail.commentaire_decision} »</em>} />
              )}
            </>
          )}

          <h3 className="panneau-section">Justification</h3>
          <p className="justification-complete">{detail.justification}</p>

          <h3 className="panneau-section">Configuration gelée</h3>
          <LigneDetail libelle="Client" valeur={detail.client_code} />
          <LigneDetail libelle="Série" valeur={detail.serie_code} />
          <LigneDetail
            libelle="Locomotive"
            valeur={detail.configuration.locomotive_numero ?? <em>non affectée</em>}
          />
          <LigneDetail libelle="Durée" valeur={`${detail.configuration.duree_mois} mois`} />
          <LigneDetail
            libelle="Km annuels"
            valeur={detail.configuration.km_annuel.toLocaleString("fr-FR")}
          />
          <LigneDetail libelle="Quantité" valeur={detail.configuration.quantite} />
          <LigneDetail libelle="Date début" valeur={detail.configuration.date_debut} />
          <LigneDetail libelle="Montant mensuel retenu" valeur={formaterMontant(detail.montant_mensuel_retenu)} />
          <LigneDetail libelle="Version du référentiel" valeur={`v${detail.version_referentiel}`} />

          {Object.keys(detail.configuration.prix_negocies ?? {}).length > 0 && (
            <>
              <h3 className="panneau-section">Prix négociés par brique</h3>
              {Object.entries(detail.configuration.prix_negocies).map(([brique, prix]) => (
                <LigneDetail key={brique} libelle={brique} valeur={formaterMontant(prix)} />
              ))}
            </>
          )}
        </PanneauDetail>
      )}
    </section>
  );
}
