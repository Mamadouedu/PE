// Le prototype Python générait un PDF (POST /api/v1/offres/pdf, numérotation
// + journal des offres). Le back-end .NET (PricingHub) ne porte pas encore
// cette fonctionnalité — ni le module de génération, ni la numérotation
// séquentielle des offres envoyées. Plutôt que de faire semblant ou de
// faire disparaître le bouton sans explication, on le désactive avec une
// mention explicite : voir le journal de la bascule frontend pour le détail
// de cet écart de périmètre, encore à combler côté API.
export function TelechargerPdfButton() {
  return (
    <div className="telecharger-pdf">
      <button
        type="button"
        className="bouton-secondaire"
        disabled
        title="Génération de PDF non encore disponible sur le nouveau back-end .NET"
      >
        ⭳ Télécharger le PDF
      </button>
      <p className="aide-comparateur">pas encore disponible sur le nouveau back-end</p>
    </div>
  );
}
