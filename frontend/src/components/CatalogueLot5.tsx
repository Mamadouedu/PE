import { useEffect, useState } from "react";
import { catalogApi } from "../api/catalog";

const LIBELLE_STATUT_OP: Record<string, string> = {
  available: "Disponible",
  leased: "Louée",
  in_maintenance: "En maintenance",
  stored: "Immobilisée",
  decommissioned: "Déclassée",
};

const COULEUR_STATUT_OP: Record<string, string> = {
  available: "approuvee",
  leased: "en_attente",
  in_maintenance: "en_attente",
  stored: "rejetee",
  decommissioned: "rejetee",
};

const LIBELLE_OWNERSHIP: Record<string, string> = {
  owned: "Akiem propriétaire",
  leased_in: "Sous-louée",
  partner: "Partenariat",
};

function fmtKm(n: number): string {
  return `${n.toLocaleString("fr-FR")} km`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

export function CatalogueLot5() {
  const [assets, setAssets] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [filtreStatut, setFiltreStatut] = useState<string>("");
  const [erreur, setErreur] = useState<string | null>(null);

  async function rafraichir() {
    try {
      const data = await catalogApi.fleetAssets(undefined, filtreStatut || undefined);
      setAssets(data);
    } catch (e) {
      setErreur(String(e));
    }
  }

  useEffect(() => {
    void rafraichir();
  }, [filtreStatut]);

  if (selected) {
    return <FleetAssetDetail assetId={selected} onBack={() => setSelected(null)} />;
  }

  if (!assets) return <p className="registre-vide">Chargement…</p>;

  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Section 12 du doc</strong> : la flotte physique réelle. Chaque locomotive est identifiée par son numéro UIC
        (ex. <code>91 80 6186 201-9 D-AKIEM</code>), typée par sa variante technique, et suivie par ses relevés compteurs
        et son historique de maintenance. Un deal peut cibler une loco précise (QuoteLine → FleetAsset) ou rester générique
        (variante seule).
      </p>

      <div className="barre-filtres">
        <span style={{ fontSize: 12.5, color: "var(--fg-muted)" }}>Statut opérationnel :</span>
        <select
          value={filtreStatut}
          onChange={(e) => setFiltreStatut(e.target.value)}
          style={{ padding: "6px 10px" }}
        >
          <option value="">Tous</option>
          <option value="available">Disponible</option>
          <option value="leased">Louée</option>
          <option value="in_maintenance">En maintenance</option>
          <option value="stored">Immobilisée</option>
          <option value="decommissioned">Déclassée</option>
        </select>
        <span className="compteur-resultats">{assets.length} loco{assets.length > 1 ? "s" : ""}</span>
      </div>

      {erreur && <div className="erreur">{erreur}</div>}

      <table className="registre-table clickable">
        <thead>
          <tr>
            <th>Asset #</th>
            <th>N° UIC</th>
            <th>Variante</th>
            <th>Année</th>
            <th>Km cumulés</th>
            <th>Statut</th>
            <th>Propriété</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a) => (
            <tr key={a.fleet_asset_id} onClick={() => setSelected(a.fleet_asset_id)}>
              <td className="mono"><strong>{a.asset_number}</strong></td>
              <td className="mono" style={{ fontSize: 11.5 }}>{a.vehicle_registration_number}</td>
              <td className="mono">
                {/* On va afficher via summary dans la vue détail */}
                <VariantCode variantId={a.technical_variant_id} />
              </td>
              <td className="num">{a.manufacturing_year}</td>
              <td className="num">{fmtKm(a.current_mileage_km)}</td>
              <td>
                <span className={`badge-statut badge-${COULEUR_STATUT_OP[a.operational_status]}`}>
                  {LIBELLE_STATUT_OP[a.operational_status]}
                </span>
              </td>
              <td style={{ fontSize: 12.5 }}>{LIBELLE_OWNERSHIP[a.ownership_status]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* --- Asset detail --- */

function VariantCode({ variantId }: { variantId: string }) {
  const [code, setCode] = useState<string>("…");
  useEffect(() => {
    catalogApi.variants().then((all) => {
      const v = all.find((x: any) => x.technical_variant_id === variantId);
      setCode(v?.variant_code ?? "?");
    });
  }, [variantId]);
  return <>{code}</>;
}

function FleetAssetDetail({ assetId, onBack }: { assetId: string; onBack: () => void }) {
  const [summary, setSummary] = useState<any>(null);
  const [readings, setReadings] = useState<any[] | null>(null);
  const [history, setHistory] = useState<any[] | null>(null);

  useEffect(() => {
    catalogApi.fleetAssetSummary(assetId).then(setSummary);
    catalogApi.fleetAssetMeterReadings(assetId).then(setReadings);
    catalogApi.fleetAssetMaintenanceHistory(assetId).then(setHistory);
  }, [assetId]);

  if (!summary) return <p className="registre-vide">Chargement…</p>;

  return (
    <div>
      <button type="button" className="bouton-secondaire" onClick={onBack} style={{ marginBottom: 12 }}>
        ← Retour à la liste
      </button>

      <h2>
        <span className="mono">{summary.asset_number}</span> — {summary.technical_variant_code}
      </h2>
      <p className="registre-sous-titre">
        <code>{summary.vehicle_registration_number}</code> · Mise en service {fmtDate(summary.commissioning_date)}
        · Pays courant <strong>{summary.current_country_iso ?? "—"}</strong>
      </p>

      <div className="cartes-kpi">
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{fmtKm(summary.current_mileage_km)}</div>
          <div className="carte-kpi-libelle">Km cumulés</div>
          <div className="carte-kpi-detail">dernier relevé</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{summary.age_years.toFixed(1)} ans</div>
          <div className="carte-kpi-libelle">Âge</div>
          <div className="carte-kpi-detail">Mfg {summary.manufacturing_year}</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{summary.km_until_next_hm ? fmtKm(summary.km_until_next_hm) : "—"}</div>
          <div className="carte-kpi-libelle">Avant prochaine HM</div>
          <div className="carte-kpi-detail">HM2 à {summary.next_hm2_due_km ? fmtKm(summary.next_hm2_due_km) : "—"}</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{summary.current_engine_hours.toLocaleString("fr-FR")} h</div>
          <div className="carte-kpi-libelle">Heures moteur</div>
          <div className="carte-kpi-detail">Pour les dual-mode</div>
        </div>
      </div>

      <h3 className="sous-titre-journal" style={{ marginTop: 24 }}>Relevés compteurs</h3>
      {readings === null ? (
        <p className="registre-vide">Chargement…</p>
      ) : readings.length === 0 ? (
        <p className="registre-vide">Aucun relevé.</p>
      ) : (
        <table className="registre-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Km</th>
              <th>Heures moteur</th>
              <th>Pays</th>
              <th>Source</th>
              <th>Relevé par</th>
            </tr>
          </thead>
          <tbody>
            {readings.map((r) => (
              <tr key={r.meter_reading_id}>
                <td>{fmtDate(r.reading_date)}</td>
                <td className="num">{fmtKm(r.mileage_km)}</td>
                <td className="num">{r.engine_hours.toLocaleString("fr-FR")} h</td>
                <td className="mono">{r.country_iso ?? "—"}</td>
                <td><span className="pastille-mode">{r.source}</span></td>
                <td style={{ fontSize: 12.5 }}>{r.recorded_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 className="sous-titre-journal" style={{ marginTop: 24 }}>Historique maintenance</h3>
      {history === null ? (
        <p className="registre-vide">Chargement…</p>
      ) : history.length === 0 ? (
        <p className="registre-vide">Aucune intervention.</p>
      ) : (
        <table className="registre-table">
          <thead>
            <tr>
              <th>Opération</th>
              <th>Statut</th>
              <th>Date</th>
              <th>Km</th>
              <th>Atelier</th>
              <th>Montant facturé</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.maintenance_history_id}>
                <td className="mono"><strong>{h.operation_code}</strong></td>
                <td>
                  <span className={`badge-statut badge-${h.status === "completed" ? "approuvee" : "en_attente"}`}>
                    {h.status}
                  </span>
                </td>
                <td>{fmtDate(h.completed_at ?? h.planned_date)}</td>
                <td className="num">{h.mileage_km_at_event ? fmtKm(h.mileage_km_at_event) : "—"}</td>
                <td>
                  {h.workshop_name}
                  {h.workshop_country_iso && <span className="pastille-pays-mini" style={{ marginLeft: 6 }}>{h.workshop_country_iso}</span>}
                </td>
                <td className="num">
                  {h.billed_amount ? h.billed_amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
