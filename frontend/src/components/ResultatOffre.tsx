import type { OffreKam } from "../api/offre";
import type { ConfigurationOffre } from "../api/types";
import { DemandeValidation } from "./DemandeValidation";
import { JaugeNegociation } from "./JaugeNegociation";

const LIBELLE_STATUT: Record<string, string> = {
  ok: "✓ Dans les règles",
  alerte: "⚠ Négocié sous catalogue",
  sous_plancher: "✗ Sous le plancher",
  exclue: "— Exclue de l'offre",
};

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
  offre: OffreKam;
  configuration: ConfigurationOffre;
}

export function ResultatOffre({ offre, configuration }: Props) {
  return (
    <div className="resultat-offre">
      {!offre.envoiDirectPossible && (
        <div className="bandeau-projet">
          <p>
            PROJET — en attente de validation ({offre.libelleNiveau}). Cette offre ne peut pas être
            envoyée telle quelle.
          </p>
          <DemandeValidation libelleNiveau={offre.libelleNiveau} configuration={configuration} />
        </div>
      )}

      <section className="briques">
        {offre.briques.map((ligne) => (
          <article key={ligne.brique} className={`brique-carte brique-${ligne.statut}`}>
            <header>
              <h3>{ligne.libelle}</h3>
              <span className="statut-badge">{LIBELLE_STATUT[ligne.statut]}</span>
            </header>

            {ligne.statut !== "exclue" && (
              <>
                <JaugeNegociation
                  plancher={ligne.plancher}
                  catalogue={ligne.prixCatalogue}
                  retenu={ligne.prixRetenu}
                />
                <dl>
                  <div>
                    <dt>Catalogue</dt>
                    <dd>{formatEuro.format(ligne.prixCatalogue)}</dd>
                  </div>
                  <div>
                    <dt>Plancher</dt>
                    <dd>{formatEuro.format(ligne.plancher)}</dd>
                  </div>
                  <div>
                    <dt>Retenu</dt>
                    <dd className="valeur-forte">{formatEuro.format(ligne.prixRetenu)}</dd>
                  </div>
                </dl>
              </>
            )}
          </article>
        ))}
      </section>

      <section className="totaux">
        <div>
          <span>Total mensuel ({formatPourcent.format(offre.remiseGlobale)} de remise)</span>
          <strong>{formatEuro.format(offre.totalRetenuMensuel)} / loco</strong>
        </div>
        <div>
          <span>Total mensuel, toutes locos</span>
          <strong>{formatEuro.format(offre.totalMensuel)}</strong>
        </div>
        <div>
          <span>Total sur la durée du contrat</span>
          <strong>{formatEuro.format(offre.totalContrat)}</strong>
        </div>
        <div>
          <span>Km supplémentaire</span>
          <strong>{formatEuro.format(offre.prixKmSupplementaire)} / km</strong>
        </div>
      </section>

      <section className="niveau-validation">
        <h3>Validation requise</h3>
        <p className={offre.envoiDirectPossible ? "niveau-ok" : "niveau-attention"}>
          {offre.libelleNiveau}
        </p>
      </section>

      <section className="controles">
        <h3>Contrôles avant envoi</h3>
        <ul>
          {offre.controles.map((controle) => (
            <li key={controle.code} className={controle.ok ? "controle-ok" : "controle-echec"}>
              {controle.ok ? "✓" : "✗"} {controle.libelle}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
