import { entetesAuth } from "./auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface Homologation {
  code: string;
  name: string;
}

export interface VariantNode {
  technical_variant_id: string;
  variant_code: string;
  variant_name: string;
  manufacturer_model_name: string;
  homologations: Homologation[];
}

export interface SeriesNode {
  series_id: string;
  series_code: string;
  series_name: string;
  nominal_power_kw: number | null;
  maximum_speed_kmh: number | null;
  starting_tractive_effort_kn: number | null;
  variants: VariantNode[];
}

export interface PlatformNode {
  product_platform_id: string;
  platform_code: string;
  platform_name: string;
  traction_mode: string;
  series: SeriesNode[];
}

export interface FamilyNode {
  product_family_id: string;
  family_code: string;
  family_name: string;
  platforms: PlatformNode[];
}

export interface Country {
  country_id: string;
  iso_alpha2: string;
  name_fr: string;
  name_en: string;
  default_network_code: string | null;
  is_eu_member: boolean;
  is_active: boolean;
}

export interface Manufacturer {
  manufacturer_id: string;
  code: string;
  name: string;
  country_of_origin_iso: string;
  parent_company: string | null;
  statut: string;
  is_active: boolean;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE_URL}${path}`, { headers: entetesAuth() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as T;
}

export const catalogApi = {
  tree: () => get<FamilyNode[]>("/api/v1/catalog/tree"),
  manufacturers: () => get<Manufacturer[]>("/api/v1/catalog/manufacturers"),
  countries: () => get<Country[]>("/api/v1/catalog/countries"),
  homologations: () => get<any[]>("/api/v1/catalog/homologations"),
  series: () => get<any[]>("/api/v1/catalog/series"),
  variants: (seriesId?: string) =>
    get<any[]>(`/api/v1/catalog/technical-variants${seriesId ? `?series_id=${seriesId}` : ""}`),
};
