import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  controlesQualite,
  creerBrouillon,
  definirClient,
  definirLocomotive,
  definirSerie,
  listerBrouillons,
  obtenirVersion,
  publierBrouillon,
  supprimerClient,
  supprimerLocomotive,
  supprimerSerie,
} from "../api/client";
import type {
  AnomalieQualiteApi,
  ClientRefApi,
  LocomotiveApi,
  SerieApi,
  StatutLocomotive,
  VersionDetailApi,
  VersionSummaryApi,
} from "../api/types";
import { FormulaireSerie } from "./admin/FormulaireSerie";
import { FormulaireClient } from "./admin/FormulaireClient";
import { FormulaireLocomotive } from "./admin/FormulaireLocomotive";
import { ImportCSV, type TypeImport } from "./admin/ImportCSV";

interface Props {
  emailKam: string;
}

type SousOnglet = "series" | "clients" | "flotte" | "imports";

function formaterDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const LIBELLE_STATUT: Record<string, string> = {
  brouillon: "Brouillon",
  publie: "Publiée",
  archive: "Archivée",
};

const LIBELLE_STATUT_LOCO: Record<StatutLocomotive, string> = {
  disponible: "Disponible",
  allouee: "Allouée",
  maintenance: "Maintenance",
  reformee: "Réformée",
};

