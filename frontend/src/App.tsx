import { useState } from "react";
import "./App.css";
import { ApiError, chiffrerOffre } from "./api/client";
import type { CalculateQuoteRequest } from "./api/types";
import { versVueKam, type OffreKam } from "./api/offre";
import { Comparateur } from "./components/Comparateur";
import { ConfigurateurForm } from "./components/ConfigurateurForm";
import { ResultatOffre } from "./components/ResultatOffre";
import { libelleScenario, MAX_SCENARIOS, type ScenarioComparaison } from "./scenario";

function messageErreur(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return "Une erreur inattendue est survenue.";
}

export default function App() {
  const [offre, setOffre] = useState<OffreKam | null>(null);
  const [requete, setRequete] = useState<CalculateQuoteRequest | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [scenarios, setScenarios] = useState<ScenarioComparaison[]>([]);
  const [kamEmail, setKamEmail] = useState("");

  async function chiffrer(req: CalculateQuoteRequest) {
    setEnCours(true);
    setErreur(null);
    try {
      const reponse = await chiffrerOffre(req);
      setOffre(versVueKam(reponse));
      setRequete(req);
    } catch (e) {
      setOffre(null);
      if (e instanceof ApiError) {
        setErreur(messageErreur(e.detail));
      } else {
        setErreur("Impossible de joindre l'API de pricing.");
      }
    } finally {
      setEnCours(false);
    }
  }

  function ajouterAuComparateur() {
    if (!offre || !requete) return;
    const scenario: ScenarioComparaison = {
      id: `${Date.now()}`,
      label: libelleScenario(requete),
      requete,
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
          <h1>Configurateur KAM</h1>
          <p>Plateforme Pricing Akiem — chiffrage full service leasing</p>
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

      <main className="contenu">
        <ConfigurateurForm enCours={enCours} onChiffrer={chiffrer} />

        <div className="zone-resultat">
          {erreur && <div className="erreur">{erreur}</div>}
          {offre && (
            <ResultatOffre
              offre={offre}
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
      </main>
    </div>
  );
}
