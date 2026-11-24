import { useEffect, useState } from "react";
import "./App.css";
import { ApiError, chiffrerOffre } from "./api/client";
import { aPermission, logout, rafraichirMe, sessionActive, type Role } from "./api/auth";
import type { ConfigurationOffre } from "./api/types";
import { versVueKam, type OffreKam } from "./api/offre";
import { AdminReferentiel } from "./components/AdminReferentiel";
import { Assistant } from "./components/Assistant";
import { Catalogue } from "./components/Catalogue";
import { ConfigurateurV2 } from "./components/ConfigurateurV2";
import { Comparateur } from "./components/Comparateur";
import { ConfigurateurForm } from "./components/ConfigurateurForm";
import { Login } from "./components/Login";
import { RegistreDerogations } from "./components/RegistreDerogations";
import { RegistreOffres } from "./components/RegistreOffres";
import { ResultatOffre } from "./components/ResultatOffre";
import { TableauDeBord } from "./components/TableauDeBord";
import { VueReferentiel } from "./components/VueReferentiel";
import { libelleScenario, MAX_SCENARIOS, type ScenarioComparaison } from "./scenario";

function messageErreur(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return "Une erreur inattendue est survenue.";
}

type Onglet =
  | "tableau_bord"
  | "configurateur"
  | "configurateur_v2"
  | "offres"
  | "derogations"
  | "referentiel"
  | "catalogue"
  | "admin"
  | "assistant";

interface DefinitionOnglet {
  id: Onglet;
  libelle: string;
  permission?: string;
}

const ONGLETS: DefinitionOnglet[] = [
  { id: "tableau_bord", libelle: "Tableau de bord" },
  { id: "configurateur", libelle: "Configurateur" },
  { id: "configurateur_v2", libelle: "Configurateur v2" },
  { id: "offres", libelle: "Offres émises" },
  { id: "derogations", libelle: "Dérogations" },
  { id: "referentiel", libelle: "Référentiel" },
  { id: "catalogue", libelle: "Catalogue" },
  { id: "admin", libelle: "Administration", permission: "admin_referentiel" },
  { id: "assistant", libelle: "Assistant" },
];

export default function App() {
  const [session, setSession] = useState(sessionActive());
  const [ongletActif, setOngletActif] = useState<Onglet>("tableau_bord");
  const [offre, setOffre] = useState<OffreKam | null>(null);
  const [configuration, setConfiguration] = useState<ConfigurationOffre | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [scenarios, setScenarios] = useState<ScenarioComparaison[]>([]);

  useEffect(() => {
    if (session) {
      void rafraichirMe().then((u) => {
        if (!u) setSession(null);
      });
    }
  }, []);

  async function surDeconnexion() {
    await logout();
    setSession(null);
    setOffre(null);
    setConfiguration(null);
    setScenarios([]);
    setOngletActif("tableau_bord");
  }

  if (!session) {
    return <Login onConnecte={() => setSession(sessionActive())} />;
  }

  const kamEmail = session.utilisateur.email;
  const ongletsVisibles = ONGLETS.filter((o) => !o.permission || aPermission(o.permission));

  async function chiffrer(config: ConfigurationOffre) {
    setEnCours(true);
    setErreur(null);
    try {
      const reponse = await chiffrerOffre(config);
      setOffre(versVueKam(reponse));
      setConfiguration(config);
    } catch (e) {
      setOffre(null);
      if (e instanceof ApiError) setErreur(messageErreur(e.detail));
      else setErreur("Impossible de joindre le moteur de prix.");
    } finally {
      setEnCours(false);
    }
  }

  function ajouterAuComparateur() {
    if (!offre || !configuration) return;
    const scenario: ScenarioComparaison = {
      id: `${Date.now()}`,
      label: libelleScenario(configuration),
      configuration,
      offre,
    };
    setScenarios((courant) => [...courant, scenario].slice(-MAX_SCENARIOS));
  }

  function retirerDuComparateur(id: string) {
    setScenarios((courant) => courant.filter((s) => s.id !== id));
  }

  const role = session.utilisateur.role as Role;

  return (
    <div className="page">
      <header className="entete">
        <div>
          <h1>Plateforme Pricing Akiem</h1>
          <p>Moteur de prix full service leasing</p>
        </div>
        <div className="utilisateur-chip">
          <span className="utilisateur-nom">{session.utilisateur.nom}</span>
          <span className={`badge-role badge-role-${role}`}>{role}</span>
          <span className="utilisateur-email">{session.utilisateur.email}</span>
          <button type="button" className="bouton-deconnexion" onClick={surDeconnexion}>
            Déconnexion
          </button>
        </div>
      </header>

      <nav className="onglets" role="tablist">
        {ongletsVisibles.map((o) => (
          <button
            key={o.id}
            type="button"
            role="tab"
            aria-selected={ongletActif === o.id}
            className={`onglet ${ongletActif === o.id ? "onglet-actif" : ""}`}
            onClick={() => setOngletActif(o.id)}
          >
            {o.libelle}
          </button>
        ))}
      </nav>

      <main className="contenu">
        {ongletActif === "configurateur" && (
          <>
            <ConfigurateurForm enCours={enCours} onChiffrer={chiffrer} />
            <div className="zone-resultat">
              {erreur && <div className="erreur">{erreur}</div>}
              {offre && configuration && (
                <ResultatOffre
                  offre={offre}
                  configuration={configuration}
                  demandeurEmail={kamEmail}
                  onAjouterAuComparateur={ajouterAuComparateur}
                  comparateurPlein={scenarios.length >= MAX_SCENARIOS}
                />
              )}
              {!offre && !erreur && (
                <p className="aide-resultat">Remplis la configuration et clique sur « Chiffrer ».</p>
              )}
              <Comparateur scenarios={scenarios} onRetirer={retirerDuComparateur} />
            </div>
          </>
        )}

        {ongletActif === "tableau_bord" && <TableauDeBord emailKam={kamEmail} />}
        {ongletActif === "offres" && <RegistreOffres />}
        {ongletActif === "derogations" && <RegistreDerogations />}
        {ongletActif === "referentiel" && <VueReferentiel />}
        {ongletActif === "configurateur_v2" && <ConfigurateurV2 />}
        {ongletActif === "catalogue" && <Catalogue />}
        {ongletActif === "admin" && <AdminReferentiel emailKam={kamEmail} />}
        {ongletActif === "assistant" && <Assistant />}
      </main>
    </div>
  );
}
