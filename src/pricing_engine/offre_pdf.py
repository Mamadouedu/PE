"""Offre PDF — numérotée, aux couleurs Akiem, avec conditions, mention
PROJET tant que la validation requise manque (M3-05).

Ce PDF part chez le client : il ne montre jamais le catalogue ni le
plancher d'une brique (ça révélerait la marge de négociation au client, pas
seulement au KAM — une contrainte plus stricte que M3-07), ni les 8
contrôles avant envoi (un outil d'aide à la décision interne, pas une pièce
commerciale). Seul le prix retenu compte ici. L'écran KAM
(`frontend/.../ResultatOffre.tsx`) reste le seul endroit qui montre
catalogue/plancher/contrôles.

Chaque PDF généré est journalisé (numéro, qui, pour quel client/série,
quel montant, quel niveau de validation) : c'est la part « journal des
offres » de M3-06 que ce dépôt couvre déjà. L'écriture dans Pipedrive
(l'autre moitié de M3-06) reste à faire — hors périmètre sans accès à
l'API Pipedrive.

Couleurs, mise en page et conditions générales ci-dessous sont un
placeholder cohérent avec le reste de la plateforme, pas la charte
graphique ni le texte juridique réels d'Akiem — les questions ouvertes du
cahier (section 12.2 : langue des offres PDF, modèles juridiques à
utiliser) sont justement encore ouvertes.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Protocol

from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .engine import calculer_offre
from .models import Brique, ConfigurationOffre
from .referentiel import VersionReferentiel

COULEUR_ACCENT = colors.HexColor("#2f5d8a")
COULEUR_ACCENT_2 = colors.HexColor("#b5672b")
COULEUR_GRIS = colors.HexColor("#5b6b7a")
COULEUR_GRIS_CLAIR = colors.HexColor("#e4e9ed")

LIBELLE_BRIQUE: dict[Brique, str] = {
    Brique.DRY_LEASE: "Dry lease",
    Brique.HEAVY_MAINTENANCE: "Heavy maintenance",
    Brique.OPERATION_MAINTENANCE: "Operation maintenance",
    Brique.ASSURANCE: "Assurance",
}

CONDITIONS_GENERALES = [
    "Offre exprimée en euros HT par locomotive et par mois, hors frais de mise en service.",
    "Le kilométrage au-delà du forfait annuel inclus est facturé au prix du km supplémentaire indiqué ci-dessus.",
    "La locomotive doit être restituée en bon état d'entretien courant, conforme aux normes en vigueur à la restitution.",
    "Toute modification de la configuration (prix, durée, quantité, locomotive) après signature fait l'objet d'un avenant.",
    "Offre soumise aux conditions générales de location full service leasing Akiem en vigueur.",
]


class OffreGeneree(BaseModel):
    sequence: int
    numero: str
    date_generation: datetime
    utilisateur: str
    client_code: str
    serie_code: str
    configuration: ConfigurationOffre
    version_referentiel: int
    montant_mensuel_retenu: float
    niveau_validation: int
    # Intégration Pipedrive (M3-06) : renseignés si l'offre a été poussée
    # dans le CRM. `statut` reste `non_configure` tant que PIPEDRIVE_API_TOKEN
    # n'est pas défini.
    pipedrive_deal_id: int | None = None
    pipedrive_deal_url: str | None = None
    pipedrive_statut: str = "non_configure"
    pipedrive_erreur: str | None = None


class OffreGenereeStore(Protocol):
    def prochaine_sequence(self) -> int: ...
    def enregistrer(self, offre: OffreGeneree) -> None: ...
    def lister(self) -> list[OffreGeneree]: ...


class InMemoryOffreGenereeStore:
    """Backend par défaut : rien de persistant. Remplacé par
    `db.SqlAlchemyOffreGenereeStore` dès que `DATABASE_URL` est défini."""

    def __init__(self) -> None:
        self._offres: list[OffreGeneree] = []
        self._compteur = 0

    def prochaine_sequence(self) -> int:
        self._compteur += 1
        return self._compteur

    def enregistrer(self, offre: OffreGeneree) -> None:
        self._offres.append(offre)

    def lister(self) -> list[OffreGeneree]:
        return sorted(self._offres, key=lambda o: o.sequence, reverse=True)


def formater_numero(sequence: int) -> str:
    return f"AK-{sequence:06d}"


def generer_offre(
    store: OffreGenereeStore,
    version: VersionReferentiel,
    configuration: ConfigurationOffre,
    utilisateur: str,
    pipedrive=None,  # PipedriveBridge | None, import tardif pour éviter la dépendance circulaire
) -> tuple[OffreGeneree, bytes]:
    """Calcule l'offre, lui attribue un numéro, la journalise, puis
    construit le PDF. Lève les mêmes erreurs que `engine.calculer_offre`
    (`KeyError`, `ValueError`) si la configuration est invalide.

    Si `pipedrive` est fourni, pousse aussi le deal dans Pipedrive (M3-06).
    L'appel est best-effort : un échec Pipedrive n'empêche jamais la
    génération du PDF — `pipedrive_statut` vaut alors `echec`."""

    detail = calculer_offre(version, configuration)

    sequence = store.prochaine_sequence()
    enregistree = OffreGeneree(
        sequence=sequence,
        numero=formater_numero(sequence),
        date_generation=datetime.now(timezone.utc),
        utilisateur=utilisateur,
        client_code=configuration.client_code,
        serie_code=configuration.serie_code,
        configuration=configuration,
        version_referentiel=version.numero,
        montant_mensuel_retenu=detail.total_retenu_mensuel,
        niveau_validation=detail.niveau_validation,
    )

    if pipedrive is not None:
        resultat = pipedrive.pousser_deal(enregistree)
        enregistree.pipedrive_deal_id = resultat.deal_id
        enregistree.pipedrive_deal_url = resultat.deal_url
        enregistree.pipedrive_statut = resultat.statut
        enregistree.pipedrive_erreur = resultat.erreur

    store.enregistrer(enregistree)

    client = version.clients.get(configuration.client_code)
    nom_client = client.nom if client else configuration.client_code

    pdf = _construire_pdf(enregistree, nom_client, version, detail)
    return enregistree, pdf


def _construire_pdf(offre: OffreGeneree, nom_client: str, version: VersionReferentiel, detail) -> bytes:
    tampon = io.BytesIO()
    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Offre {offre.numero}",
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "TitreAkiem", parent=styles["Title"], textColor=COULEUR_ACCENT, fontSize=20, spaceAfter=2
    )
    style_sous_titre = ParagraphStyle(
        "SousTitre", parent=styles["Normal"], textColor=COULEUR_GRIS, fontSize=10
    )
    style_section = ParagraphStyle(
        "Section", parent=styles["Heading2"], textColor=COULEUR_ACCENT, fontSize=12, spaceBefore=14
    )
    style_normal = styles["Normal"]
    style_petit = ParagraphStyle("Petit", parent=styles["Normal"], fontSize=8.5, textColor=COULEUR_GRIS)
    style_projet = ParagraphStyle(
        "Projet",
        parent=styles["Normal"],
        textColor=colors.white,
        backColor=COULEUR_ACCENT_2,
        alignment=TA_CENTER,
        fontSize=11,
        fontName="Helvetica-Bold",
        borderPadding=8,
    )

    elements: list = []
    elements.append(Paragraph("Akiem — Full service leasing", style_titre))
    elements.append(
        Paragraph(
            f"Offre n° {offre.numero} · émise le {offre.date_generation.strftime('%d/%m/%Y')}",
            style_sous_titre,
        )
    )
    elements.append(Spacer(1, 10 * mm))

    if offre.niveau_validation > 0:
        elements.append(
            Paragraph(
                "PROJET — offre non définitive, soumise à validation interne avant envoi.",
                style_projet,
            )
        )
        elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Client et configuration", style_section))
    parametres = version.parametres
    date_limite = offre.date_generation + timedelta(days=parametres.validite_offre_jours)
    lignes_config = [
        ["Client", nom_client],
        ["Série", offre.configuration.serie_code],
        ["Quantité", str(offre.configuration.quantite)],
        ["Durée", f"{offre.configuration.duree_mois} mois"],
        ["Kilométrage annuel inclus", f"{offre.configuration.km_annuel:,.0f} km".replace(",", " ")],
        ["Date de début", offre.configuration.date_debut.strftime("%d/%m/%Y")],
        ["Validité de l'offre", f"{date_limite.strftime('%d/%m/%Y')} ({parametres.validite_offre_jours} jours)"],
        ["Indexation annuelle", f"{parametres.indexation_annuelle:.1%}"],
    ]
    table_config = Table(lignes_config, colWidths=[55 * mm, 110 * mm])
    table_config.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), COULEUR_GRIS),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, COULEUR_GRIS_CLAIR),
            ]
        )
    )
    elements.append(table_config)

    elements.append(Paragraph("Prix", style_section))
    entetes = ["Brique", "Prix mensuel HT"]
    lignes_prix = [entetes]
    for brique in (Brique.DRY_LEASE, Brique.HEAVY_MAINTENANCE, Brique.OPERATION_MAINTENANCE, Brique.ASSURANCE):
        d = detail.par_brique.get(brique)
        if d is None or d.statut.value == "exclue":
            continue
        lignes_prix.append([LIBELLE_BRIQUE[brique], f"{d.prix_retenu:,.2f} €".replace(",", " ")])
    lignes_prix.append(["Km supplémentaire", f"{detail.prix_km_supplementaire:,.2f} € / km".replace(",", " ")])
    lignes_prix.append(["Total mensuel HT par locomotive", f"{detail.total_retenu_par_loco_mensuel:,.2f} €".replace(",", " ")])
    if offre.configuration.quantite > 1:
        lignes_prix.append(
            ["Total mensuel HT, toutes locomotives", f"{detail.total_retenu_mensuel:,.2f} €".replace(",", " ")]
        )
    lignes_prix.append(["Total sur la durée du contrat", f"{detail.total_retenu_contrat:,.2f} €".replace(",", " ")])

    table_prix = Table(lignes_prix, colWidths=[95 * mm, 70 * mm])
    style_table_prix = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, COULEUR_GRIS_CLAIR),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, COULEUR_ACCENT),
    ]
    table_prix.setStyle(TableStyle(style_table_prix))
    elements.append(table_prix)

    elements.append(Paragraph("Conditions générales", style_section))
    for condition in CONDITIONS_GENERALES:
        elements.append(Paragraph(f"• {condition}", style_normal))
        elements.append(Spacer(1, 2))

    elements.append(Spacer(1, 10 * mm))
    elements.append(
        Paragraph(
            "Document généré automatiquement par la plateforme Pricing Akiem — à valeur commerciale "
            "une fois signé et, le cas échéant, validé en interne.",
            style_petit,
        )
    )

    document.build(elements)
    return tampon.getvalue()
