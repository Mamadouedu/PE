interface Props {
  plancher: number;
  catalogue: number;
  retenu: number;
}

// Position du prix retenu entre le plancher (0 %) et le catalogue (100 %).
// Un prix retenu sous le plancher dépasse 0 % vers la gauche : affiché à 0 %
// avec une marque rouge, le statut de la brique porte déjà l'alerte.
export function JaugeNegociation({ plancher, catalogue, retenu }: Props) {
  const ecart = catalogue - plancher;
  const position = ecart > 0 ? ((retenu - plancher) / ecart) * 100 : 100;
  const positionAffichee = Math.min(100, Math.max(0, position));
  const sousLePlancher = retenu < plancher;

  return (
    <div className="jauge" title={`Plancher ${plancher.toFixed(0)} — Catalogue ${catalogue.toFixed(0)}`}>
      <div className="jauge-piste">
        <div
          className={`jauge-marqueur${sousLePlancher ? " jauge-marqueur-alerte" : ""}`}
          style={{ left: `${positionAffichee}%` }}
        />
      </div>
      <div className="jauge-bornes">
        <span>plancher</span>
        <span>catalogue</span>
      </div>
    </div>
  );
}
