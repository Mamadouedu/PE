import { useEffect, type ReactNode } from "react";

interface Props {
  titre: string;
  sousTitre?: string;
  onFermer: () => void;
  children: ReactNode;
}

export function PanneauDetail({ titre, sousTitre, onFermer, children }: Props) {
  useEffect(() => {
    function surEchap(e: KeyboardEvent) {
      if (e.key === "Escape") onFermer();
    }
    document.addEventListener("keydown", surEchap);
    return () => document.removeEventListener("keydown", surEchap);
  }, [onFermer]);

  return (
    <div className="panneau-overlay" role="dialog" aria-modal="true" onClick={onFermer}>
      <aside className="panneau-detail" onClick={(e) => e.stopPropagation()}>
        <header className="panneau-detail-entete">
          <div>
            <h2>{titre}</h2>
            {sousTitre && <p className="panneau-detail-sous-titre">{sousTitre}</p>}
          </div>
          <button type="button" className="panneau-fermer" aria-label="Fermer" onClick={onFermer}>
            ×
          </button>
        </header>
        <div className="panneau-detail-corps">{children}</div>
      </aside>
    </div>
  );
}

export function LigneDetail({ libelle, valeur }: { libelle: string; valeur: ReactNode }) {
  return (
    <div className="ligne-detail">
      <span className="ligne-detail-libelle">{libelle}</span>
      <span className="ligne-detail-valeur">{valeur}</span>
    </div>
  );
}
