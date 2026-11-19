import type { ConfigurationOffre, DetailOffreApi, ErreurApi } from "./types";

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

export async function chiffrerOffre(config: ConfigurationOffre): Promise<DetailOffreApi> {
  const reponse = await fetch(`${BASE_URL}/api/v1/prix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });

  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({ detail: reponse.statusText }))) as ErreurApi;
    throw new ApiError(reponse.status, corps.detail);
  }

  return (await reponse.json()) as DetailOffreApi;
}
