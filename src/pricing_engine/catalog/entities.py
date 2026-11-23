"""Entités du catalogue PricingHub (Lot 1 du doc Architecture Cible).

Hiérarchie reconstruite depuis l'analyse du configurateur Excel actuel :

    Manufacturer (Bombardier, Siemens, Alstom, Stadler…)
            │
    ProductFamily (Electric Locomotive, Diesel, Dual-Mode, Passenger Rolling Stock)
            │
    ProductPlatform (Traxx_AC, Traxx_MS, Vectron_MS, Vectron_AC, Eurodual…)
            │
    LocomotiveSeries (E185, E186, E187, 193…)  -- puissance / vitesse / effort
            │
    TechnicalVariant (E186-DABNL, E186-DBF, E185-DA, E185-DACH…) -- la vraie clé
            │
    VariantHomologation (M2M → Homologation → HomologationCountries)

Décision architecturale (section 16 du doc) :
    Locomotive  ≠ Mileage   (le mileage vit sur QuoteLine + UsageProfile)
    Locomotive  ≠ Prix       (les prix vivent dans PriceBookVersions)
    Série       ≠ Homologation (M2M, pas 1-1)
    Sous-série  ≠ Asset physique (une variante peut avoir plusieurs locos)

Tous les identifiants internes sont des UUID (pour supporter des ingestions
multi-sources sans collision), avec un `*Code` métier unique en plus pour
l'export / l'intégration avec les systèmes aval.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# Enums
# ============================================================================


class TractionMode(str, Enum):
    """Mode de traction d'une plateforme ou variante."""

    AC = "AC"           # Courant alternatif (15 kV ou 25 kV)
    DC = "DC"           # Courant continu (1.5 kV ou 3 kV)
    MS = "MS"           # Multi-system (AC + DC, exploitation transfrontalière)
    DE = "DE"           # Diesel-électrique
    DUAL = "DUAL"       # Dual-mode (électrique + diesel, Eurodual)
    BATTERY = "BATTERY" # Batterie / last-mile


class StatutHomologation(str, Enum):
    """État d'une homologation nationale."""

    PENDING = "pending"     # Dossier déposé, pas encore obtenue
    APPROVED = "approved"   # Homologation valide
    SUSPENDED = "suspended" # Suspendue (défaut technique, recall)
    EXPIRED = "expired"     # Expirée, non renouvelée


