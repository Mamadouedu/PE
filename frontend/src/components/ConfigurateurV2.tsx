import { useEffect, useState } from "react";
import { catalogApi } from "../api/catalog";
import { sessionActive, aPermission } from "../api/auth";

const PAYS_ISO = [
  "DE", "AT", "CH", "IT", "FR", "PL", "CZ", "SK", "HU", "RO",
  "NL", "BE", "LU", "DK", "SE", "NO", "UK",
];

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

const LIBELLE_STATUT: Record<string, string> = {
  draft: "Brouillon",
  submitted: "Soumise",
  approved: "Approuvée",
  rejected: "Rejetée",
  won: "Gagnée",
  lost: "Perdue",
  expired: "Expirée",
};

const COULEUR_STATUT: Record<string, string> = {
  draft: "en_attente",
  submitted: "en_attente",
  approved: "approuvee",
  rejected: "rejetee",
  won: "approuvee",
  lost: "rejetee",
  expired: "rejetee",
};

interface QuoteSummary {
  quote_id: string;
  quote_number: string;
  client_code: string;
  client_name: string;
  created_by: string;
  created_at: string;
  status: string;
  total_mensuel: number;
  total_contrat: number;
  niveau_validation: number;
}

export function ConfigurateurV2() {
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);
  const [quoteActive, setQuoteActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  async function rafraichir() {
    setLoading(true);
    try {
      const list = await catalogApi.listQuotes();
      setQuotes(list);
    } catch (e) {
      setErreur(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void rafraichir();
  }, []);

  if (quoteActive) {
    return (
      <QuoteDetail
        quoteId={quoteActive}
        onBack={() => {
          setQuoteActive(null);
          void rafraichir();
        }}
      />
    );
  }

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <h2>Configurateur v2</h2>
          <p className="registre-sous-titre">
            Nouveau configurateur branché sur le <strong>moteur v2 PriceBook</strong>. Une offre regroupe plusieurs <strong>Quote lines</strong> (une par variante technique). Chaque calcul est figé via <code>PricingCalculation</code> — immutable quand une nouvelle version de PriceBook est publiée.
          </p>
        </div>
        <NouvelleQuoteForm onCree={(id) => setQuoteActive(id)} />
      </header>

      {erreur && <div className="erreur">{erreur}</div>}
      {loading ? (
        <p className="registre-vide">Chargement…</p>
      ) : quotes.length === 0 ? (
        <p className="registre-vide">Aucune quote. Clique sur <strong>+ Nouvelle quote</strong> pour commencer.</p>
      ) : (
        <table className="registre-table clickable">
          <thead>
            <tr>
              <th>N°</th>
              <th>Date</th>
              <th>Client</th>
              <th>KAM</th>
              <th>Statut</th>
              <th>Niveau</th>
              <th>Mensuel</th>
              <th>Total contrat</th>
            </tr>
          </thead>
          <tbody>
            {quotes.map((q) => (
              <tr key={q.quote_id} onClick={() => setQuoteActive(q.quote_id)}>
                <td className="mono"><strong>{q.quote_number}</strong></td>
                <td>{fmtDate(q.created_at)}</td>
                <td>
                  <div><strong>{q.client_name}</strong></div>
                  <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>{q.client_code}</div>
                </td>
                <td>{q.created_by}</td>
                <td>
                  <span className={`badge-statut badge-${COULEUR_STATUT[q.status]}`}>
                    {LIBELLE_STATUT[q.status]}
                  </span>
                </td>
                <td>
                  {q.niveau_validation === 0 ? (
                    <span className="badge-statut badge-approuvee">KAM</span>
                  ) : (
                    <span className="badge-statut badge-en_attente">N{q.niveau_validation}</span>
                  )}
                </td>
                <td className="num">{fmt(q.total_mensuel)}</td>
                <td className="num">{fmt(q.total_contrat)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

/* ----------------------------- Nouvelle quote ----------------------------- */

function NouvelleQuoteForm({ onCree }: { onCree: (quoteId: string) => void }) {
  const [ouvert, setOuvert] = useState(false);
  const [clientCode, setClientCode] = useState("");
  const [clientName, setClientName] = useState("");
  const [enCours, setEnCours] = useState(false);

  async function soumettre() {
    if (!clientCode || !clientName) return;
    setEnCours(true);
    try {
      const q = await catalogApi.createQuote(clientCode, clientName);
      onCree(q.quote_id);
    } catch (e) {
      alert(String(e));
    } finally {
      setEnCours(false);
    }
  }

  if (!ouvert) {
    return (
      <button type="button" className="bouton-principal" onClick={() => setOuvert(true)}>
        + Nouvelle quote
      </button>
    );
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
      <label style={{ fontSize: 12.5, color: "var(--fg-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
        Code client
        <input value={clientCode} onChange={(e) => setClientCode(e.target.value.toUpperCase())} style={{ padding: "6px 10px" }} />
      </label>
      <label style={{ fontSize: 12.5, color: "var(--fg-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
        Nom
        <input value={clientName} onChange={(e) => setClientName(e.target.value)} style={{ padding: "6px 10px" }} />
      </label>
      <button type="button" className="bouton-principal" onClick={soumettre} disabled={enCours}>
        {enCours ? "…" : "Créer"}
      </button>
      <button type="button" className="bouton-secondaire" onClick={() => setOuvert(false)}>
        Annuler
      </button>
    </div>
  );
}

/* ----------------------------- Detail Quote ----------------------------- */

function QuoteDetail({ quoteId, onBack }: { quoteId: string; onBack: () => void }) {
  const [data, setData] = useState<any>(null);
  const [variants, setVariants] = useState<any[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);

  async function charger() {
    try {
      const d = await catalogApi.getQuote(quoteId);
      setData(d);
    } catch (e) {
      setErreur(String(e));
    }
  }

  useEffect(() => {
    void charger();
    catalogApi.variants().then(setVariants);
  }, [quoteId]);

  if (!data) return <p className="registre-vide">Chargement…</p>;
  const quote = data.quote;
  const lines = data.lines ?? [];
  const session = sessionActive();
  const canDecide = aPermission("decider_derogation");
  const estBrouillon = quote.status === "draft";
  const estSoumise = quote.status === "submitted";
  const estMienne = session && quote.created_by.toLowerCase() === session.utilisateur.email.toLowerCase();

  async function supprimerLigne(lineId: string) {
    if (!confirm("Supprimer cette ligne ?")) return;
    try {
      await catalogApi.deleteQuoteLine(quoteId, lineId);
      await charger();
    } catch (e) {
      alert(String(e));
    }
  }

  async function soumettre() {
    try {
      await catalogApi.submitQuote(quoteId);
      await charger();
    } catch (e) {
      alert(String(e));
    }
  }

  async function decider(approved: boolean) {
    const comment = prompt(approved ? "Commentaire (optionnel)" : "Raison du rejet") ?? "";
    try {
      await catalogApi.decisionQuote(quoteId, approved, comment);
      await charger();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <section className="registre">
      <header className="registre-entete">
        <div>
          <button type="button" className="bouton-secondaire" onClick={onBack} style={{ marginBottom: 8 }}>
            ← Retour à la liste
          </button>
          <h2>
            <span className="mono">{quote.quote_number}</span> — {quote.client_name}
          </h2>
          <p className="registre-sous-titre">
            Code client <code>{quote.client_code}</code> · KAM {quote.created_by} · Créée le {fmtDate(quote.created_at)}
            <span style={{ marginLeft: 12 }}>
              <span className={`badge-statut badge-${COULEUR_STATUT[quote.status]}`}>
                {LIBELLE_STATUT[quote.status]}
              </span>
            </span>
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {estBrouillon && estMienne && (
            <button type="button" className="bouton-principal" onClick={soumettre} disabled={lines.length === 0}>
              Soumettre pour validation
            </button>
          )}
          {estSoumise && canDecide && (
            <>
              <button type="button" className="bouton-principal" onClick={() => decider(true)}>
                Approuver
              </button>
              <button type="button" className="bouton-secondaire" onClick={() => decider(false)}>
                Rejeter
              </button>
            </>
          )}
        </div>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      <div className="cartes-kpi">
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{fmt(quote.total_mensuel)}</div>
          <div className="carte-kpi-libelle">Mensuel total</div>
          <div className="carte-kpi-detail">Somme toutes lignes × quantité</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{fmt(quote.total_contrat)}</div>
          <div className="carte-kpi-libelle">Total contrat</div>
          <div className="carte-kpi-detail">Mensuel × durée max</div>
        </div>
        <div className="carte-kpi">
          <div className="carte-kpi-valeur">{lines.length}</div>
          <div className="carte-kpi-libelle">Quote lines</div>
          <div className="carte-kpi-detail">Variantes techniques du deal</div>
        </div>
        <div className="carte-kpi" style={{ borderColor: quote.niveau_validation > 0 ? "var(--alerte)" : undefined, borderWidth: quote.niveau_validation > 0 ? 2 : undefined }}>
          <div className="carte-kpi-valeur">N{quote.niveau_validation}</div>
          <div className="carte-kpi-libelle">Niveau validation</div>
          <div className="carte-kpi-detail">
            {quote.niveau_validation === 0 && "KAM autonome"}
            {quote.niveau_validation === 1 && "Manager"}
            {quote.niveau_validation === 2 && "Head of Pricing"}
            {quote.niveau_validation === 3 && "Direction"}
          </div>
        </div>
      </div>

      <h3 className="sous-titre-journal" style={{ marginTop: 20 }}>Quote lines</h3>
      {lines.map((item: any) => (
        <QuoteLineCard
          key={item.line.quote_line_id}
          item={item}
          onDelete={estBrouillon && estMienne ? () => supprimerLigne(item.line.quote_line_id) : undefined}
        />
      ))}

      {estBrouillon && estMienne && (
        <AjouterLigneForm quoteId={quoteId} variants={variants} onAjoutee={charger} />
      )}
    </section>
  );
}

/* ----------------------------- Line card ----------------------------- */

function QuoteLineCard({ item, onDelete }: { item: any; onDelete?: () => void }) {
  const [deplie, setDeplie] = useState(false);
  const { line, calculation, components } = item;
  if (!calculation) return null;

  return (
    <div className="quote-line-card">
      <div className="quote-line-entete" onClick={() => setDeplie((d) => !d)}>
        <div>
          <strong className="mono">#{line.line_number}</strong>
          <span className="variante-code" style={{ marginLeft: 10 }}>{line.technical_variant_code}</span>
          <span style={{ marginLeft: 12, color: "var(--fg-muted)", fontSize: 13 }}>
            {line.quantity} × {line.country_iso} · {line.contract_duration_months} mois · {line.annual_mileage_km.toLocaleString("fr-FR")} km/an
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="pastille-mode">v{calculation.dl_version_label} / {calculation.om_version_label}</span>
          <strong style={{ fontSize: 16, color: "var(--accent)" }}>{fmt(calculation.total_monthly * line.quantity)}</strong>
          <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>/mois</span>
          {onDelete && (
            <button type="button" className="bouton-mini bouton-mini-danger" onClick={(e) => { e.stopPropagation(); onDelete(); }}>
              Supprimer
            </button>
          )}
          <span className="noeud-chevron">{deplie ? "▼" : "▶"}</span>
        </div>
      </div>

      {deplie && (
        <div className="quote-line-detail">
          <div className="cartes-kpi" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(calculation.dl_monthly)}</div>
              <div className="carte-kpi-libelle">Dry Lease</div>
            </div>
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(calculation.hm_monthly_provisioned)}</div>
              <div className="carte-kpi-libelle">HM provisionnée</div>
            </div>
            <div className="carte-kpi">
              <div className="carte-kpi-valeur">{fmt(calculation.om_monthly)}</div>
              <div className="carte-kpi-libelle">OM</div>
            </div>
            <div className="carte-kpi" style={{ borderColor: "var(--accent)", borderWidth: 2 }}>
              <div className="carte-kpi-valeur" style={{ color: "var(--accent)" }}>{fmt(calculation.total_monthly)}</div>
              <div className="carte-kpi-libelle">Total / loco</div>
            </div>
          </div>

          {calculation.warnings?.length > 0 && (
            <div className="chiffrage-warnings">
              {calculation.warnings.map((w: string, i: number) => (
                <div key={i} className="chiffrage-warning">⚠ {w}</div>
              ))}
            </div>
          )}

          <h4 className="sous-titre-journal" style={{ marginTop: 12 }}>Composants (explicabilité)</h4>
          <table className="registre-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Code</th>
                <th>Description</th>
                <th>Mensuel</th>
                <th>Annuel</th>
                <th>Visible client</th>
              </tr>
            </thead>
            <tbody>
              {components.map((c: any) => (
                <tr key={c.component_id}>
                  <td><span className="pastille-mode">{c.component_type}</span></td>
                  <td className="mono">{c.component_code}</td>
                  <td>{c.description}</td>
                  <td className="num">{fmt(c.monthly_amount)}</td>
                  <td className="num">{fmt(c.annual_amount)}</td>
                  <td>{c.is_visible_to_client ? "✓" : <span style={{ color: "var(--fg-muted)" }}>interne</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ----------------------------- Ajouter ligne ----------------------------- */

function AjouterLigneForm({ quoteId, variants, onAjoutee }: { quoteId: string; variants: any[]; onAjoutee: () => void }) {
  const [form, setForm] = useState({
    technical_variant_code: variants[0]?.variant_code ?? "E186-DABNL",
    country_iso: "DE",
    duration_months: 24,
    age_years: 5,
    annual_mileage_km: 150000,
    annual_engine_hours: 0,
    quantity: 1,
  });
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (variants.length && !form.technical_variant_code) {
      setForm((f) => ({ ...f, technical_variant_code: variants[0].variant_code }));
    }
  }, [variants]);

  async function ajouter() {
    setEnCours(true);
    setErreur(null);
    try {
      await catalogApi.addQuoteLine(quoteId, form);
      onAjoutee();
    } catch (e) {
      setErreur(String(e));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="ajout-ligne-form">
      <h4 className="sous-titre-journal">+ Ajouter une ligne</h4>
      <div className="chiffrage-form" style={{ marginTop: 8 }}>
        <label>
          Variante technique
          <select value={form.technical_variant_code} onChange={(e) => setForm({ ...form, technical_variant_code: e.target.value })}>
            {variants.map((v) => (
              <option key={v.technical_variant_id} value={v.variant_code}>
                {v.variant_code} — {v.variant_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Pays (ISO)
          <select value={form.country_iso} onChange={(e) => setForm({ ...form, country_iso: e.target.value })}>
            {PAYS_ISO.map((iso) => <option key={iso} value={iso}>{iso}</option>)}
          </select>
        </label>
        <label>
          Quantité (locos)
          <input type="number" min={1} value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
        </label>
        <label>
          Durée (mois)
          <input type="number" min={1} value={form.duration_months}
            onChange={(e) => setForm({ ...form, duration_months: Number(e.target.value) })} />
        </label>
        <label>
          Âge (ans)
          <input type="number" min={0} step={0.5} value={form.age_years}
            onChange={(e) => setForm({ ...form, age_years: Number(e.target.value) })} />
        </label>
        <label>
          Mileage annuel (km)
          <input type="number" min={0} value={form.annual_mileage_km}
            onChange={(e) => setForm({ ...form, annual_mileage_km: Number(e.target.value) })} />
        </label>
        <label>
          Heures moteur
          <input type="number" min={0} value={form.annual_engine_hours}
            onChange={(e) => setForm({ ...form, annual_engine_hours: Number(e.target.value) })} />
        </label>
        <button type="button" className="bouton-principal" onClick={ajouter} disabled={enCours}
          style={{ gridColumn: "1 / -1", marginTop: 8 }}>
          {enCours ? "Chiffrage…" : "+ Ajouter la ligne"}
        </button>
      </div>
      {erreur && <div className="erreur" style={{ marginTop: 10 }}>{erreur}</div>}
    </div>
  );
}
