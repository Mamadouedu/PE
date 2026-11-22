import { useEffect, useMemo, useState } from "react";
import { ApiError, listerOffresGenerees, telechargerOffrePdf } from "../api/client";
import type { OffreGenereeApi } from "../api/types";
import { BarreFiltres } from "./BarreFiltres";
import { LigneDetail, PanneauDetail } from "./PanneauDetail";

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

function telecharger(blob: Blob, nom: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function RegistreOffres() {
  const [offres, setOffres] = useState<OffreGenereeApi[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [filtreClient, setFiltreClient] = useState("");
  const [filtreKam, setFiltreKam] = useState("");
  const [detail, setDetail] = useState<OffreGenereeApi | null>(null);
  const [telechargement, setTelechargement] = useState(false);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const data = await listerOffresGenerees();
      setOffres(data.sort((a, b) => b.sequence - a.sequence));
    } catch (e) {
      setErreur(e instanceof ApiError ? `${e.status} : ${e.message}` : "Impossible de joindre l'API.");
    } finally {
      setEnCours(false);
    }
  }

  useEffect(() => {
    void rafraichir();
  }, []);

  const clients = useMemo(
    () => (offres ? Array.from(new Set(offres.map((o) => o.client_code))).sort() : []),
    [offres],
  );
  const kams = useMemo(
    () => (offres ? Array.from(new Set(offres.map((o) => o.utilisateur))).sort() : []),
    [offres],
  );

  const offresFiltrees = useMemo(() => {
    if (!offres) return [];
    const q = recherche.trim().toLowerCase();
    return offres.filter((o) => {
      if (filtreClient && o.client_code !== filtreClient) return false;
      if (filtreKam && o.utilisateur !== filtreKam) return false;
      if (q && !`${o.numero} ${o.client_code} ${o.serie_code} ${o.utilisateur}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [offres, recherche, filtreClient, filtreKam]);

  async function reTelecharger(offre: OffreGenereeApi) {
    setTelechargement(true);
    try {
      const { blob, nomFichier } = await telechargerOffrePdf(offre.configuration, offre.utilisateur);
      telecharger(blob, nomFichier);
    } catch (e) {
      alert(e instanceof ApiError ? `${e.status} : ${e.message}` : "Téléchargement impossible.");
    } finally {
      setTelechargement(false);
    }
  }

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <h2>Offres PDF émises</h2>
          <p className="registre-sous-titre">
            M3-06 : chaque PDF numéroté <code>AK-XXXXXX</code> envoyé au client est tracé ici. Clic sur une ligne pour le détail et re-téléchargement.
          </p>
        </div>
        <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
          {enCours ? "Chargement…" : "Rafraîchir"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {offres && (
        <BarreFiltres
          recherche={recherche}
          surRecherche={setRecherche}
          placeholderRecherche="N° offre, client, série, KAM…"
          filtres={[
            {
              libelle: "Client",
              valeur: filtreClient,
              options: clients.map((c) => ({ valeur: c, libelle: c })),
              onChange: setFiltreClient,
            },
            {
              libelle: "KAM",
              valeur: filtreKam,
              options: kams.map((k) => ({ valeur: k, libelle: k })),
              onChange: setFiltreKam,
            },
          ]}
          nbResultats={offresFiltrees.length}
          nbTotal={offres.length}
        />
      )}

      {offres && offres.length === 0 && (
        <p className="registre-vide">Aucune offre PDF n'a encore été générée.</p>
      )}
      {offres && offres.length > 0 && offresFiltrees.length === 0 && (
        <p className="registre-vide">Aucun résultat ne correspond aux filtres.</p>
      )}

      {offresFiltrees.length > 0 && (
        <table className="registre-table clickable">
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
            {offresFiltrees.map((o) => (
              <tr key={o.sequence} onClick={() => setDetail(o)}>
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

      {detail && (
        <PanneauDetail
          titre={`Offre ${detail.numero}`}
          sousTitre={`Générée le ${formaterDate(detail.date_generation)} par ${detail.utilisateur}`}
          onFermer={() => setDetail(null)}
        >
          <h3 className="panneau-section">Récapitulatif</h3>
          <LigneDetail libelle="Client" valeur={detail.client_code} />
          <LigneDetail libelle="Série" valeur={detail.serie_code} />
          <LigneDetail
            libelle="Locomotive"
            valeur={detail.configuration.locomotive_numero ?? <em>non affectée</em>}
          />
          <LigneDetail libelle="Durée" valeur={`${detail.configuration.duree_mois} mois`} />
          <LigneDetail libelle="Km annuels" valeur={detail.configuration.km_annuel.toLocaleString("fr-FR")} />
          <LigneDetail libelle="Quantité" valeur={detail.configuration.quantite} />
          <LigneDetail libelle="Date début" valeur={detail.configuration.date_debut} />
          <LigneDetail libelle="Âge début" valeur={`${detail.configuration.age_debut_ans ?? "—"} ans`} />
          <LigneDetail
            libelle="Km cumulés début"
            valeur={detail.configuration.km_cumules_debut?.toLocaleString("fr-FR") ?? "—"}
          />
          <LigneDetail libelle="Montant mensuel" valeur={formaterMontant(detail.montant_mensuel_retenu)} />
          <LigneDetail
            libelle="Niveau de validation"
            valeur={
              detail.niveau_validation === 0 ? (
                <span className="badge-statut badge-approuvee">KAM — niveau 0</span>
              ) : (
                <span className="badge-statut badge-en_attente">Niveau {detail.niveau_validation}</span>
              )
            }
          />
          <LigneDetail libelle="Version du référentiel" valeur={`v${detail.version_referentiel}`} />

          {Object.keys(detail.configuration.prix_negocies ?? {}).length > 0 && (
            <>
              <h3 className="panneau-section">Prix négociés par brique</h3>
              {Object.entries(detail.configuration.prix_negocies).map(([brique, prix]) => (
                <LigneDetail key={brique} libelle={brique} valeur={formaterMontant(prix)} />
              ))}
            </>
          )}

          <div className="panneau-actions">
            <button
              type="button"
              className="bouton-principal"
              onClick={() => reTelecharger(detail)}
              disabled={telechargement}
            >
              {telechargement ? "Téléchargement…" : "Re-télécharger le PDF"}
            </button>
          </div>
        </PanneauDetail>
      )}
    </section>
  );
}
