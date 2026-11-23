import { useEffect, useState } from "react";
import {
  catalogApi,
  type EcmProvider,
  type MaintenanceOperation,
  type MaintenancePlan,
  type MileageBand,
  type ServiceLevel,
  type UsageProfile,
} from "../api/catalog";

type SousOngletLot2 = "profils" | "paliers" | "operations" | "plans" | "ecm" | "service";

export function CatalogueLot2() {
  const [onglet, setOnglet] = useState<SousOngletLot2>("profils");
  return (
    <div>
      <nav className="sous-onglets" style={{ marginBottom: 16 }}>
        {[
          { v: "profils", l: "Profils d'usage" },
          { v: "paliers", l: "Paliers de mileage" },
          { v: "operations", l: "Opérations HM" },
          { v: "plans", l: "Plans de maintenance" },
          { v: "ecm", l: "Fournisseurs ECM" },
          { v: "service", l: "Niveaux de service" },
        ].map((o) => (
          <button
            key={o.v}
            className={`sous-onglet ${onglet === o.v ? "sous-onglet-actif" : ""}`}
            onClick={() => setOnglet(o.v as SousOngletLot2)}
          >
            {o.l}
          </button>
        ))}
      </nav>
      {onglet === "profils" && <ListeProfilsUsage />}
      {onglet === "paliers" && <ListePaliers />}
      {onglet === "operations" && <ListeOperations />}
      {onglet === "plans" && <ListePlans />}
      {onglet === "ecm" && <ListeECM />}
      {onglet === "service" && <ListeServiceLevels />}
    </div>
  );
}

