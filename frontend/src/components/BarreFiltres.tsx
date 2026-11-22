interface OptionSelect {
  valeur: string;
  libelle: string;
}

interface Props {
  recherche: string;
  surRecherche: (v: string) => void;
  placeholderRecherche?: string;
  filtres?: {
    libelle: string;
    valeur: string;
    options: OptionSelect[];
    onChange: (v: string) => void;
  }[];
  nbResultats?: number;
  nbTotal?: number;
}

export function BarreFiltres({
  recherche,
  surRecherche,
  placeholderRecherche = "Rechercher…",
  filtres = [],
  nbResultats,
  nbTotal,
}: Props) {
  return (
    <div className="barre-filtres">
      <input
        type="search"
        className="input-recherche"
        value={recherche}
        onChange={(e) => surRecherche(e.target.value)}
        placeholder={placeholderRecherche}
      />
      {filtres.map((f) => (
        <label key={f.libelle} className="filtre-select">
          <span>{f.libelle}</span>
          <select value={f.valeur} onChange={(e) => f.onChange(e.target.value)}>
            <option value="">Tous</option>
            {f.options.map((o) => (
              <option key={o.valeur} value={o.valeur}>
                {o.libelle}
              </option>
            ))}
          </select>
        </label>
      ))}
      {nbResultats !== undefined && nbTotal !== undefined && (
        <span className="compteur-resultats">
          {nbResultats === nbTotal ? `${nbTotal} ligne${nbTotal > 1 ? "s" : ""}` : `${nbResultats} / ${nbTotal}`}
        </span>
      )}
    </div>
  );
}
