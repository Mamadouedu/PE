const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const STORAGE_KEY = "akiem_auth";

export type Role = "KAM" | "PRICING" | "DIRECTION" | "ADMIN";

export interface UtilisateurConnecte {
  email: string;
  nom: string;
  role: Role;
  permissions: string[];
}

export interface Session {
  token: string;
  utilisateur: UtilisateurConnecte;
}

let sessionCourante: Session | null = chargerSessionLocale();

export function sessionActive(): Session | null {
  return sessionCourante;
}

export function aPermission(p: string): boolean {
  return sessionCourante?.utilisateur.permissions.includes(p) ?? false;
}

export function entetesAuth(): Record<string, string> {
  const s = sessionCourante;
  if (s) return { Authorization: `Bearer ${s.token}` };
  return {};
}

function chargerSessionLocale(): Session | null {
  try {
    const brut = localStorage.getItem(STORAGE_KEY);
    if (!brut) return null;
    return JSON.parse(brut) as Session;
  } catch {
    return null;
  }
}

function sauverSessionLocale(s: Session | null) {
  try {
    if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // quota ou mode privé : tant pis, la session vit en mémoire
  }
}

export async function login(email: string, motDePasse: string): Promise<Session> {
  const r = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, mot_de_passe: motDePasse }),
  });
  if (!r.ok) {
    const corps = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(typeof corps.detail === "string" ? corps.detail : "Échec de connexion");
  }
  const data = (await r.json()) as { token: string; utilisateur: UtilisateurConnecte };
  const session: Session = { token: data.token, utilisateur: data.utilisateur };
  sessionCourante = session;
  sauverSessionLocale(session);
  return session;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: entetesAuth(),
    });
  } catch {
    // on nettoie quand même la session locale
  }
  sessionCourante = null;
  sauverSessionLocale(null);
}

export async function rafraichirMe(): Promise<UtilisateurConnecte | null> {
  if (!sessionCourante) return null;
  try {
    const r = await fetch(`${BASE_URL}/api/v1/auth/me`, { headers: entetesAuth() });
    if (!r.ok) {
      sessionCourante = null;
      sauverSessionLocale(null);
      return null;
    }
    const u = (await r.json()) as UtilisateurConnecte;
    sessionCourante = { token: sessionCourante.token, utilisateur: u };
    sauverSessionLocale(sessionCourante);
    return u;
  } catch {
    return null;
  }
}

export async function changerMotDePasse(ancien: string, nouveau: string): Promise<void> {
  const r = await fetch(`${BASE_URL}/api/v1/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...entetesAuth() },
    body: JSON.stringify({ ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau }),
  });
  if (!r.ok) {
    const corps = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(typeof corps.detail === "string" ? corps.detail : "Échec");
  }
}
