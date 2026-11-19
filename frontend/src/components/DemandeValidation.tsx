import { useEffect, useRef, useState } from "react";
import { ApiError, demanderDerogation, obtenirDerogation } from "../api/client";
import type { ApprovalRequestResponse, ApprovalStatus } from "../api/types";

const INTERVALLE_SONDAGE_MS = 4000;

// Les classes CSS (statut-en_attente, etc.) datent du prototype Python —
// on y ramène les valeurs `ApprovalStatus` de l'API .NET ici plutôt que de
// réécrire App.css.
const SLUG_STATUT: Record<ApprovalStatus, string> = {
  Pending: "en_attente",
  Approved: "approuvee",
  Rejected: "rejetee",
};

const LIBELLE_STATUT: Record<ApprovalStatus, string> = {
  Pending: "En attente de décision",
  Approved: "Approuvée",
  Rejected: "Rejetée",
};

interface Props {
  libelleNiveau: string;
  quoteId: string;
  versionNumber: number;
  demandeurEmail: string;
}

export function DemandeValidation({ libelleNiveau, quoteId, versionNumber, demandeurEmail }: Props) {
  const [justification, setJustification] = useState("");
  const [derogation, setDerogation] = useState<ApprovalRequestResponse | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const intervalleRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Remet tout à zéro si l'offre change de version : une dérogation ne
    // vaut que pour la version exacte qui l'a déclenchée (M4-04).
    setDerogation(null);
    setErreur(null);
  }, [quoteId, versionNumber]);

  useEffect(() => {
    if (!derogation || derogation.status !== "Pending") {
      if (intervalleRef.current) clearInterval(intervalleRef.current);
      return;
    }
    intervalleRef.current = setInterval(async () => {
      try {
        const miseAJour = await obtenirDerogation(derogation.number);
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
  }, [derogation?.number, derogation?.status]);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const creee = await demanderDerogation(quoteId, demandeurEmail, justification);
      setDerogation(creee);
    } catch (e) {
      setErreur(e instanceof ApiError ? String(e.detail) : "Impossible de joindre l'API de pricing.");
    } finally {
      setEnCours(false);
    }
  }

  if (derogation) {
    return (
      <div className={`demande-validation statut-${SLUG_STATUT[derogation.status]}`}>
        <p className="demande-statut">{LIBELLE_STATUT[derogation.status]}</p>
        <p className="demande-detail">
          Demandé par {derogation.requestedBy}
          {derogation.validatorEmail && <> — en attente de {derogation.validatorEmail}</>}
        </p>
        {derogation.status === "Pending" && (
          <p className="demande-detail aide">Vérification automatique toutes les 4 secondes…</p>
        )}
        {derogation.decidedAt && (
          <p className="demande-detail">
            Décidé par {derogation.decidedBy} le{" "}
            {new Date(derogation.decidedAt).toLocaleString("fr-FR")}
            {derogation.decisionComment && <> — « {derogation.decisionComment} »</>}
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
