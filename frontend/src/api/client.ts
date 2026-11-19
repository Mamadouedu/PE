import type {
  ApprovalRequestResponse,
  CalculateQuoteRequest,
  CampaignResponse,
  ErreurApi,
  ModelSummaryResponse,
  QuoteResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5067";

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
  const corps = (await reponse.json().catch(() => ({ error: reponse.statusText }))) as ErreurApi;
  throw new ApiError(reponse.status, corps.error);
}

export async function listerModeles(): Promise<ModelSummaryResponse[]> {
  const reponse = await fetch(`${BASE_URL}/api/models`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as ModelSummaryResponse[];
}

export async function listerCampagnes(): Promise<CampaignResponse[]> {
  const reponse = await fetch(`${BASE_URL}/api/campaigns`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as CampaignResponse[];
}

export async function chiffrerOffre(requete: CalculateQuoteRequest): Promise<QuoteResponse> {
  const reponse = await fetch(`${BASE_URL}/api/quotes/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requete),
  });

  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as QuoteResponse;
}

// M4-02 : la justification est obligatoire côté API. La dérogation est
// toujours demandée pour la version COURANTE de l'offre déjà calculée
// (`quoteId`) — le back-end .NET ne recalcule rien.
export async function demanderDerogation(
  quoteId: string,
  requestedBy: string,
  justification: string,
): Promise<ApprovalRequestResponse> {
  const reponse = await fetch(`${BASE_URL}/api/approval-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quoteId, requestedBy, justification }),
  });

  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as ApprovalRequestResponse;
}

export async function obtenirDerogation(number: number): Promise<ApprovalRequestResponse> {
  const reponse = await fetch(`${BASE_URL}/api/approval-requests/${number}`);
  if (!reponse.ok) await lireErreur(reponse);
  return (await reponse.json()) as ApprovalRequestResponse;
}