function fmt(n: number | null, unit = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("fr-FR")}${unit ? " " + unit : ""}`;
}

/* ---------- Profils d'usage ---------- */

function ListeProfilsUsage() {
  const [data, setData] = useState<UsageProfile[] | null>(null);
  useEffect(() => { catalogApi.usageProfiles().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Section 5 du doc</strong> : le mileage n'est PAS une propriété fixe de la série. Un profil d'usage borne un intervalle de mileage annuel + heures moteur typique selon le type d'exploitation (fret, voyageurs, manœuvres, last-mile).
      </p>
      <table className="registre-table">
        <thead>
          <tr>
            <th>Code</th><th>Nom</th><th>Type</th><th>Mileage min/max (km/an)</th><th>Heures moteur min/max</th><th>Monthly min/max</th>
          </tr>
        </thead>
        <tbody>
          {data.map((p) => (
            <tr key={p.usage_profile_id}>
              <td className="mono"><strong>{p.usage_profile_code}</strong></td>
              <td>{p.usage_profile_name}</td>
              <td><span className="pastille-mode">{p.utilisation_type}</span></td>
              <td className="num">{fmt(p.annual_mileage_min_km)} - {fmt(p.annual_mileage_max_km, "")}</td>
              <td className="num">{fmt(p.annual_engine_hours_min, "h")} - {fmt(p.annual_engine_hours_max, "h")}</td>
              <td className="num">{fmt(p.monthly_mileage_min_km, "km")} - {fmt(p.monthly_mileage_max_km, "km")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Paliers ---------- */

function ListePaliers() {
  const [bands, setBands] = useState<MileageBand[] | null>(null);
  const [ehBands, setEhBands] = useState<any[] | null>(null);

  useEffect(() => {
    catalogApi.mileageBands().then(setBands);
    catalogApi.engineHoursBands().then(setEhBands);
  }, []);
  if (!bands || !ehBands) return <p className="registre-vide">Chargement…</p>;

  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Section 6 du doc</strong> : les paliers OM sont repris du configurateur Excel réel (80, 120, 160, 200, 240 x 1000 km/an). Chaque palier a une méthode de calcul (linéaire, progressive, flat). Les tarifs eux-mêmes vivent dans PriceBook (Lot 3).
      </p>

      <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Paliers de mileage (OM)</h3>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Min annuel (km)</th><th>Max annuel (km)</th><th>Méthode calcul</th></tr>
        </thead>
        <tbody>
          {bands.map((b) => (
            <tr key={b.mileage_band_id}>
              <td className="mono"><strong>{b.band_code}</strong></td>
              <td>{b.band_name}</td>
              <td className="num">{fmt(b.min_annual_mileage_km)}</td>
              <td className="num">{b.max_annual_mileage_km === null ? "∞" : fmt(b.max_annual_mileage_km)}</td>
              <td><span className="pastille-mode">{b.calculation_method}</span></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="sous-titre-journal" style={{ marginTop: 24 }}>Paliers d'heures moteur</h3>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Min (h/an)</th><th>Max (h/an)</th></tr>
        </thead>
        <tbody>
          {ehBands.map((b) => (
            <tr key={b.engine_hours_band_id}>
              <td className="mono"><strong>{b.band_code}</strong></td>
              <td>{b.band_name}</td>
              <td className="num">{fmt(b.min_annual_engine_hours)}</td>
              <td className="num">{b.max_annual_engine_hours === null ? "∞" : fmt(b.max_annual_engine_hours)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Opérations HM ---------- */

function ListeOperations() {
  const [data, setData] = useState<MaintenanceOperation[] | null>(null);
  useEffect(() => { catalogApi.maintenanceOperations().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Section 10 du doc</strong> : chaque opération HM a un déclencheur (mileage, engine hours, calendar, mixed) et des intervalles. HM-1 à 600 000 km, HM-2 à 1 200 000 km, HM-3 à 1 800 000 km, échange bogies à 2 400 000 km.
      </p>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Type</th><th>Déclencheur</th><th>Intervalle km</th><th>Intervalle heures</th><th>Intervalle mois</th><th>Durée moyenne</th></tr>
        </thead>
        <tbody>
          {data.map((o) => (
            <tr key={o.operation_id}>
              <td className="mono"><strong>{o.operation_code}</strong></td>
              <td>{o.operation_name}</td>
              <td><span className="pastille-mode">{o.operation_type}</span></td>
              <td><span className="pastille-homo">{o.trigger_type}</span></td>
              <td className="num">{fmt(o.interval_mileage_km, "km")}</td>
              <td className="num">{fmt(o.interval_engine_hours, "h")}</td>
              <td className="num">{fmt(o.interval_months, "mois")}</td>
              <td className="num">{fmt(o.standard_duration_hours, "h")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Plans ---------- */

function ListePlans() {
  const [data, setData] = useState<MaintenancePlan[] | null>(null);
  const [plansOps, setPlansOps] = useState<Record<string, MaintenanceOperation[]>>({});
  useEffect(() => {
    catalogApi.maintenancePlans().then(async (plans) => {
      setData(plans);
      const map: Record<string, MaintenanceOperation[]> = {};
      for (const p of plans) {
        const r = await fetch(`${(import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000")}/api/v1/catalog/maintenance-plans/${p.maintenance_plan_id}/operations`);
        map[p.maintenance_plan_id] = await r.json();
      }
      setPlansOps(map);
    });
  }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        Un plan regroupe les opérations qui s'appliquent à une famille de variantes. Le plan par défaut d'une variante est automatiquement celui de son constructeur.
      </p>
      {data.map((plan) => (
        <div key={plan.maintenance_plan_id} className="plan-maintenance">
          <h4>
            <span className="mono"><strong>{plan.plan_code}</strong></span> — {plan.plan_name}
          </h4>
          <div className="plan-ops">
            {(plansOps[plan.maintenance_plan_id] ?? []).map((op) => (
              <span key={op.operation_id} className="pastille-homo" title={op.operation_name}>
                {op.operation_code}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- ECM Providers ---------- */

function ListeECM() {
  const [data, setData] = useState<EcmProvider[] | null>(null);
  useEffect(() => { catalogApi.ecmProviders().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Règlement UE 445/2011</strong> : chaque locomotive doit avoir une Entité en Charge de la Maintenance (ECM) certifiée. AMS = ECM interne Akiem.
      </p>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>N° certification</th><th>Description</th></tr>
        </thead>
        <tbody>
          {data.map((e) => (
            <tr key={e.ecm_provider_id}>
              <td className="mono"><strong>{e.provider_code}</strong></td>
              <td>{e.provider_name}</td>
              <td className="mono">{e.certification_number ?? "—"}</td>
              <td style={{ color: "var(--fg-muted)", fontSize: 12.5 }}>{e.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Service Levels ---------- */

function ListeServiceLevels() {
  const [data, setData] = useState<ServiceLevel[] | null>(null);
  useEffect(() => { catalogApi.serviceLevels().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        Niveau de service inclus dans un contrat : hotline, couverture horaire, temps de réponse garanti (RTO).
      </p>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Hotline</th><th>Couverture</th><th>RTO</th><th>Description</th></tr>
        </thead>
        <tbody>
          {data.map((s) => (
            <tr key={s.service_level_id}>
              <td className="mono"><strong>{s.service_level_code}</strong></td>
              <td>{s.service_level_name}</td>
              <td>{s.hotline_included ? "✓" : "—"}</td>
              <td className="mono">{s.hotline_coverage ?? "—"}</td>
              <td className="num">{s.response_time_hours ? `${s.response_time_hours}h` : "—"}</td>
              <td style={{ color: "var(--fg-muted)", fontSize: 12.5 }}>{s.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