class ManufacturerStatut(str, Enum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"  # Site de production fermé / marque disparue


# ============================================================================
# Niveau 0 : Constructeurs et pays (dimensions partagées)
# ============================================================================


class Manufacturer(BaseModel):
    """Constructeur de matériel roulant (Bombardier, Siemens, Alstom, Stadler…).

    Depuis la fusion Bombardier Transportation → Alstom (2021), certaines
    locomotives TRAXX sont désormais estampillées Alstom. On garde les deux
    identités séparées : le matériel conserve son constructeur d'origine,
    la relation commerciale pointe vers l'entité actuelle.
    """

    manufacturer_id: UUID = Field(default_factory=uuid4)
    code: str = Field(description="Code court unique, ex. BOMBARDIER, SIEMENS")
    name: str
    country_of_origin_iso: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    parent_company: str | None = None
    statut: ManufacturerStatut = ManufacturerStatut.ACTIVE
    is_active: bool = True


class Country(BaseModel):
    """Pays où une homologation peut être demandée.

    Référentiel ISO 3166-1 alpha-2. La table existe pour supporter les
    network codes nationaux (DB Netz pour DE, SNCF Réseau pour FR, PKP PLK
    pour PL…) qui vivent sur `HomologationCountry.network_code`.
    """

    country_id: UUID = Field(default_factory=uuid4)
    iso_alpha2: str = Field(min_length=2, max_length=2)
    name_fr: str
    name_en: str
    default_network_code: str | None = None
    is_eu_member: bool = True
    is_active: bool = True


# ============================================================================
# Niveau 1-4 : Hiérarchie catalogue
# ============================================================================


class ProductFamily(BaseModel):
    """Niveau 1 — famille métier la plus large.

    Exemples : Electric Locomotive, Diesel Locomotive, Dual-Mode Locomotive,
    Passenger Rolling Stock. Sert à filtrer les offres par métier dans les
    rapports Direction.
    """

    product_family_id: UUID = Field(default_factory=uuid4)
    family_code: str
    family_name: str
    description: str = ""
    is_active: bool = True


class ProductPlatform(BaseModel):
    """Niveau 2 — plateforme produit chez le constructeur.

    Ex. TRAXX_AC, TRAXX_MS, VECTRON_MS, VECTRON_AC, EURODUAL. C'est la
    « marque commerciale » la plus utilisée dans le marketing Akiem et dans
    la colonne Product du configurateur actuel.
    """

    product_platform_id: UUID = Field(default_factory=uuid4)
    product_family_id: UUID
    platform_code: str = Field(description="ex. TRAXX_MS, VECTRON_AC")
    platform_name: str = Field(description="ex. Traxx Multi-System")
    manufacturer_id: UUID
    traction_mode: TractionMode
    description: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True


class LocomotiveSeries(BaseModel):
    """Niveau 3 — série au sens technique (E185, E186, E187, 193…).

    Porte les caractéristiques techniques partagées par toutes les variantes
    de la série : puissance nominale, vitesse maximale, effort de traction
    au démarrage. Ces valeurs sont indicatives ; la variante peut les affiner.
    """

    series_id: UUID = Field(default_factory=uuid4)
    product_platform_id: UUID
    series_code: str = Field(description="ex. E186, E187, 193")
    series_name: str
    nominal_power_kw: float | None = Field(default=None, ge=0, description="Puissance continue en kW")
    maximum_speed_kmh: int | None = Field(default=None, ge=0, le=400)
    starting_tractive_effort_kn: float | None = Field(default=None, ge=0, description="Effort au démarrage en kN")
    traction_mode: TractionMode | None = None
    production_start_year: int | None = None
    production_end_year: int | None = None
    is_active: bool = True


class TechnicalVariant(BaseModel):
    """Niveau 4 — variante technique, LA clé de calcul tarifaire.

    Chaque série se décline en variantes qui dépendent du périmètre
    d'homologation et de la configuration technique. E186-DABNL pour
    Allemagne+Autriche+Belgique+Pays-Bas, E186-DBF pour +France, etc.

    Les colonnes `nominal_power_kw` / `maximum_speed_kmh` / `starting_tractive_effort_kn`
    peuvent affiner celles de la série (certaines variantes sont plafonnées
    par l'homologation locale). Si None, hériter de la série.

    `manufacturing_year_from/to` bornent la période de production de cette
    variante — utile pour les rebuilds et les séries longue durée.

    `default_ecm_provider_id` pointe vers l'ECM Provider par défaut (Lot 2).
    """

    technical_variant_id: UUID = Field(default_factory=uuid4)
    series_id: UUID
    variant_code: str = Field(description="ex. E186-DABNL, E186-DBF")
    variant_name: str
    manufacturer_model_name: str = Field(description="Nom commercial, ex. TRAXX F140 MS")
    technical_configuration_code: str = Field(
        description="Code configuration combiné ex. Traxx_MS|E186-DABNL",
    )
    traction_mode: TractionMode | None = None
    nominal_power_kw: float | None = Field(default=None, ge=0)
    maximum_speed_kmh: int | None = Field(default=None, ge=0, le=400)
    starting_tractive_effort_kn: float | None = Field(default=None, ge=0)
    manufacturing_year_from: int | None = None
    manufacturing_year_to: int | None = None
    default_ecm_provider_id: UUID | None = None
    is_active: bool = True


# ============================================================================
# Homologations (relation M2M : une série a plusieurs homologations, chaque
# homologation couvre plusieurs pays / réseaux).
# ============================================================================


class Homologation(BaseModel):
    """Package d'homologation (ex. DABNL = DE+AT+BE+NL approved together).

    Un package homologation est généralement obtenu en bloc auprès de
    l'ERA + agences nationales après tests croisés. Le code est souvent
    la concaténation des codes pays (DABNL, DACH, DABF…).
    """

    homologation_id: UUID = Field(default_factory=uuid4)
    homologation_code: str = Field(description="ex. DABNL, DACH, DABF")
    homologation_name: str
    description: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    status: StatutHomologation = StatutHomologation.APPROVED


class VariantHomologation(BaseModel):
    """Association M2M TechnicalVariant ↔ Homologation.

    `is_standard` = True si cette homologation vient en standard sur la
    variante ; False si elle a été ajoutée après coup (surcoût).
    `additional_cost` = surcoût éventuel versus la variante nue.
    """

    technical_variant_id: UUID
    homologation_id: UUID
    is_standard: bool = True
    additional_cost: float = Field(default=0, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None


class HomologationCountry(BaseModel):
    """Détail des pays couverts par une homologation + code réseau national.

    Une même homologation peut couvrir plusieurs pays (DABNL = 4 pays),
    et chaque pays peut avoir plusieurs réseaux (en Allemagne : DB Netz,
    VPE, SBB Cargo DE…). Le `network_code` précise lequel.
    """

    homologation_id: UUID
    country_id: UUID
    network_code: str | None = Field(default=None, description="DB_NETZ, SNCF_RESEAU, PKP_PLK…")
    is_approved: bool = True
    valid_from: date | None = None
    valid_to: date | None = None


# ============================================================================
# Audit trail commun — toute entité du catalogue est horodatée.
# ============================================================================


class AuditTrail(BaseModel):
    """Commun à toutes les tables catalog.* : créé/modifié par qui, quand.

    Pas exposé en API dans ce lot (on garde les entités plus simples), mais
    réservé pour la couche persistance (Lot 2 ou 3).
    """

    created_at: datetime = Field(default_factory=_now_utc)
    created_by: str = "system"
    updated_at: datetime = Field(default_factory=_now_utc)
    updated_by: str = "system"
    version: int = 1
