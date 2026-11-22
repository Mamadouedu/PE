import type {
  ConfigurationOffre,
  DerogationApi,
  DetailOffreApi,
  ErreurApi,
  JournalEntryApi,
  OffreGenereeApi,
  VersionPublieeApi,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function lireErreur(reponse: Response): Promise<never> {
  const corps = (await reponse.json().catch(() => ({ detail: reponse.statusText }))) as ErreurApi;
  throw new ApiError(reponse.status, corps.detail);
}

export async function chiffrerOffre(config: ConfigurationOffre): Promise<DetailOffreApi> {
  const reponse = await fetch(`${BASE_URL}/api/v1/prix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as DetailOffreApi;
}

// M4-02 : la justification est obligatoire côté API (elle refuse une chaîne
// vide) ; `demandeur` identifie le KAM tant qu'il n'y a pas d'authentification.
export async function demanderDerogation(
  configuration: ConfigurationOffre,
  justification: string,
  demandeur: string,
): Promise<DerogationApi> {
  const reponse = await fetch(`${BASE_URL}/api/v1/derogations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Utilisateur": demandeur },
    body: JSON.stringify({ configuration, justification }),
  });

  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as DerogationApi;
}

export async function obtenirDerogation(id: number): Promise<DerogationApi> {
  const reponse = await fetch(`${BASE_URL}/api/v1/derogations/${id}`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as DerogationApi;
}

export interface PdfTelecharge {
  blob: Blob;
  nomFichier: string;
}

// M3-05 : le PDF ne montre jamais catalogue/plancher/contrôles, seulement
// le prix retenu (voir offre_pdf.py côté API) ; `demandeur` identifie le
// KAM tant qu'il n'y a pas d'authentification.
export async function telechargerOffrePdf(
  configuration: ConfigurationOffre,
  demandeur: string,
): Promise<PdfTelecharge> {
  const reponse = await fetch(`${BASE_URL}/api/v1/offres/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Utilisateur": demandeur },
    body: JSON.stringify(configuration),
  });

  if (!reponse.ok) await lireErreur(reponse);

  const entete = reponse.headers.get("content-disposition") ?? "";
  const correspondance = /filename="([^"]+)"/.exec(entete);
  const nomFichier = correspondance?.[1] ?? "offre.pdf";

  return { blob: await reponse.blob(), nomFichier };
}

export async function listerDerogations(): Promise<DerogationApi[]> {
  const reponse = await fetch(`${BASE_URL}/api/v1/derogations`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as DerogationApi[];
}

export async function listerOffresGenerees(): Promise<OffreGenereeApi[]> {
  const reponse = await fetch(`${BASE_URL}/api/v1/offres`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as OffreGenereeApi[];
}

export async function obtenirVersionPubliee(): Promise<VersionPublieeApi | null> {
  const reponse = await fetch(`${BASE_URL}/api/v1/referentiel/publiee`);
  if (reponse.status === 404) return null;
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as VersionPublieeApi;
}

export async function obtenirJournalReferentiel(): Promise<JournalEntryApi[]> {
  const reponse = await fetch(`${BASE_URL}/api/v1/referentiel/journal`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as JournalEntryApi[];
}
