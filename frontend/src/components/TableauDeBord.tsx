import { useEffect, useMemo, useState } from "react";
import { ApiError, listerDerogations, listerOffresGenerees } from "../api/client";
import type { DerogationApi, OffreGenereeApi } from "../api/types";

function formaterMontant(n: number): string {
  return n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

function clefMois(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function libelleMois(cle: string): string {
  const [y, m] = cle.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
}

interface Props {
  emailKam?: string;
}

export function TableauDeBord({ emailKam }: Props) {
  const [offres, setOffres] = useState<OffreGenereeApi[]>([]);
  const [derogations, setDerogations] = useState<DerogationApi[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [vueMoi, setVueMoi] = useState(false);

  async function rafraichir() {
    setEnCours(true);
    setErreur(null);
    try {
      const [o, d] = await Promise.all([listerOffresGenerees(), listerDerogations()]);
      setOffres(o);
      setDerogations(d);
    } catch (e) {
      setErreur(e instanceof ApiError ? `${e.status} : ${e.message}` : "Impossible de joindre l'API.");
    } finally {
      setEnCours(false);
    }
  }

  useEffect(() => {
    void rafraichir();
  }, []);

  const emailFiltre = vueMoi && emailKam ? emailKam.toLowerCase() : null;

  const offresVisibles = useMemo(
    () => (emailFiltre ? offres.filter((o) => o.utilisateur.toLowerCase() === emailFiltre) : offres),
    [offres, emailFiltre],
  );
  const derogationsVisibles = useMemo(
    () => (emailFiltre ? derogations.filter((d) => d.demandeur.toLowerCase() === emailFiltre) : derogations),
    [derogations, emailFiltre],
  );

  const moisCourant = new Date();
  const cleMoisCourant = `${moisCourant.getFullYear()}-${String(moisCourant.getMonth() + 1).padStart(2, "0")}`;

  const offresMoisEnCours = offresVisibles.filter((o) => clefMois(o.date_generation) === cleMoisCourant);
  const caMensuel = offresMoisEnCours.reduce(
    (total, o) => total + o.montant_mensuel_retenu * o.configuration.duree_mois,
    0,
  );

  const derogationsEnAttente = derogationsVisibles.filter((d) => d.statut === "en_attente");
  const derogationsApprouvees = derogationsVisibles.filter((d) => d.statut === "approuvee").length;
  const derogationsRejetees = derogationsVisibles.filter((d) => d.statut === "rejetee").length;
  const derogationsDecidees = derogationsApprouvees + derogationsRejetees;
  const tauxApprobation = derogationsDecidees > 0 ? Math.round((derogationsApprouvees / derogationsDecidees) * 100) : null;

  const topClients = useMemo(() => {
    const parClient = new Map<string, number>();
    for (const o of offresVisibles) {
      parClient.set(o.client_code, (parClient.get(o.client_code) ?? 0) + 1);
    }
    return Array.from(parClient.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [offresVisibles]);

  const parMois = useMemo(() => {
    const m = new Map<string, number>();
    for (const o of offresVisibles) {
      const cle = clefMois(o.date_generation);
      m.set(cle, (m.get(cle) ?? 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0])).slice(-6);
  }, [offresVisibles]);

  const maxMois = Math.max(1, ...parMois.map(([, v]) => v));

  const repartitionNiveau = useMemo(() => {
    const r = [0, 0, 0, 0];
    for (const o of offresVisibles) {
      const niveau = Math.min(3, Math.max(0, o.niveau_validation));
      r[niveau] += 1;
    }
    return r;
  }, [offresVisibles]);

  return (
    <section className="registre tableau-bord">
      <header className="registre-entete">
        <div>
          <h2>Tableau de bord</h2>
          <p className="registre-sous-titre">
            Vue d'ensemble de l'activité commerciale — offres émises, dérogations, répartition par niveau et par client.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {emailKam && (
            <label className="filtre-moi">
              <input type="checkbox" checked={vueMoi} onChange={(e) => setVueMoi(e.target.checked)} />
              Mes offres uniquement
            </label>
          )}
          <button type="button" className="bouton-secondaire" onClick={rafraichir} disabled={enCours}>
            {enCours ? "Chargement…" : "Rafraîchir"}
          </button>
        </div>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      <div className="cartes-kpi">
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{offresVisibles.length}</div>
          <div className="carte-kpi-libelle">Offres PDF émises (total)</div>
          <div className="carte-kpi-detail">{offresMoisEnCours.length} ce mois-ci</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{formaterMontant(caMensuel)}</div>
          <div className="carte-kpi-libelle">CA contrats émis ce mois</div>
          <div className="carte-kpi-detail">Somme montant × durée</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{derogationsEnAttente.length}</div>
          <div className="carte-kpi-libelle">Dérogations en attente</div>
          <div className="carte-kpi-detail">{derogationsVisibles.length} au total</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{tauxApprobation !== null ? `${tauxApprobation}%` : "—"}</div>
          <div className="carte-kpi-libelle">Taux d'approbation</div>
          <div className="carte-kpi-detail">
            {derogationsApprouvees} approuvée{derogationsApprouvees > 1 ? "s" : ""} / {derogationsRejetees} rejetée{derogationsRejetees > 1 ? "s" : ""}
          </div>
        </div>
      </div>

      <div className="grille-graphiques">
        <div className="carte-graphique">
          <h3 className="sous-titre-journal">Offres par mois (6 derniers)</h3>
          {parMois.length === 0 ? (
            <p className="registre-vide">Aucune offre pour le moment.</p>
          ) : (
            <div className="barres-mois">
              {parMois.map(([cle, valeur]) => (
                <div key={cle} className="barre-mois">
                  <div className="barre-mois-valeur">{valeur}</div>
                  <div
                    className="barre-mois-bar"
                    style={{ height: `${Math.round((valeur / maxMois) * 100)}%` }}
                  />
                  <div className="barre-mois-libelle">{libelleMois(cle)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="carte-graphique">
          <h3 className="sous-titre-journal">Répartition par niveau de validation</h3>
          <div className="repartition-niveau">
            {repartitionNiveau.map((n, i) => {
              const total = offresVisibles.length || 1;
              const pct = Math.round((n / total) * 100);
              return (
                <div key={i} className="niveau-ligne">
                  <span className="niveau-label">N{i}</span>
                  <div className="niveau-bar-bg">
                    <div className={`niveau-bar niveau-bar-${i}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="niveau-valeur">
                    {n} ({pct}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="carte-graphique">
          <h3 className="sous-titre-journal">Top clients (nb offres)</h3>
          {topClients.length === 0 ? (
            <p className="registre-vide">Aucun client encore.</p>
          ) : (
            <table className="registre-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Offres</th>
                </tr>
              </thead>
              <tbody>
                {topClients.map(([code, nb]) => (
                  <tr key={code}>
                    <td>{code}</td>
                    <td className="num">{nb}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
