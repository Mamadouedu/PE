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

export interface UsageProfile {
  usage_profile_id: string;
  usage_profile_code: string;
  usage_profile_name: string;
  annual_mileage_min_km: number | null;
  annual_mileage_max_km: number | null;
  annual_engine_hours_min: number | null;
  annual_engine_hours_max: number | null;
  monthly_mileage_min_km: number | null;
  monthly_mileage_max_km: number | null;
  utilisation_type: string;
  description: string;
}

export interface MileageBand {
  mileage_band_id: string;
  band_code: string;
  band_name: string;
  min_annual_mileage_km: number;
  max_annual_mileage_km: number | null;
  calculation_method: string;
}

export interface MaintenanceOperation {
  operation_id: string;
  operation_code: string;
  operation_name: string;
  operation_type: string;
  trigger_type: string;
  interval_mileage_km: number | null;
  interval_engine_hours: number | null;
  interval_months: number | null;
  standard_duration_hours: number | null;
  description: string;
}

export interface MaintenancePlan {
  maintenance_plan_id: string;
  plan_code: string;
  plan_name: string;
  manufacturer_id: string | null;
  description: string;
}

export interface EcmProvider {
  ecm_provider_id: string;
  provider_code: string;
  provider_name: string;
  certification_number: string | null;
  description: string;
}

export interface ServiceLevel {
  service_level_id: string;
  service_level_code: string;
  service_level_name: string;
  hotline_included: boolean;
  hotline_coverage: string | null;
  response_time_hours: number | null;
  description: string;
}

export const catalogApi = {
  tree: () => get<FamilyNode[]>("/api/v1/catalog/tree"),
  manufacturers: () => get<Manufacturer[]>("/api/v1/catalog/manufacturers"),
  countries: () => get<Country[]>("/api/v1/catalog/countries"),
  homologations: () => get<any[]>("/api/v1/catalog/homologations"),
  series: () => get<any[]>("/api/v1/catalog/series"),
  variants: (seriesId?: string) =>
    get<any[]>(`/api/v1/catalog/technical-variants${seriesId ? `?series_id=${seriesId}` : ""}`),
  // Lot 2
  usageProfiles: () => get<UsageProfile[]>("/api/v1/catalog/usage-profiles"),
  mileageBands: () => get<MileageBand[]>("/api/v1/catalog/mileage-bands"),
  engineHoursBands: () => get<any[]>("/api/v1/catalog/engine-hours-bands"),
  maintenanceOperations: () => get<MaintenanceOperation[]>("/api/v1/catalog/maintenance-operations"),
  maintenancePlans: () => get<MaintenancePlan[]>("/api/v1/catalog/maintenance-plans"),
  ecmProviders: () => get<EcmProvider[]>("/api/v1/catalog/ecm-providers"),
  serviceLevels: () => get<ServiceLevel[]>("/api/v1/catalog/service-levels"),
};
