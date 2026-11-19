import { useState } from "react";
import "./App.css";
import { ApiError, chiffrerOffre } from "./api/client";
import type { ConfigurationOffre } from "./api/types";
import { versVueKam, type OffreKam } from "./api/offre";
import { ConfigurateurForm } from "./components/ConfigurateurForm";
import { ResultatOffre } from "./components/ResultatOffre";

function messageErreur(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return "Une erreur inattendue est survenue.";
}

export default function App() {
  const [offre, setOffre] = useState<OffreKam | null>(null);
  const [configuration, setConfiguration] = useState<ConfigurationOffre | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

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

  return (
    <div className="page">
      <header className="entete">
        <h1>Configurateur KAM</h1>
        <p>Plateforme Pricing Akiem — chiffrage full service leasing</p>
      </header>

      <main className="contenu">
        <ConfigurateurForm enCours={enCours} onChiffrer={chiffrer} />

        <div className="zone-resultat">
          {erreur && <div className="erreur">{erreur}</div>}
          {offre && configuration && <ResultatOffre offre={offre} configuration={configuration} />}
          {!offre && !erreur && (
            <p className="aide-resultat">Remplissez la configuration et cliquez sur « Chiffrer ».</p>
          )}
        </div>
      </main>
    </div>
  );
}
