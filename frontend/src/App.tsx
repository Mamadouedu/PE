import { useState } from "react";
import "./App.css";
import { ApiError, chiffrerOffre } from "./api/client";
import type { ConfigurationOffre } from "./api/types";
import { versVueKam, type OffreKam } from "./api/offre";
import { Comparateur } from "./components/Comparateur";
import { ConfigurateurForm } from "./components/ConfigurateurForm";
import { AdminReferentiel } from "./components/AdminReferentiel";
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

type Onglet = "tableau_bord" | "configurateur" | "offres" | "derogations" | "referentiel" | "admin";

const ONGLETS: { id: Onglet; libelle: string }[] = [
  { id: "tableau_bord", libelle: "Tableau de bord" },
  { id: "configurateur", libelle: "Configurateur" },
  { id: "offres", libelle: "Offres émises" },
  { id: "derogations", libelle: "Dérogations" },
  { id: "referentiel", libelle: "Référentiel" },
  { id: "admin", libelle: "Administration" },
];

export default function App() {
  const [ongletActif, setOngletActif] = useState<Onglet>("tableau_bord");
  const [offre, setOffre] = useState<OffreKam | null>(null);
  const [configuration, setConfiguration] = useState<ConfigurationOffre | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [scenarios, setScenarios] = useState<ScenarioComparaison[]>([]);
  const [kamEmail, setKamEmail] = useState("");

  async function chiffrer(config: ConfigurationOffre) {
    setEnCours(true);
    setErreur(null);
    try {
      const reponse = await chiffrerOffre(config);
      setOffre(versVueKam(reponse));
      setConfiguration(config);
    } catch (e) {
      setOffre(null);
      if (e instanceof ApiError) {
        setErreur(messageErreur(e.detail));
      } else {
        setErreur("Impossible de joindre le moteur de prix.");
      }
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

  return (
    <div className="page">
      <header className="entete">
        <div>
          <h1>Plateforme Pricing Akiem</h1>
          <p>Moteur de prix full service leasing — configurateur KAM</p>
        </div>
        <label className="identification-kam">
          Votre e-mail
          <input
            type="email"
            value={kamEmail}
            onChange={(e) => setKamEmail(e.target.value)}
            placeholder="vous@akiem.com"
          />
        </label>
      </header>

      <nav className="onglets" role="tablist">
        {ONGLETS.map((o) => (
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
                <p className="aide-resultat">Remplissez la configuration et cliquez sur « Chiffrer ».</p>
              )}
              <Comparateur scenarios={scenarios} onRetirer={retirerDuComparateur} />
            </div>
          </>
        )}

        {ongletActif === "tableau_bord" && <TableauDeBord emailKam={kamEmail} />}
        {ongletActif === "offres" && <RegistreOffres />}
        {ongletActif === "derogations" && <RegistreDerogations />}
        {ongletActif === "referentiel" && <VueReferentiel />}
        {ongletActif === "admin" && <AdminReferentiel emailKam={kamEmail} />}
      </main>
    </div>
  );
}
