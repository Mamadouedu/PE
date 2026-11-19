import type { ScenarioComparaison } from "../scenario";
import type { PriceLine } from "../api/types";
import { LIBELLE_PRICE_LINE } from "../api/types";

const LIGNES: PriceLine[] = ["DryLease", "HeavyMaintenance", "OperatingMaintenance", "Insurance"];

const formatEuro = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const formatPourcent = new Intl.NumberFormat("fr-FR", {
  style: "percent",
  maximumFractionDigits: 1,
});

interface Props {
  scenarios: ScenarioComparaison[];
  onRetirer: (id: string) => void;
}

export function Comparateur({ scenarios, onRetirer }: Props) {
  if (scenarios.length === 0) return null;

  return (
    <section className="comparateur">
      <h2>Comparateur de scénarios</h2>
      <div className="comparateur-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col" className="comparateur-ligne-titre" />
              {scenarios.map((s) => (
                <th key={s.id} scope="col">
                  <div className="comparateur-entete-colonne">
                    <span>{s.label}</span>
                    <button
                      type="button"
                      className="comparateur-retirer"
                      onClick={() => onRetirer(s.id)}
                      aria-label={`Retirer ${s.label} du comparateur`}
                    >
                      ✕
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Client</th>
              {scenarios.map((s) => (
                <td key={s.id}>{s.requete.customerCode}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">Quantité</th>
              {scenarios.map((s) => (
                <td key={s.id}>{s.requete.quantity}</td>
              ))}
            </tr>
            {LIGNES.map((ligneCode) => (
              <tr key={ligneCode}>
                <th scope="row">{LIBELLE_PRICE_LINE[ligneCode]}</th>
                {scenarios.map((s) => {
                  const ligne = s.offre.briques.find((b) => b.brique === ligneCode);
                  return (
                    <td key={s.id} className={ligne ? `brique-${ligne.statut}` : undefined}>
                      {ligne && ligne.statut !== "exclue" ? formatEuro.format(ligne.prixRetenu) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="comparateur-ligne-forte">
              <th scope="row">Total mensuel / loco</th>
              {scenarios.map((s) => (
                <td key={s.id}>{formatEuro.format(s.offre.totalRetenuMensuel)}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">Total sur la durée</th>
              {scenarios.map((s) => (
                <td key={s.id}>{formatEuro.format(s.offre.totalContrat)}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">Remise globale</th>
              {scenarios.map((s) => (
                <td key={s.id}>{formatPourcent.format(s.offre.remiseGlobale)}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">Validation requise</th>
              {scenarios.map((s) => (
                <td key={s.id} className={s.offre.envoiDirectPossible ? "niveau-ok" : "niveau-attention"}>
                  {s.offre.libelleNiveau}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
