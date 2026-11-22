import { useEffect, useRef, useState } from "react";
import { ApiError, demanderDerogation, obtenirDerogation } from "../api/client";
import type { ConfigurationOffre, DerogationApi } from "../api/types";

const INTERVALLE_SONDAGE_MS = 4000;

const LIBELLE_STATUT: Record<string, string> = {
  en_attente: "En attente de décision",
  approuvee: "Approuvée",
  rejetee: "Rejetée",
};

interface Props {
  libelleNiveau: string;
  configuration: ConfigurationOffre;
  demandeurEmail: string;
}

export function DemandeValidation({ libelleNiveau, configuration, demandeurEmail }: Props) {
  const [justification, setJustification] = useState("");
  const [derogation, setDerogation] = useState<DerogationApi | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const intervalleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Remet tout à zéro si la configuration change : une dérogation ne vaut
    // que pour la configuration exacte qui l'a déclenchée (M4-04).
    setDerogation(null);
    setErreur(null);
  }, [configuration]);

  useEffect(() => {
    if (!derogation || derogation.statut !== "en_attente") {
      if (intervalleRef.current) clearInterval(intervalleRef.current);
      return;
    }
    intervalleRef.current = setInterval(async () => {
      try {
        const miseAJour = await obtenirDerogation(derogation.id);
        setDerogation(miseAJour);
      } catch {
        // on retente au prochain tick ; pas la peine d'alarmer l'utilisateur
        // pour un sondage raté.
      }
    }, INTERVALLE_SONDAGE_MS);
    return () => {
      if (intervalleRef.current) clearInterval(intervalleRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [derogation?.id, derogation?.statut]);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const creee = await demanderDerogation(configuration, justification);
      setDerogation(creee);
    } catch (e) {
      setErreur(e instanceof ApiError ? String(e.detail) : "Impossible de joindre le moteur de prix.");
    } finally {
      setEnCours(false);
    }
  }

  if (derogation) {
    return (
      <div className={`demande-validation statut-${derogation.statut}`}>
        <p className="demande-statut">{LIBELLE_STATUT[derogation.statut]}</p>
        <p className="demande-detail">
          Demandé par {derogation.demandeur}
          {derogation.validateur_email && <> — en attente de {derogation.validateur_email}</>}
        </p>
        {derogation.statut === "en_attente" && (
          <p className="demande-detail aide">Vérification automatique toutes les 4 secondes…</p>
        )}
        {derogation.date_decision && (
          <p className="demande-detail">
            Décidé par {derogation.decideur} le{" "}
            {new Date(derogation.date_decision).toLocaleString("fr-FR")}
            {derogation.commentaire_decision && <> — « {derogation.commentaire_decision} »</>}
          </p>
        )}
      </div>
    );
  }

  return (
    <form className="demande-validation" onSubmit={soumettre}>
      <p className="demande-detail">
        Cette offre nécessite une validation : {libelleNiveau}.
      </p>
      <label>
        Justification
        <textarea
          value={justification}
          onChange={(e) => setJustification(e.target.value)}
          rows={2}
          required
        />
      </label>
      {!demandeurEmail && (
        <p className="erreur-inline">Renseignez votre e-mail en haut de page avant de continuer.</p>
      )}
      {erreur && <p className="erreur-inline">{erreur}</p>}
      <button type="submit" disabled={enCours || !demandeurEmail}>
        {enCours ? "Envoi en cours…" : "Demander la validation"}
      </button>
    </form>
  );
}
