import { useEffect, useState } from "react";
import {
  catalogApi,
  type ChiffrageResponse,
  type CountryGroup,
  type PriceBook,
  type PriceBookVersion,
} from "../api/catalog";

type SousOngletLot3 = "pricebooks" | "pays" | "chiffrage";

export function CatalogueLot3() {
  const [onglet, setOnglet] = useState<SousOngletLot3>("pricebooks");
  return (
    <div>
      <nav className="sous-onglets" style={{ marginBottom: 16 }}>
        <button
          className={`sous-onglet ${onglet === "pricebooks" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("pricebooks")}
        >
          PriceBooks
        </button>
        <button
          className={`sous-onglet ${onglet === "pays" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("pays")}
        >
          Groupes pays & paliers
        </button>
        <button
          className={`sous-onglet ${onglet === "chiffrage" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("chiffrage")}
        >
          Chiffrage v2
        </button>
      </nav>
      {onglet === "pricebooks" && <ListePriceBooks />}
      {onglet === "pays" && <ListePaysEtPaliers />}
      {onglet === "chiffrage" && <Chiffrage />}
    </div>
  );
}

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
}

/* ---------- PriceBooks ---------- */

function ListePriceBooks() {
  const [books, setBooks] = useState<PriceBook[] | null>(null);
  const [versionsMap, setVersionsMap] = useState<Record<string, PriceBookVersion[]>>({});

  useEffect(() => {
    catalogApi.priceBooks().then(async (bs) => {
      setBooks(bs);
      const m: Record<string, PriceBookVersion[]> = {};
      for (const b of bs) {
        m[b.price_book_id] = await catalogApi.priceBookVersions(b.price_book_id);
      }
      setVersionsMap(m);
    });
  }, []);

  if (!books) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Sections 8-11 du doc</strong> : chaque PriceBook versionné est le nouveau référentiel tarifaire. Une version publiée reste en vigueur jusqu'à la suivante. Les offres chiffrées figent leur version d'émission (comme aujourd'hui avec Serie).
      </p>
      {books.map((pb) => (
        <div key={pb.price_book_id} className="price-book-carte">
          <div className="price-book-entete">
            <div>
              <strong className="mono">{pb.price_book_code}</strong>
              <span className="price-book-nom"> — {pb.price_book_name}</span>
              <span className="pastille-mode" style={{ marginLeft: 8 }}>{pb.price_type}</span>
            </div>
            <span style={{ color: "var(--fg-muted)", fontSize: 12 }}>{pb.currency_iso}</span>
          </div>
          <div className="price-book-versions">
            {(versionsMap[pb.price_book_id] ?? []).map((v) => (
              <div key={v.price_book_version_id} className={`price-book-version version-${v.status}`}>
                <strong>{v.year} — v{v.version_number}</strong>
                <span className={`badge-statut badge-${v.status === "published" ? "approuvee" : v.status === "draft" ? "en_attente" : "rejetee"}`}>
                  {v.status}
                </span>
                <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>
                  à partir du {v.valid_from}
                  {v.valid_to ? ` jusqu'au ${v.valid_to}` : ""}
                </span>
                {v.approved_by && (
                  <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>par {v.approved_by}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Pays et paliers ---------- */

function ListePaysEtPaliers() {
  const [groups, setGroups] = useState<CountryGroup[] | null>(null);
  const [leaseBands, setLeaseBands] = useState<any[] | null>(null);
  const [ageBands, setAgeBands] = useState<any[] | null>(null);

  useEffect(() => {
    catalogApi.countryGroups().then(setGroups);
    catalogApi.leaseBands().then(setLeaseBands);
    catalogApi.assetAgeBands().then(setAgeBands);
  }, []);

  if (!groups || !leaseBands || !ageBands) return <p className="registre-vide">Chargement…</p>;
  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        Dimensions tarifaires DL : les prix varient selon le groupe pays × le palier durée × le palier âge de la locomotive.
      </p>

      <h3 className="sous-titre-journal" style={{ marginTop: 16 }}>Groupes pays</h3>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Pays inclus</th><th>Description</th></tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.country_group_id}>
              <td className="mono"><strong>{g.group_code}</strong></td>
              <td>{g.group_name}</td>
              <td>
                <div className="homologations-liste">
                  {g.country_iso_codes.map((iso) => (
                    <span key={iso} className="pastille-pays-mini">{iso}</span>
                  ))}
                </div>
              </td>
              <td style={{ color: "var(--fg-muted)", fontSize: 12.5 }}>{g.description}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Paliers durée</h3>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Min (mois)</th><th>Max (mois)</th></tr>
        </thead>
        <tbody>
          {leaseBands.map((lb) => (
            <tr key={lb.lease_band_id}>
              <td className="mono"><strong>{lb.band_code}</strong></td>
              <td>{lb.band_name}</td>
              <td className="num">{lb.min_duration_months}</td>
              <td className="num">{lb.max_duration_months === null ? "∞" : lb.max_duration_months}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Paliers âge</h3>
      <table className="registre-table">
        <thead>
          <tr><th>Code</th><th>Nom</th><th>Min (ans)</th><th>Max (ans)</th></tr>
        </thead>
        <tbody>
          {ageBands.map((ab) => (
            <tr key={ab.asset_age_band_id}>
              <td className="mono"><strong>{ab.band_code}</strong></td>
              <td>{ab.band_name}</td>
              <td className="num">{ab.min_age_years}</td>
              <td className="num">{ab.max_age_years === null ? "∞" : ab.max_age_years}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- Chiffrage v2 ---------- */

function Chiffrage() {
  const [variants, setVariants] = useState<any[]>([]);
  const [form, setForm] = useState({
    technical_variant_code: "E186-DABNL",
    country_iso: "DE",
    duration_months: 24,
    age_years: 5,
    annual_mileage_km: 150000,
    annual_engine_hours: 0,
  });
  const [res, setRes] = useState<ChiffrageResponse | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    catalogApi.variants().then(setVariants);
  }, []);

  async function chiffrer() {
    setEnCours(true);
    setErreur(null);
    try {
      const r = await catalogApi.chiffrer(form);
      setRes(r);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div>
      <p className="registre-sous-titre" style={{ marginBottom: 12 }}>
        <strong>Moteur v2</strong> : résout les tarifs via PriceBookVersion publiée et applique la formule OM cible du doc (section 11) :
        <code style={{ marginLeft: 8, fontSize: 11 }}>
          OM = MonthlyFixed + (AnnualKm × PricePerKm/12) + (EngineHours × PricePerHour/12) + ECM + LastMile
        </code>
      </p>

      <div className="chiffrage-form">
        <label>
          Variante technique
          <select
            value={form.technical_variant_code}
            onChange={(e) => setForm({ ...form, technical_variant_code: e.target.value })}
          >
            {variants.map((v) => (
              <option key={v.technical_variant_id} value={v.variant_code}>
                {v.variant_code} — {v.variant_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Pays (ISO)
          <input
            type="text"
            maxLength={2}
            value={form.country_iso}
            onChange={(e) => setForm({ ...form, country_iso: e.target.value.toUpperCase() })}
          />
        </label>
        <label>
          Durée (mois)
          <input
            type="number"
            min={1}
            value={form.duration_months}
            onChange={(e) => setForm({ ...form, duration_months: Number(e.target.value) })}
          />
        </label>
        <label>
          Âge (ans)
          <input
            type="number"
            min={0}
            step={0.5}
            value={form.age_years}
            onChange={(e) => setForm({ ...form, age_years: Number(e.target.value) })}
          />
        </label>
        <label>
          Mileage annuel (km)
          <input
            type="number"
            min={0}
            value={form.annual_mileage_km}
            onChange={(e) => setForm({ ...form, annual_mileage_km: Number(e.target.value) })}
          />
        </label>
        <label>
          Heures moteur annuelles
          <input
            type="number"
            min={0}
            value={form.annual_engine_hours}
            onChange={(e) => setForm({ ...form, annual_engine_hours: Number(e.target.value) })}
          />
        </label>
        <button
          type="button"
          className="bouton-principal"
          onClick={chiffrer}
          disabled={enCours}
          style={{ gridColumn: "1 / -1", marginTop: 8 }}
        >
          {enCours ? "Chiffrage en cours…" : "Chiffrer"}
        </button>
      </div>

      {erreur && <div className="erreur" style={{ marginTop: 14 }}>{erreur}</div>}

      {res && (
        <div className="chiffrage-resultat">
          <div className="chiffrage-totaux">
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(res.dl_mensuel)}</div>
              <div className="carte-kpi-libelle">Dry Lease / mois</div>
              <div className="carte-kpi-detail">{res.detail_dl.country_group} · {res.detail_dl.lease_band} · {res.detail_dl.asset_age_band}</div>
            </div>
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(res.hm_mensuel_provisionne)}</div>
              <div className="carte-kpi-libelle">HM provisionnée / mois</div>
              <div className="carte-kpi-detail">{res.detail_hm.length} opérations</div>
            </div>
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(res.om_mensuel)}</div>
              <div className="carte-kpi-libelle">OM / mois</div>
              <div className="carte-kpi-detail">{res.detail_om.mileage_band}</div>
            </div>
            <div className="carte-kpi" style={{ borderColor: "var(--accent)", borderWidth: 2 }}>
              <div className="carte-kpi-valeur" style={{ color: "var(--accent)" }}>{fmt(res.total_mensuel)}</div>
              <div className="carte-kpi-libelle">TOTAL mensuel</div>
              <div className="carte-kpi-detail">
                × {form.duration_months} mois = {fmt(res.total_mensuel * form.duration_months)}
              </div>
            </div>
          </div>

          {res.warnings.length > 0 && (
            <div className="chiffrage-warnings">
              {res.warnings.map((w, i) => (
                <div key={i} className="chiffrage-warning">⚠ {w}</div>
              ))}
            </div>
          )}

          <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Décomposition OM (formule cible)</h3>
          <table className="registre-table">
            <tbody>
              <tr><td>Montant mensuel fixe</td><td className="num">{fmt(res.detail_om.monthly_fixed)}</td></tr>
              <tr><td>Composante kilométrage (km × €/km / 12)</td><td className="num">{fmt(res.detail_om.mileage_component)}</td></tr>
              <tr><td>Composante heures moteur</td><td className="num">{fmt(res.detail_om.engine_hours_component)}</td></tr>
              <tr><td>ECM mensuel</td><td className="num">{fmt(res.detail_om.ecm_monthly)}</td></tr>
              <tr><td>Last-mile mensuel</td><td className="num">{fmt(res.detail_om.last_mile_monthly)}</td></tr>
              <tr><td>Options mensuelles</td><td className="num">{fmt(res.detail_om.options_monthly)}</td></tr>
              {res.detail_om.floor_applied && (
                <tr><td style={{ color: "var(--alerte)" }}>Plancher appliqué</td><td className="num" style={{ color: "var(--alerte)" }}>+{fmt(res.detail_om.floor_applied)}</td></tr>
              )}
              <tr style={{ fontWeight: "bold" }}><td>Total OM mensuel</td><td className="num">{fmt(res.detail_om.total_monthly)}</td></tr>
            </tbody>
          </table>

          <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Provisions HM mensuelles</h3>
          <table className="registre-table">
            <thead>
              <tr><th>Opération</th><th>Prix / opération</th><th>Provision mensuelle</th><th>Méthode</th></tr>
            </thead>
            <tbody>
              {res.detail_hm.map((hm, i) => (
                <tr key={i}>
                  <td className="mono"><strong>{hm.operation_code}</strong></td>
                  <td className="num">{fmt(hm.selling_price_per_operation)}</td>
                  <td className="num">{fmt(hm.monthly_provision)}</td>
                  <td><span className="pastille-mode">{hm.calculation_method}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 16, fontSize: 12, color: "var(--fg-muted)" }}>
            Versions de tarifs utilisées : {Object.entries(res.versions_utilisees).map(([pb, v]) => `${pb} = ${v}`).join(" · ")}
          </div>
        </div>
      )}
    </div>
  );
}
