import { useEffect, useMemo, useState } from "react";
import { catalogApi, type FamilyNode, type PlatformNode, type SeriesNode, type VariantNode, type Country, type Manufacturer } from "../api/catalog";
import { CatalogueLot2 } from "./CatalogueLot2";
import { CatalogueLot3 } from "./CatalogueLot3";

type OngletCatalogue = "hierarchie" | "constructeurs" | "pays" | "homologations" | "usage_maintenance" | "tarifs";

export function Catalogue() {
  const [onglet, setOnglet] = useState<OngletCatalogue>("hierarchie");

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <h2>Catalogue PricingHub</h2>
          <p className="registre-sous-titre">
            Référentiel locomotive hiérarchique (Lot 1 Architecture Cible) :
            <strong> ProductFamily → ProductPlatform → LocomotiveSeries → TechnicalVariant</strong>,
            homologations M2M, pays et réseaux. La structure stricte évite la confusion série/sous-série/homologation du configurateur Excel actuel.
          </p>
        </div>
      </header>

      <nav className="sous-onglets" style={{ marginBottom: 16 }}>
        <button
          className={`sous-onglet ${onglet === "hierarchie" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("hierarchie")}
        >
          Hiérarchie
        </button>
        <button
          className={`sous-onglet ${onglet === "constructeurs" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("constructeurs")}
        >
          Constructeurs
        </button>
        <button
          className={`sous-onglet ${onglet === "pays" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("pays")}
        >
          Pays & réseaux
        </button>
        <button
          className={`sous-onglet ${onglet === "homologations" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("homologations")}
        >
          Homologations
        </button>
        <button
          className={`sous-onglet ${onglet === "usage_maintenance" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("usage_maintenance")}
        >
          Usage & maintenance
        </button>
        <button
          className={`sous-onglet ${onglet === "tarifs" ? "sous-onglet-actif" : ""}`}
          onClick={() => setOnglet("tarifs")}
        >
          Tarifs & chiffrage v2
        </button>
      </nav>

      {onglet === "hierarchie" && <ArbreHierarchie />}
      {onglet === "constructeurs" && <ListeConstructeurs />}
      {onglet === "pays" && <ListePays />}
      {onglet === "homologations" && <ListeHomologations />}
      {onglet === "usage_maintenance" && <CatalogueLot2 />}
      {onglet === "tarifs" && <CatalogueLot3 />}
    </section>
  );
}

/* ------------------------- Arbre hiérarchique ------------------------- */

function ArbreHierarchie() {
  const [tree, setTree] = useState<FamilyNode[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [recherche, setRecherche] = useState("");

  useEffect(() => {
    catalogApi.tree().then(setTree).catch((e) => setErreur(String(e)));
  }, []);

  const filtre = recherche.trim().toLowerCase();

  function matchVariant(v: VariantNode): boolean {
    if (!filtre) return true;
    const texte = `${v.variant_code} ${v.variant_name} ${v.manufacturer_model_name} ${v.homologations.map(h => h.code).join(" ")}`.toLowerCase();
    return texte.includes(filtre);
  }
  function matchSeries(s: SeriesNode): boolean {
    if (!filtre) return true;
    if (s.series_code.toLowerCase().includes(filtre) || s.series_name.toLowerCase().includes(filtre)) return true;
    return s.variants.some(matchVariant);
  }
  function matchPlatform(p: PlatformNode): boolean {
    if (!filtre) return true;
    if (p.platform_code.toLowerCase().includes(filtre) || p.platform_name.toLowerCase().includes(filtre)) return true;
    return p.series.some(matchSeries);
  }

  const treeFiltre = useMemo(() => {
    if (!tree) return [];
    return tree
      .map((f) => ({ ...f, platforms: f.platforms.filter(matchPlatform) }))
      .filter((f) => f.platforms.length > 0);
  }, [tree, filtre]);

  if (erreur) return <div className="erreur">{erreur}</div>;
  if (tree === null) return <p className="registre-vide">Chargement du catalogue…</p>;

  return (
    <div>
      <div className="barre-filtres">
        <input
          type="search"
          className="input-recherche"
          placeholder="Chercher variante, série, plateforme, homologation (TRAXX, E186, DABNL...)"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
        />
      </div>

      {treeFiltre.length === 0 && <p className="registre-vide">Aucun résultat.</p>}

      <div className="arbre-catalogue">
        {treeFiltre.map((f) => (
          <FamilleNode key={f.product_family_id} family={f} />
        ))}
      </div>
    </div>
  );
}

function FamilleNode({ family }: { family: FamilyNode }) {
  const [deplie, setDeplie] = useState(true);
  return (
    <div className="noeud-famille">
      <button className="noeud-toggle" onClick={() => setDeplie((d) => !d)}>
        <span className="noeud-chevron">{deplie ? "▼" : "▶"}</span>
        <span className="noeud-emoji">🏭</span>
        <strong>{family.family_name}</strong>
        <span className="noeud-compteur">{family.platforms.length} plateforme{family.platforms.length > 1 ? "s" : ""}</span>
      </button>
      {deplie && (
        <div className="noeud-enfants">
          {family.platforms.map((p) => (
            <PlateformeNode key={p.product_platform_id} platform={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlateformeNode({ platform }: { platform: PlatformNode }) {
  const [deplie, setDeplie] = useState(false);
  return (
    <div className="noeud-plateforme">
      <button className="noeud-toggle" onClick={() => setDeplie((d) => !d)}>
        <span className="noeud-chevron">{deplie ? "▼" : "▶"}</span>
        <span className="noeud-emoji">🚆</span>
        <strong>{platform.platform_name}</strong>
        <span className="pastille-mode">{platform.traction_mode}</span>
        <span className="noeud-compteur">{platform.series.length} série{platform.series.length > 1 ? "s" : ""}</span>
      </button>
      {deplie && (
        <div className="noeud-enfants">
          {platform.series.map((s) => (
            <SerieNode key={s.series_id} serie={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SerieNode({ serie }: { serie: SeriesNode }) {
  const [deplie, setDeplie] = useState(false);
  return (
    <div className="noeud-serie">
      <button className="noeud-toggle" onClick={() => setDeplie((d) => !d)}>
        <span className="noeud-chevron">{deplie ? "▼" : "▶"}</span>
        <span className="noeud-emoji">⚡</span>
        <strong>{serie.series_code}</strong>
        <span className="serie-detail">
          {serie.nominal_power_kw ? `${serie.nominal_power_kw.toLocaleString("fr-FR")} kW` : "—"} ·{" "}
          {serie.maximum_speed_kmh ? `${serie.maximum_speed_kmh} km/h` : "—"} ·{" "}
          {serie.starting_tractive_effort_kn ? `${serie.starting_tractive_effort_kn} kN` : "—"}
        </span>
        <span className="noeud-compteur">{serie.variants.length} variante{serie.variants.length > 1 ? "s" : ""}</span>
      </button>
      {deplie && (
        <div className="noeud-enfants">
          {serie.variants.map((v) => (
            <VarianteNode key={v.technical_variant_id} variante={v} />
          ))}
        </div>
      )}
    </div>
  );
}

function VarianteNode({ variante }: { variante: VariantNode }) {
  return (
    <div className="noeud-variante">
      <span className="noeud-emoji">🔖</span>
      <div style={{ flex: 1 }}>
        <div>
          <strong className="variante-code">{variante.variant_code}</strong>
          <span className="variante-nom"> — {variante.variant_name}</span>
        </div>
        <div className="variante-model">{variante.manufacturer_model_name}</div>
        <div className="variante-homos">
          {variante.homologations.map((h) => (
            <span key={h.code} className="pastille-homo" title={h.name}>
              {h.code}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------- Constructeurs ------------------------- */

function ListeConstructeurs() {
  const [data, setData] = useState<Manufacturer[] | null>(null);
  useEffect(() => { catalogApi.manufacturers().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <table className="registre-table">
      <thead>
        <tr><th>Code</th><th>Nom</th><th>Pays d'origine</th><th>Société mère</th><th>Statut</th></tr>
      </thead>
      <tbody>
        {data.map((m) => (
          <tr key={m.manufacturer_id}>
            <td className="mono">{m.code}</td>
            <td><strong>{m.name}</strong></td>
            <td>{m.country_of_origin_iso}</td>
            <td>{m.parent_company ?? "—"}</td>
            <td>{m.statut}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------- Pays ------------------------- */

function ListePays() {
  const [data, setData] = useState<Country[] | null>(null);
  useEffect(() => { catalogApi.countries().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <table className="registre-table">
      <thead>
        <tr><th>ISO</th><th>Nom (FR)</th><th>Nom (EN)</th><th>Réseau par défaut</th><th>UE</th></tr>
      </thead>
      <tbody>
        {data.map((c) => (
          <tr key={c.country_id}>
            <td className="mono">{c.iso_alpha2}</td>
            <td><strong>{c.name_fr}</strong></td>
            <td>{c.name_en}</td>
            <td className="mono">{c.default_network_code ?? "—"}</td>
            <td>{c.is_eu_member ? "✓" : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------- Homologations ------------------------- */

function ListeHomologations() {
  const [data, setData] = useState<any[] | null>(null);
  useEffect(() => { catalogApi.homologations().then(setData); }, []);
  if (!data) return <p className="registre-vide">Chargement…</p>;
  return (
    <table className="registre-table">
      <thead>
        <tr><th>Code</th><th>Nom</th><th>Description</th><th>Statut</th></tr>
      </thead>
      <tbody>
        {data.map((h) => (
          <tr key={h.homologation_id}>
            <td className="mono"><strong>{h.homologation_code}</strong></td>
            <td>{h.homologation_name}</td>
            <td style={{ color: "var(--fg-muted)", fontSize: 12.5 }}>{h.description}</td>
            <td>
              <span className={`badge-statut badge-${h.status === "approved" ? "approuvee" : h.status === "expired" ? "rejetee" : "en_attente"}`}>
                {h.status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
