"""Tarifs versionnés PricingHub (Lot 3, sections 8-11 du doc Architecture
Cible).

Principe fondamental : **le prix est une donnée temporelle et versionnée,
pas une propriété de la variante**. La structure cible :

    PriceBook (DL_STANDARD, HM_STANDARD, OM_STANDARD)
        └── PriceBookVersion (année, version, statut, ValidFrom/To)
            └── PriceBookLines (table pivot) ou tables spécialisées :
                - DryLeaseRates   (loyer mensuel + assurance + risk)
                - HeavyMaintenanceRates (prix par opération)
                - OperatingMaintenanceRates (formule multi-composants)

Formule OM cible (section 11) :

    OM mensuel =   MonthlyFixedAmount
                 + (AnnualMileage       × PricePerKilometer  / 12)
                 + (AnnualEngineHours   × PricePerEngineHour / 12)
                 + EcmMonthlyAmount
                 + LastMileMonthlyAmount
                 + Options

Dimensions annexes (section 8) :
- LeaseBand        : paliers de durée (12-24, 25-36, 37-60, 61+ mois)
- AssetAgeBand     : paliers d'âge (< 5 ans, 5-10, 10-15, 15+)
- CountryGroup     : groupes pays pour les tarifs DL (ex. Core_DACH, Fret_PL)
- CommercialOption : ECM_SERVICE, LAST_MILE, HOTLINE, WHEEL_REPROFILING, ...
- BillingUnit      : MONTHLY, YEARLY, PER_KM, PER_HOUR, PER_OPERATION
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PriceType(str, Enum):
    """Nature du tarif dans un PriceBook."""

    DRY_LEASE = "DL"
    HEAVY_MAINTENANCE = "HM"
    OPERATING_MAINTENANCE = "OM"
    WORKSHOP_SERVICE = "WS"


class PriceBookStatus(str, Enum):
    """Cycle de vie d'une version de PriceBook."""

    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BillingUnit(str, Enum):
    """Unité de facturation d'une ligne tarifaire."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    PER_KM = "per_km"
    PER_HOUR = "per_hour"
    PER_OPERATION = "per_operation"
    ONE_SHOT = "one_shot"


class CalculationMethodHM(str, Enum):
    """Méthode de facturation HM."""

    FIXED = "fixed"              # Montant forfaitaire par opération
    TIME_AND_MATERIAL = "t_and_m"  # Temps passé + pièces
    MONTHLY_PROVISION = "monthly_provision"  # Lissé mensuellement


# =========================================================================
# Dimensions auxiliaires (Lot 3)
# =========================================================================


class LeaseBand(BaseModel):
    """Palier de durée de contrat (en mois).

    Ex. SHORT (0-11), MEDIUM (12-36), LONG (37-60), VERY_LONG (61+).
    Le loyer DL varie selon le palier : plus long = tarif unitaire réduit.
    """

    lease_band_id: UUID = Field(default_factory=uuid4)
    band_code: str = Field(description="SHORT, MEDIUM, LONG, VERY_LONG")
    band_name: str
    min_duration_months: int = Field(ge=0)
    max_duration_months: int | None = Field(default=None, ge=0)
    is_active: bool = True

    def contient(self, duration_months: int) -> bool:
        if duration_months < self.min_duration_months:
            return False
        if self.max_duration_months is None:
            return True
        return duration_months <= self.max_duration_months


class AssetAgeBand(BaseModel):
    """Palier d'âge de la locomotive (en années à la mise en contrat).

    Ex. NEW (0-5), YOUNG (5-10), MATURE (10-15), OLD (15+).
    Le loyer DL varie selon l'âge : plus âgé = tarif plus bas (perte
    de valeur plus lente, amortissement avancé).
    """

    asset_age_band_id: UUID = Field(default_factory=uuid4)
    band_code: str = Field(description="NEW, YOUNG, MATURE, OLD")
    band_name: str
    min_age_years: float = Field(ge=0)
    max_age_years: float | None = Field(default=None, ge=0)
    is_active: bool = True

    def contient(self, age_years: float) -> bool:
        if age_years < self.min_age_years:
            return False
        if self.max_age_years is None:
            return True
        return age_years < self.max_age_years


class CountryGroup(BaseModel):
    """Groupe de pays pour la tarification DL/HM/OM.

    Certains tarifs sont identiques pour un ensemble de pays (ex. DACH =
    DE+AT+CH partagent les mêmes loyers), d'autres sont pays-spécifiques.
    Simplifie les grilles tarifaires.
    """

    country_group_id: UUID = Field(default_factory=uuid4)
    group_code: str = Field(description="CORE_DACH, FRET_PL, BENELUX, SCANDI, UK_ONLY, EURO_WIDE")
    group_name: str
    country_iso_codes: list[str] = Field(default_factory=list, description="ISO 3166-1 alpha-2")
    description: str = ""
    is_active: bool = True

    def contient_pays(self, iso: str) -> bool:
        return iso.upper() in {c.upper() for c in self.country_iso_codes}


class CommercialOption(BaseModel):
    """Option commerciale ajoutable à un QuoteLine (Lot 4).

    Section 4 du doc : ECM_SERVICE, LAST_MILE, HOTLINE, WHEEL_REPROFILING,
    INSURANCE_COVER, SPECIFIC_COMMITMENT, WORKSHOP_PACKAGE."""

    commercial_option_id: UUID = Field(default_factory=uuid4)
    option_code: str
    option_name: str
    option_type: str = Field(default="service", description="service, insurance, maintenance")
    default_billing_unit: BillingUnit = BillingUnit.MONTHLY
    description: str = ""
    is_active: bool = True


# =========================================================================
# PriceBook + Version
# =========================================================================


class PriceBook(BaseModel):
    """Livre de prix : une collection de tarifs cohérents d'un type.

    Un PriceBook ne porte PAS de prix lui-même — c'est juste un header
    nommé (DL_STANDARD, HM_STANDARD, OM_STANDARD). Les prix vivent dans
    ses `PriceBookVersion`s successives (annuelles typiquement).
    """

    price_book_id: UUID = Field(default_factory=uuid4)
    price_book_code: str = Field(description="DL_STANDARD, HM_STANDARD, OM_STANDARD, WS_STANDARD")
    price_book_name: str
    price_type: PriceType
    currency_iso: str = Field(default="EUR", min_length=3, max_length=3)
    description: str = ""
    is_active: bool = True


class PriceBookVersion(BaseModel):
    """Version datée d'un PriceBook.

    Chaque année (ou semestre) l'équipe pricing publie une nouvelle version
    qui remplace l'ancienne à partir de `valid_from`. L'ancienne continue
    de s'appliquer aux offres déjà chiffrées (version gelée à l'offre).

    Workflow :
        draft → approved (par Head of Pricing)
              → published (ValidFrom atteint)
              → archived (une version plus récente publiée)
    """

    price_book_version_id: UUID = Field(default_factory=uuid4)
    price_book_id: UUID
    year: int = Field(ge=2000, le=2100)
    version_number: int = Field(ge=1, description="1, 2, 3 à l'intérieur d'une même année")
    status: PriceBookStatus = PriceBookStatus.DRAFT
    valid_from: date
    valid_to: date | None = None
    currency_iso: str = Field(default="EUR", min_length=3, max_length=3)
    approved_by: str | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    description: str = ""


# =========================================================================
# Tables spécialisées de tarifs
# =========================================================================


class DryLeaseRate(BaseModel):
    """Tarif Dry Lease pour (variante × country_group × lease_band × asset_age).

    Décompose le loyer en :
    - monthly_base_rent : loyer mensuel socle (perte de valeur + marge)
    - insurance_amount : prime d'assurance mensuelle
    - risk_provision_amount : provision pour risque (défaut client, bris)
    - specific_commitment_rate : surcoût engagement spécifique (%)
    """

    dry_lease_rate_id: UUID = Field(default_factory=uuid4)
    price_book_version_id: UUID
    technical_variant_id: UUID
    country_group_id: UUID
    lease_band_id: UUID
    asset_age_band_id: UUID
    monthly_base_rent: float = Field(gt=0)
    insurance_amount: float = Field(default=0, ge=0)
    risk_provision_amount: float = Field(default=0, ge=0)
    specific_commitment_rate: float = Field(default=0, ge=0, le=1, description="Fraction, 0.05 = +5%")
    minimum_price: float | None = Field(default=None, ge=0, description="Plancher absolu (dérogation)")
    currency_iso: str = "EUR"
    valid_from: date | None = None
    valid_to: date | None = None

    def total_mensuel(self) -> float:
        base = self.monthly_base_rent + self.insurance_amount + self.risk_provision_amount
        return base * (1 + self.specific_commitment_rate)


class HeavyMaintenanceRate(BaseModel):
    """Tarif HM pour (variante × opération × pays × atelier éventuel).

    Les HM sont facturées différemment selon la stratégie :
    - FIXED : montant forfaitaire par intervention (plus simple)
    - TIME_AND_MATERIAL : temps + pièces (plus réaliste mais complexe)
    - MONTHLY_PROVISION : lissage mensuel sur la durée du contrat
    """

    heavy_maintenance_rate_id: UUID = Field(default_factory=uuid4)
    price_book_version_id: UUID
    technical_variant_id: UUID
    operation_id: UUID
    country_group_id: UUID | None = None
    workshop_id: UUID | None = Field(default=None, description="None = tout atelier conforme")
    calculation_method: CalculationMethodHM = CalculationMethodHM.FIXED
    cost_amount: float = Field(ge=0, description="Coût interne (pas visible KAM)")
    selling_price: float = Field(gt=0, description="Prix vente KAM")
    billing_unit: BillingUnit = BillingUnit.PER_OPERATION
    monthly_provision_amount: float | None = Field(default=None, ge=0,
        description="Pour MONTHLY_PROVISION : montant mensuel équivalent")
    currency_iso: str = "EUR"
    valid_from: date | None = None
    valid_to: date | None = None


class OperatingMaintenanceRate(BaseModel):
    """Tarif OM — la structure la plus riche (section 11).

    Formule canonique (appliquée par `calculer_om_mensuel()`) :
        OM = MonthlyFixedAmount
           + (AnnualMileage × PricePerKilometer / 12)
           + (AnnualEngineHours × PricePerEngineHour / 12)
           + EcmMonthlyAmount
           + LastMileMonthlyAmount
    (+ options traitées séparément côté QuoteLine)

    `minimum_monthly_amount` et `maximum_annual_amount` fixent des bornes
    de validation (plancher, cap annuel).
    """

    operating_maintenance_rate_id: UUID = Field(default_factory=uuid4)
    price_book_version_id: UUID
    technical_variant_id: UUID
    country_id: UUID | None = None
    mileage_band_id: UUID
    engine_hours_band_id: UUID | None = None
    ecm_provider_id: UUID | None = None
    service_level_id: UUID | None = None
    monthly_fixed_amount: float = Field(default=0, ge=0)
    price_per_kilometer: float = Field(default=0, ge=0)
    price_per_engine_hour: float = Field(default=0, ge=0)
    ecm_monthly_amount: float = Field(default=0, ge=0)
    last_mile_monthly_amount: float = Field(default=0, ge=0)
    minimum_monthly_amount: float | None = Field(default=None, ge=0)
    maximum_annual_amount: float | None = Field(default=None, ge=0)
    currency_iso: str = "EUR"
    valid_from: date | None = None
    valid_to: date | None = None


# =========================================================================
# Moteur de prix v2 — résout un tarif + applique la formule
# =========================================================================


class ResolutionTarif(BaseModel):
    """Résultat intermédiaire : le tarif retenu + son détail."""

    technical_variant_code: str
    price_book_version_id: UUID
    annual_mileage_km: int
    annual_engine_hours: float | None = None
    duration_months: int
    age_years: float | None = None
    country_iso: str | None = None

    dl_retenu: float | None = None
    hm_mensuel_provisionne: float | None = None
    om_mensuel: float | None = None
    total_mensuel: float | None = None

    detail_om: dict = Field(default_factory=dict)
    detail_dl: dict = Field(default_factory=dict)
    detail_hm: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def calculer_om_mensuel(
    rate: OperatingMaintenanceRate,
    annual_mileage_km: int,
    annual_engine_hours: float = 0,
    options_monthly: float = 0,
) -> dict:
    """Applique la formule OM cible du doc (section 11).

    Retourne un dict `detail_om` avec les composants et le total mensuel,
    utilisable tel quel dans l'offre (explicabilité M2-05)."""

    composante_mileage = (annual_mileage_km * rate.price_per_kilometer) / 12
    composante_engine_h = (annual_engine_hours * rate.price_per_engine_hour) / 12
    detail = {
        "monthly_fixed": rate.monthly_fixed_amount,
        "mileage_component": composante_mileage,
        "engine_hours_component": composante_engine_h,
        "ecm_monthly": rate.ecm_monthly_amount,
        "last_mile_monthly": rate.last_mile_monthly_amount,
        "options_monthly": options_monthly,
    }
    total = sum(detail.values())

    # Application du plancher minimum
    if rate.minimum_monthly_amount is not None and total < rate.minimum_monthly_amount:
        detail["floor_applied"] = rate.minimum_monthly_amount - total
        total = rate.minimum_monthly_amount

    # Application du cap annuel
    if rate.maximum_annual_amount is not None:
        cap_mensuel = rate.maximum_annual_amount / 12
        if total > cap_mensuel:
            detail["cap_applied"] = total - cap_mensuel
            total = cap_mensuel

    detail["total_monthly"] = total
    return detail
