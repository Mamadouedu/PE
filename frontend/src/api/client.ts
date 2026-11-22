import type {
  AnomalieQualiteApi,
  ClientRefApi,
  ConfigurationOffre,
  DerogationApi,
  DetailOffreApi,
  ErreurApi,
  JournalEntryApi,
  LocomotiveApi,
  OffreGenereeApi,
  SerieApi,
  VersionDetailApi,
  VersionPublieeApi,
  VersionSummaryApi,
} from "./types";
import { entetesAuth } from "./auth";

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

type MethodeHttp = "GET" | "POST" | "PUT" | "DELETE";

async function appel<T>(
  methode: MethodeHttp,
  chemin: string,
  corps?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { ...entetesAuth() };
  if (corps !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(`${BASE_URL}${chemin}`, {
    method: methode,
    headers,
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  if (!r.ok) await lireErreur(r);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export async function chiffrerOffre(config: ConfigurationOffre): Promise<DetailOffreApi> {
  return appel<DetailOffreApi>("POST", "/api/v1/prix", config);
}

export async function demanderDerogation(
  configuration: ConfigurationOffre,
  justification: string,
): Promise<DerogationApi> {
  return appel<DerogationApi>("POST", "/api/v1/derogations", { configuration, justification });
}

export async function obtenirDerogation(id: number): Promise<DerogationApi> {
  return appel<DerogationApi>("GET", `/api/v1/derogations/${id}`);
}

export interface PdfTelecharge {
  blob: Blob;
  nomFichier: string;
}

export async function telechargerOffrePdf(
  configuration: ConfigurationOffre,
): Promise<PdfTelecharge> {
  const r = await fetch(`${BASE_URL}/api/v1/offres/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...entetesAuth() },
    body: JSON.stringify(configuration),
  });
  if (!r.ok) await lireErreur(r);
  const entete = r.headers.get("content-disposition") ?? "";
  const correspondance = /filename="([^"]+)"/.exec(entete);
  const nomFichier = correspondance?.[1] ?? "offre.pdf";
  return { blob: await r.blob(), nomFichier };
}

export async function listerDerogations(): Promise<DerogationApi[]> {
  return appel<DerogationApi[]>("GET", "/api/v1/derogations");
}

export async function listerOffresGenerees(): Promise<OffreGenereeApi[]> {
  return appel<OffreGenereeApi[]>("GET", "/api/v1/offres");
}

export async function obtenirVersionPubliee(): Promise<VersionPublieeApi | null> {
  const r = await fetch(`${BASE_URL}/api/v1/referentiel/publiee`, { headers: entetesAuth() });
  if (r.status === 404) return null;
  if (!r.ok) await lireErreur(r);
  return (await r.json()) as VersionPublieeApi;
}

export async function obtenirJournalReferentiel(): Promise<JournalEntryApi[]> {
  return appel<JournalEntryApi[]>("GET", "/api/v1/referentiel/journal");
}

/* ---------------- Admin référentiel ---------------- */

export async function listerBrouillons(): Promise<VersionSummaryApi[]> {
  return appel<VersionSummaryApi[]>("GET", "/api/v1/referentiel/brouillons");
}

export async function obtenirVersion(numero: number): Promise<VersionDetailApi> {
  return appel<VersionDetailApi>("GET", `/api/v1/referentiel/brouillons/${numero}`);
}

export async function creerBrouillon(): Promise<{ numero: number; statut: string }> {
  return appel<{ numero: number; statut: string }>("POST", "/api/v1/referentiel/brouillons");
}

export async function definirSerie(numero: number, code: string, serie: SerieApi): Promise<SerieApi> {
  return appel<SerieApi>("PUT", `/api/v1/referentiel/brouillons/${numero}/series/${code}`, {
    serie, raison: "Mise à jour série",
  });
}

export async function supprimerSerie(numero: number, code: string): Promise<void> {
  await appel("DELETE", `/api/v1/referentiel/brouillons/${numero}/series/${code}`);
}

export async function definirClient(numero: number, code: string, client: ClientRefApi): Promise<ClientRefApi> {
  return appel<ClientRefApi>("PUT", `/api/v1/referentiel/brouillons/${numero}/clients/${code}`, client);
}

export async function supprimerClient(numero: number, code: string): Promise<void> {
  await appel("DELETE", `/api/v1/referentiel/brouillons/${numero}/clients/${code}`);
}

export async function definirLocomotive(numero: number, numeroLoco: string, loco: LocomotiveApi): Promise<LocomotiveApi> {
  return appel<LocomotiveApi>("PUT", `/api/v1/referentiel/brouillons/${numero}/flotte/${numeroLoco}`, loco);
}

export async function supprimerLocomotive(numero: number, numeroLoco: string): Promise<void> {
  await appel("DELETE", `/api/v1/referentiel/brouillons/${numero}/flotte/${numeroLoco}`);
}

export async function controlesQualite(numero: number): Promise<AnomalieQualiteApi[]> {
  return appel<AnomalieQualiteApi[]>("GET", `/api/v1/referentiel/brouillons/${numero}/controles-qualite`);
}

export async function publierBrouillon(numero: number): Promise<void> {
  await appel("POST", `/api/v1/referentiel/brouillons/${numero}/publier`);
}

/* ---------------- Admin utilisateurs ---------------- */

export interface UtilisateurAdmin {
  email: string;
  nom: string;
  role: string;
  actif: boolean;
}

export async function listerUtilisateurs(): Promise<UtilisateurAdmin[]> {
  return appel<UtilisateurAdmin[]>("GET", "/api/v1/utilisateurs");
}

export async function creerUtilisateur(
  email: string, nom: string, role: string, motDePasse: string,
): Promise<UtilisateurAdmin> {
  return appel<UtilisateurAdmin>("POST", "/api/v1/utilisateurs", {
    email, nom, role, mot_de_passe: motDePasse,
  });
}

export async function supprimerUtilisateur(email: string): Promise<void> {
  await appel("DELETE", `/api/v1/utilisateurs/${encodeURIComponent(email)}`);
}
