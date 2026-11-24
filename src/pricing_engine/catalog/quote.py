"""Quote & QuoteLines — le nouveau configurateur (Lot 4).

Structure cible section 13 du doc :

    Quote
      └── QuoteLine (une par variante technique du deal)
            ├── TechnicalVariant
            ├── AnnualMileage
            ├── EngineHours
            ├── Duration
            ├── Homologation (variantes multi-pays)
            ├── ECM
            └── Options (QuoteLineOptions)

Chaque QuoteLine déclenche un `PricingCalculation` : snapshot figé des
tarifs utilisés et du résultat du moteur v2. Si la version du PriceBook
change après la création de la quote, le calcul reste inchangé.

`AppliedPricingRule` trace les règles métier appliquées : remises client,
majorations, dérogations, campagnes promotionnelles.

Statuts du cycle de vie :
    DRAFT (KAM en construction)
      → SUBMITTED (envoyé au client)
      → APPROVED (accepté commercialement) / REJECTED (abandonné)
      → WON (contrat signé) / LOST (perdu face à un concurrent)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class QuoteStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WON = "won"
    LOST = "lost"
    EXPIRED = "expired"


class PricingRuleKind(str, Enum):
    """Catégorie de règle appliquée au calcul."""

    VOLUME_DISCOUNT = "volume_discount"
    LOYALTY_DISCOUNT = "loyalty_discount"
    CAMPAIGN = "campaign"
    DEROGATION = "derogation"
    SURCHARGE = "surcharge"
    SPECIFIC_COMMITMENT = "specific_commitment"
    NEGOTIATED = "negotiated"


class Quote(BaseModel):
    """En-tête d'une proposition commerciale.

    Un Quote regroupe une ou plusieurs QuoteLines (variantes techniques
    distinctes dans un même deal). Il porte le client, la devise, la
    période de validité de l'offre, et le statut global.
    """

    quote_id: UUID = Field(default_factory=uuid4)
    quote_number: str = Field(description="Ex. Q-2026-000042, numérotation séquentielle")
    client_code: str
    client_name: str
    created_by: str = Field(description="E-mail du KAM")
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    status: QuoteStatus = QuoteStatus.DRAFT
    submitted_at: datetime | None = None
    decision_at: datetime | None = None
    decided_by: str | None = None
    decision_comment: str | None = None
    valid_until: date | None = None
    currency_iso: str = Field(default="EUR", min_length=3, max_length=3)
    total_mensuel: float = Field(default=0, ge=0)
    total_contrat: float = Field(default=0, ge=0)
    niveau_validation: int = Field(default=0, ge=0, le=3,
        description="0=KAM, 1=Manager, 2=HeadPricing, 3=Direction")
    pipedrive_deal_id: int | None = None


class QuoteLine(BaseModel):
    """Une ligne de l'offre : une variante technique avec sa configuration.

    Le prix calculé vit dans PricingCalculation attaché à cette ligne.
    """

    quote_line_id: UUID = Field(default_factory=uuid4)
    quote_id: UUID
    line_number: int = Field(ge=1, description="Ordre dans la quote (1, 2, 3...)")
    technical_variant_id: UUID
    technical_variant_code: str = Field(description="Dénormalisé pour l'affichage sans join")

    # Configuration commerciale
    quantity: int = Field(ge=1, default=1)
    contract_duration_months: int = Field(ge=1)
    annual_mileage_km: int = Field(ge=0)
    annual_engine_hours: float = Field(default=0, ge=0)
    monthly_mileage_km: int | None = None
    start_date: date
    end_date: date | None = None

    # Contexte géographique + réglementaire
    country_iso: str = Field(min_length=2, max_length=2)
    homologation_id: UUID | None = None
    selected_ecm_provider_id: UUID | None = None
    selected_service_level_id: UUID | None = None

    # Flotte (optionnel : si le deal cible une loco spécifique)
    fleet_asset_id: UUID | None = None

    # Note libre KAM
    notes: str = ""


class QuoteLineOption(BaseModel):
    """Option commerciale attachée à une QuoteLine.

    Ex. ECM_SERVICE à 350 €/mois, HOTLINE_24_7 à 180 €/mois.
    Le montant peut être calculé à partir de CommercialOption + tarif,
    ou saisi manuellement par le KAM.
    """

    quote_line_option_id: UUID = Field(default_factory=uuid4)
    quote_line_id: UUID
    commercial_option_id: UUID
    option_code: str = Field(description="Dénormalisé pour l'affichage")
    quantity: int = Field(default=1, ge=0)
    unit_price: float = Field(ge=0)
    billing_unit: str = "monthly"
    total_monthly_impact: float = Field(default=0, ge=0,
        description="Impact mensuel équivalent (après conversion yearly / per_km → monthly)")
    is_included: bool = True


class PricingCalculation(BaseModel):
    """Snapshot figé du calcul pour une QuoteLine.

    Enregistre à l'instant T les versions de PriceBook utilisées, les
    totaux DL/HM/OM/Total, et les plancher/plafond éventuellement
    appliqués. Si l'équipe pricing publie une nouvelle version 2026-v2
    de DL_STANDARD, ce record n'est PAS modifié : la quote garde son prix
    d'émission.
    """

    pricing_calculation_id: UUID = Field(default_factory=uuid4)
    quote_line_id: UUID
    calculated_at: datetime = Field(default_factory=_now_utc)

    # Snapshot des versions
    dl_price_book_version_id: UUID | None = None
    hm_price_book_version_id: UUID | None = None
    om_price_book_version_id: UUID | None = None
    dl_version_label: str | None = Field(default=None, description="ex. 2026-v1")
    hm_version_label: str | None = None
    om_version_label: str | None = None

    # Composants
    dl_monthly: float = 0
    hm_monthly_provisioned: float = 0
    om_monthly: float = 0
    options_monthly: float = 0
    total_monthly: float = 0
    total_contract: float = 0

    # Bornes et contrôles
    floor_applied: float = 0
    cap_applied: float = 0
    is_under_floor: bool = False
    niveau_validation: int = Field(default=0, ge=0, le=3)
    warnings: list[str] = Field(default_factory=list)


class PricingCalculationComponent(BaseModel):
    """Détail d'une composante du calcul (pour l'explicabilité M2-05).

    Une ligne par composante : par brique OM, par opération HM, par
    option commerciale. Permet au KAM de comprendre d'où vient chaque €.
    """

    component_id: UUID = Field(default_factory=uuid4)
    pricing_calculation_id: UUID
    component_type: str = Field(description="dl_base, dl_insurance, dl_risk, dl_specific, "
                                "om_fixed, om_mileage, om_engine_hours, om_ecm, om_last_mile, "
                                "hm_provision, option_fixed, floor, cap")
    component_code: str = Field(description="Code métier : HM1, VGI, ECM_SERVICE, ...")
    description: str = ""
    monthly_amount: float = Field(default=0)
    annual_amount: float = Field(default=0)
    is_visible_to_client: bool = Field(default=True,
        description="False pour les coûts internes (plancher, marge, cost)")


class AppliedPricingRule(BaseModel):
    """Règle métier appliquée au calcul (dérogation, remise, campagne).

    Chaque application est tracée avec :
    - la règle (kind + code + description)
    - l'impact (% ou montant mensuel)
    - qui l'a validée (approved_by, approved_at)
    """

    applied_rule_id: UUID = Field(default_factory=uuid4)
    pricing_calculation_id: UUID
    rule_kind: PricingRuleKind
    rule_code: str
    rule_description: str = ""
    impact_percentage: float = Field(default=0, description="Négatif = remise, positif = surcoût")
    impact_monthly_amount: float = Field(default=0)
    approved_by: str | None = None
    approved_at: datetime | None = None
    reference: str | None = Field(default=None, description="Numéro dérogation, code campagne…")
