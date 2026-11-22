import { useState } from "react";
import { ApiError, telechargerOffrePdf } from "../api/client";
import type { ConfigurationOffre } from "../api/types";

interface Props {
  configuration: ConfigurationOffre;
  demandeurEmail: string;
}

export function TelechargerPdfButton({ configuration, demandeurEmail }: Props) {
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function telecharger() {
    setEnCours(true);
    setErreur(null);
    try {
      const { blob, nomFichier } = await telechargerOffrePdf(configuration);
      const url = URL.createObjectURL(blob);
      const lien = document.createElement("a");
      lien.href = url;
      lien.download = nomFichier;
      document.body.appendChild(lien);
      lien.click();
      lien.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErreur(e instanceof ApiError ? String(e.detail) : "Impossible de générer le PDF.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="telecharger-pdf">
      <button
        type="button"
        className="bouton-secondaire"
        onClick={telecharger}
        disabled={enCours || !demandeurEmail}
        title={!demandeurEmail ? "Renseignez votre e-mail en haut de page" : undefined}
      >
        {enCours ? "Génération…" : "⭳ Télécharger le PDF"}
      </button>
      {erreur && <p className="erreur-inline">{erreur}</p>}
    </div>
  );
}