export function AdminReferentiel({ emailKam }: Props) {
  const [versions, setVersions] = useState<VersionSummaryApi[]>([]);
  const [versionSelectionnee, setVersionSelectionnee] = useState<number | null>(null);
  const [detail, setDetail] = useState<VersionDetailApi | null>(null);
  const [sousOnglet, setSousOnglet] = useState<SousOnglet>("series");
  const [editionSerie, setEditionSerie] = useState<SerieApi | null>(null);
  const [editionClient, setEditionClient] = useState<ClientRefApi | null>(null);
  const [editionLoco, setEditionLoco] = useState<LocomotiveApi | null>(null);
  const [formOuvert, setFormOuvert] = useState(false);
  const [anomalies, setAnomalies] = useState<AnomalieQualiteApi[] | null>(null);
  const [message, setMessage] = useState<{ type: "ok" | "erreur"; texte: string } | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function chargerVersions() {
    try {
      const data = await listerBrouillons();
      setVersions(data);
      if (!versionSelectionnee && data.length > 0) {
        setVersionSelectionnee(data[0].numero);
      }
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Chargement impossible" });
    }
  }

  async function chargerDetail(num: number) {
    try {
      const d = await obtenirVersion(num);
      setDetail(d);
      setAnomalies(null);
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Chargement impossible" });
    }
  }

  useEffect(() => {
    void chargerVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (versionSelectionnee !== null) {
      void chargerDetail(versionSelectionnee);
    }
  }, [versionSelectionnee]);

  const versionCourante = detail;
  const estBrouillon = versionCourante?.statut === "brouillon";

  async function nouveauBrouillon() {
    if (!emailKam) {
      setMessage({ type: "erreur", texte: "Renseigne ton e-mail en haut de page avant de créer un brouillon." });
      return;
    }
    setEnCours(true);
    try {
      const { numero } = await creerBrouillon();
      await chargerVersions();
      setVersionSelectionnee(numero);
      setMessage({ type: "ok", texte: `Brouillon v${numero} créé.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Création impossible" });
    } finally {
      setEnCours(false);
    }
  }

  async function lancerControles() {
    if (!versionSelectionnee) return;
    setEnCours(true);
    try {
      const a = await controlesQualite(versionSelectionnee);
      setAnomalies(a);
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Contrôles impossibles" });
    } finally {
      setEnCours(false);
    }
  }

  async function publier() {
    if (!versionSelectionnee) return;
    if (!emailKam) {
      setMessage({ type: "erreur", texte: "Renseigne ton e-mail en haut de page avant de publier." });
      return;
    }
    setEnCours(true);
    try {
      await publierBrouillon(versionSelectionnee, emailKam);
      setMessage({ type: "ok", texte: `Version v${versionSelectionnee} publiée.` });
      await chargerVersions();
      await chargerDetail(versionSelectionnee);
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Publication refusée" });
    } finally {
      setEnCours(false);
    }
  }

  async function sauverSerie(serie: SerieApi) {
    if (!versionSelectionnee || !emailKam) return;
    try {
      await definirSerie(versionSelectionnee, serie.code, serie, emailKam);
      await chargerDetail(versionSelectionnee);
      setFormOuvert(false);
      setEditionSerie(null);
      setMessage({ type: "ok", texte: `Série ${serie.code} enregistrée.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  async function effacerSerie(code: string) {
    if (!versionSelectionnee || !emailKam) return;
    if (!confirm(`Supprimer la série ${code} ?`)) return;
    try {
      await supprimerSerie(versionSelectionnee, code, emailKam);
      await chargerDetail(versionSelectionnee);
      setMessage({ type: "ok", texte: `Série ${code} supprimée.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  async function sauverClient(client: ClientRefApi) {
    if (!versionSelectionnee || !emailKam) return;
    try {
      await definirClient(versionSelectionnee, client.code, client, emailKam);
      await chargerDetail(versionSelectionnee);
      setFormOuvert(false);
      setEditionClient(null);
      setMessage({ type: "ok", texte: `Client ${client.code} enregistré.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  async function effacerClient(code: string) {
    if (!versionSelectionnee || !emailKam) return;
    if (!confirm(`Supprimer le client ${code} ?`)) return;
    try {
      await supprimerClient(versionSelectionnee, code, emailKam);
      await chargerDetail(versionSelectionnee);
      setMessage({ type: "ok", texte: `Client ${code} supprimé.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  async function sauverLoco(loco: LocomotiveApi) {
    if (!versionSelectionnee || !emailKam) return;
    try {
      await definirLocomotive(versionSelectionnee, loco.numero, loco, emailKam);
      await chargerDetail(versionSelectionnee);
      setFormOuvert(false);
      setEditionLoco(null);
      setMessage({ type: "ok", texte: `Locomotive ${loco.numero} enregistrée.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  async function effacerLoco(num: string) {
    if (!versionSelectionnee || !emailKam) return;
    if (!confirm(`Supprimer la locomotive ${num} ?`)) return;
    try {
      await supprimerLocomotive(versionSelectionnee, num, emailKam);
      await chargerDetail(versionSelectionnee);
      setMessage({ type: "ok", texte: `Locomotive ${num} supprimée.` });
    } catch (e) {
      setMessage({ type: "erreur", texte: e instanceof ApiError ? e.message : "Erreur" });
    }
  }

  const seriesActuelles = useMemo(
    () => (versionCourante ? Object.values(versionCourante.series) : []),
    [versionCourante],
  );
  const clientsActuels = useMemo(
    () => (versionCourante ? Object.values(versionCourante.clients) : []),
    [versionCourante],
  );
  const locomotivesActuelles = useMemo(
    () => (versionCourante ? Object.values(versionCourante.flotte) : []),
    [versionCourante],
  );
  const codesSeriesExistantes = useMemo(() => seriesActuelles.map((s) => s.code), [seriesActuelles]);

  return (
    <section className="registre admin">
      <header className="registre-entete">
        <div>
          <h2>Administration du référentiel</h2>
          <p className="registre-sous-titre">
            M1 : cycle de vie brouillon → contrôles qualité → publié. Toute modification est tracée au journal avec l'utilisateur et la raison.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" className="bouton-secondaire" onClick={() => void chargerVersions()} disabled={enCours}>
            Rafraîchir
          </button>
          <button type="button" className="bouton-principal" onClick={nouveauBrouillon} disabled={enCours}>
            + Nouveau brouillon
          </button>
        </div>
      </header>

      {message && (
        <div className={message.type === "ok" ? "bandeau-ok" : "erreur"} onClick={() => setMessage(null)}>
          {message.texte} <span style={{ marginLeft: 8, opacity: 0.6, fontSize: 11 }}>(cliquer pour fermer)</span>
        </div>
      )}

      <div className="admin-layout">
        <aside className="admin-versions">
          <h3 className="sous-titre-journal">Versions</h3>
          {versions.length === 0 && <p className="registre-vide">Aucune version.</p>}
          <ul className="liste-versions">
            {versions.map((v) => (
              <li
                key={v.numero}
                className={`item-version item-version-${v.statut} ${versionSelectionnee === v.numero ? "item-version-actif" : ""}`}
                onClick={() => setVersionSelectionnee(v.numero)}
              >
                <div className="item-version-ligne">
                  <strong>v{v.numero}</strong>
                  <span className={`badge-statut badge-${v.statut === "publie" ? "approuvee" : v.statut === "brouillon" ? "en_attente" : "rejetee"}`}>
                    {LIBELLE_STATUT[v.statut]}
                  </span>
                </div>
                <div className="item-version-detail">
                  {v.nb_series} série{v.nb_series > 1 ? "s" : ""} · {v.nb_clients} client{v.nb_clients > 1 ? "s" : ""} · {v.nb_locomotives} loco
                </div>
                {v.statut === "publie" && v.date_publication && (
                  <div className="item-version-detail">publiée {formaterDate(v.date_publication)}</div>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <div className="admin-contenu">
          {!versionCourante && <p className="registre-vide">Sélectionne une version à gauche.</p>}

          {versionCourante && (
            <>
              <div className="admin-entete-version">
                <h3>
                  Version v{versionCourante.numero} — {LIBELLE_STATUT[versionCourante.statut]}
                </h3>
                <p className="registre-sous-titre">
                  Créée {formaterDate(versionCourante.date_creation)}
                  {versionCourante.date_publication && ` · publiée ${formaterDate(versionCourante.date_publication)} par ${versionCourante.publie_par ?? "?"}`}
                </p>
              </div>

              {estBrouillon && (
                <div className="admin-actions-publication">
                  <button type="button" className="bouton-secondaire" onClick={lancerControles} disabled={enCours}>
                    Lancer les contrôles qualité
                  </button>
                  <button type="button" className="bouton-principal" onClick={publier} disabled={enCours}>
                    Publier cette version
                  </button>
                </div>
              )}

              {anomalies && (
                <div className="anomalies-boite">
                  <h4>
                    Contrôles qualité : {anomalies.length === 0 ? "aucune anomalie" : `${anomalies.length} anomalie${anomalies.length > 1 ? "s" : ""}`}
                  </h4>
                  {anomalies.length > 0 && (
                    <ul className="anomalies-liste">
                      {anomalies.map((a, i) => (
                        <li key={i} className={a.bloquante ? "anomalie-bloquante" : "anomalie-avertissement"}>
                          <span className="anomalie-code">{a.code}</span> {a.message}
                          {a.bloquante && <span className="anomalie-tag">bloquante</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <nav className="sous-onglets">
                <button className={`sous-onglet ${sousOnglet === "series" ? "sous-onglet-actif" : ""}`} onClick={() => setSousOnglet("series")}>
                  Séries ({seriesActuelles.length})
                </button>
                <button className={`sous-onglet ${sousOnglet === "clients" ? "sous-onglet-actif" : ""}`} onClick={() => setSousOnglet("clients")}>
                  Clients ({clientsActuels.length})
                </button>
                <button className={`sous-onglet ${sousOnglet === "flotte" ? "sous-onglet-actif" : ""}`} onClick={() => setSousOnglet("flotte")}>
                  Flotte ({locomotivesActuelles.length})
                </button>
                {estBrouillon && (
                  <button className={`sous-onglet ${sousOnglet === "imports" ? "sous-onglet-actif" : ""}`} onClick={() => setSousOnglet("imports")}>
                    Imports CSV
                  </button>
                )}
              </nav>

              {sousOnglet === "series" && (
                <div className="sous-onglet-corps">
                  {estBrouillon && (
                    <button
                      type="button"
                      className="bouton-ajout"
                      onClick={() => { setEditionSerie(null); setFormOuvert(true); }}
                    >
                      + Ajouter une série
                    </button>
                  )}
                  {seriesActuelles.length === 0 ? (
                    <p className="registre-vide">Aucune série.</p>
                  ) : (
                    <table className="registre-table">
                      <thead>
                        <tr>
                          <th>Code</th>
                          <th>Valeur neuve</th>
                          <th>Durée vie</th>
                          <th>Km réf/an</th>
                          <th>HM 8/16</th>
                          <th>OM fixe/var</th>
                          <th>Assur</th>
                          {estBrouillon && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {seriesActuelles.map((s) => (
                          <tr key={s.code}>
                            <td className="mono">{s.code}</td>
                            <td className="num">{s.valeur_neuve.toLocaleString("fr-FR")} €</td>
                            <td className="num">{s.duree_vie_ans} ans</td>
                            <td className="num">{s.km_reference_annuel.toLocaleString("fr-FR")}</td>
                            <td className="num">{s.cout_hm_8_ans.toLocaleString("fr-FR")} / {s.cout_hm_16_ans.toLocaleString("fr-FR")}</td>
                            <td className="num">{s.om_fixe} / {s.om_variable_eur_par_km}</td>
                            <td className="num">{(s.taux_assurance_annuel * 100).toFixed(2)}%</td>
                            {estBrouillon && (
                              <td>
                                <button className="bouton-mini" onClick={() => { setEditionSerie(s); setFormOuvert(true); }}>Modifier</button>
                                <button className="bouton-mini bouton-mini-danger" onClick={() => effacerSerie(s.code)}>Supprimer</button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {sousOnglet === "clients" && (
                <div className="sous-onglet-corps">
                  {estBrouillon && (
                    <button
                      type="button"
                      className="bouton-ajout"
                      onClick={() => { setEditionClient(null); setFormOuvert(true); }}
                    >
                      + Ajouter un client
                    </button>
                  )}
                  {clientsActuels.length === 0 ? (
                    <p className="registre-vide">Aucun client.</p>
                  ) : (
                    <table className="registre-table">
                      <thead>
                        <tr>
                          <th>Code</th>
                          <th>Nom</th>
                          <th>Rating</th>
                          <th>Paiement avance</th>
                          <th>Cash deposit</th>
                          {estBrouillon && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {clientsActuels.map((c) => (
                          <tr key={c.code}>
                            <td className="mono">{c.code}</td>
                            <td>{c.nom}</td>
                            <td className="num">{c.rating}</td>
                            <td>{c.paiement_avance ? "Oui" : "Non"}</td>
                            <td className="num">{c.cash_deposit ?? 0} €</td>
                            {estBrouillon && (
                              <td>
                                <button className="bouton-mini" onClick={() => { setEditionClient(c); setFormOuvert(true); }}>Modifier</button>
                                <button className="bouton-mini bouton-mini-danger" onClick={() => effacerClient(c.code)}>Supprimer</button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {sousOnglet === "flotte" && (
                <div className="sous-onglet-corps">
                  {estBrouillon && (
                    <button
                      type="button"
                      className="bouton-ajout"
                      onClick={() => { setEditionLoco(null); setFormOuvert(true); }}
                    >
                      + Ajouter une locomotive
                    </button>
                  )}
                  {locomotivesActuelles.length === 0 ? (
                    <p className="registre-vide">Aucune locomotive.</p>
                  ) : (
                    <table className="registre-table">
                      <thead>
                        <tr>
                          <th>Numéro</th>
                          <th>Produit</th>
                          <th>Sous-série</th>
                          <th>Homologations</th>
                          <th>Mise en service</th>
                          <th>Km cumulés</th>
                          <th>Statut</th>
                          {estBrouillon && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {locomotivesActuelles.map((l) => (
                          <tr key={l.numero}>
                            <td className="mono">{l.numero}</td>
                            <td>{l.produit || "—"}</td>
                            <td>{l.sous_serie || "—"}</td>
                            <td>
                              <div className="homologations-liste">
                                {(l.homologations ?? []).length === 0 ? (
                                  <span style={{ color: "var(--fg-muted)" }}>—</span>
                                ) : (
                                  (l.homologations ?? []).map((h) => (
                                    <span key={h} className="pastille-pays-mini">{h}</span>
                                  ))
                                )}
                              </div>
                            </td>
                            <td>{l.mise_en_service}</td>
                            <td className="num">{l.km_cumules.toLocaleString("fr-FR")}</td>
                            <td>{LIBELLE_STATUT_LOCO[l.statut]}</td>
                            {estBrouillon && (
                              <td>
                                <button className="bouton-mini" onClick={() => { setEditionLoco(l); setFormOuvert(true); }}>Modifier</button>
                                <button className="bouton-mini bouton-mini-danger" onClick={() => effacerLoco(l.numero)}>Supprimer</button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {sousOnglet === "imports" && estBrouillon && versionSelectionnee !== null && (
                <div className="sous-onglet-corps">
                  <p className="registre-sous-titre" style={{ marginBottom: 16 }}>
                    Chaque import écrase la section correspondante du brouillon. Les lignes en erreur sont remontées sans bloquer les autres. Encodage UTF-8 attendu, séparateur virgule.
                  </p>
                  {(["dry-lease-grille", "budget-plan", "flotte"] as TypeImport[]).map((type) => (
                    <ImportCSV
                      key={type}
                      type={type}
                      brouillonNumero={versionSelectionnee}
                      emailKam={emailKam}
                      onImporte={() => void chargerDetail(versionSelectionnee)}
                    />
                  ))}
                </div>
              )}

              {formOuvert && sousOnglet === "series" && (
                <FormulaireSerie
                  initial={editionSerie}
                  onSauver={sauverSerie}
                  onAnnuler={() => { setFormOuvert(false); setEditionSerie(null); }}
                />
              )}
              {formOuvert && sousOnglet === "clients" && (
                <FormulaireClient
                  initial={editionClient}
                  onSauver={sauverClient}
                  onAnnuler={() => { setFormOuvert(false); setEditionClient(null); }}
                />
              )}
              {formOuvert && sousOnglet === "flotte" && (
                <FormulaireLocomotive
                  initial={editionLoco}
                  seriesDisponibles={codesSeriesExistantes}
                  onSauver={sauverLoco}
                  onAnnuler={() => { setFormOuvert(false); setEditionLoco(null); }}
                />
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
