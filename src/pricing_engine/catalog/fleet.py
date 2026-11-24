"""Flotte réelle PricingHub (Lot 5, section 12 du doc Architecture Cible).

Distinction fondamentale, section 12 : un FleetAsset est une locomotive
physique identifiable par son numéro d'immatriculation, tandis qu'une
TechnicalVariant est un type auquel plusieurs FleetAssets appartiennent.

    TechnicalVariant   : E186-DABNL (type)
         ↓
    FleetAsset         : Locomotive n° BR186-101 (instance physique)

Cas d'usage :
- Un QuoteLine générique « 2 × E186-DABNL » peut rester sans FleetAsset
  attaché : c'est une offre de flotte, Akiem choisira les locos au
  moment de la mise en service.
- Un QuoteLine spécifique « la BR186-101 » pointe sur un FleetAsset :
  c'est un deal sur une loco nommée (renouvellement de contrat, SPV
  dédié, ancienne loco relouée).

Deux tables de suivi opérationnel accompagnent FleetAsset :
- AssetMeterReading : relevés compteurs (km, engine hours, dates)
  permettent de planifier la prochaine HM
- AssetMaintenanceHistoryEntry : historique des opérations réalisées
  (quelle HM, quand, où, par qui, montant payé)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class OwnershipStatus(str, Enum):
    """Statut de propriété de la locomotive."""

    OWNED = "owned"             # Akiem propriétaire
    LEASED_IN = "leased_in"     # Akiem sous-loue depuis un tiers
    PARTNER = "partner"         # Partenariat (JV, SPV)


class OperationalStatus(str, Enum):
    """État opérationnel courant de la locomotive."""

    AVAILABLE = "available"             # Disponible à la location
    LEASED = "leased"                   # En location chez un client
    IN_MAINTENANCE = "in_maintenance"   # En atelier (HM, PM, CM)
    STORED = "stored"                   # Immobilisée (pas de contrat)
    DECOMMISSIONED = "decommissioned"   # Déclassée / vendue


class MaintenanceEventStatus(str, Enum):
    """Statut d'une opération de maintenance planifiée ou réalisée."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FleetAsset(BaseModel):
    """Locomotive physique de la flotte Akiem.

    Identifiée par son `asset_number` (interne Akiem, ex. AK-00042) et
    son `vehicle_registration_number` (numéro officiel réseau, ex.
    BR186-101 ou 91 80 6193 901-2 D-AKIEM).

    Pointe vers son TechnicalVariantId : la loco est typée par sa variante
    (E186-DABNL) même si ses caractéristiques réelles (km cumulés, âge,
    pays courant, ECM courant) évoluent dans le temps.
    """

    fleet_asset_id: UUID = Field(default_factory=uuid4)
    asset_number: str = Field(description="Ex. AK-00042, identifiant interne Akiem")
    vehicle_registration_number: str = Field(description="Ex. 91 80 6193 901-2 D-AKIEM, N° UIC 12 chiffres")
    technical_variant_id: UUID
    manufacturing_year: int = Field(ge=1950, le=2100)
    commissioning_date: date
    ownership_status: OwnershipStatus = OwnershipStatus.OWNED
    operational_status: OperationalStatus = OperationalStatus.AVAILABLE

    # État courant (mis à jour via AssetMeterReading)
    current_country_id: UUID | None = None
    current_mileage_km: float = Field(default=0, ge=0)
    current_engine_hours: float = Field(default=0, ge=0)
    current_ecm_provider_id: UUID | None = None

    # Métadonnées administratives
    last_hm1_date: date | None = None
    last_hm2_date: date | None = None
    last_hm3_date: date | None = None
    last_bogie_swap_date: date | None = None
    last_vgi_date: date | None = None

    notes: str = ""
    is_active: bool = True

    def age_years(self, at_date: date | None = None) -> float:
        """Âge de la locomotive à une date donnée (par défaut : aujourd'hui)."""
        ref = at_date or date.today()
        return (ref - self.commissioning_date).days / 365.25


class AssetMeterReading(BaseModel):
    """Relevé compteur à une date donnée.

    Les compteurs km et engine_hours sont monotonement croissants. Un
    nouveau relevé met à jour `FleetAsset.current_mileage_km` et
    `current_engine_hours` par convention (dernier relevé fait foi).

    Source possible : télémétrie embarquée, relevé atelier, déclaration
    client, inventaire physique.
    """

    meter_reading_id: UUID = Field(default_factory=uuid4)
    fleet_asset_id: UUID
    reading_date: date
    mileage_km: float = Field(ge=0)
    engine_hours: float = Field(default=0, ge=0)
    country_iso: str | None = Field(default=None, min_length=2, max_length=2)
    source: str = Field(default="telemetry",
        description="telemetry, workshop, client_declaration, physical_inventory")
    recorded_by: str = "system"
    recorded_at: datetime = Field(default_factory=_now_utc)
    notes: str = ""


class AssetMaintenanceHistoryEntry(BaseModel):
    """Opération de maintenance réalisée ou planifiée sur une locomotive.

    Permet de reconstituer l'historique complet HM/PM/CM pour :
    - calculer les prochaines échéances à partir des dernières dates
    - alimenter les contrôles de contrat (révision due dans X km)
    - produire les reportings ECM réglementaires (UE 445/2011)
    """

    maintenance_history_id: UUID = Field(default_factory=uuid4)
    fleet_asset_id: UUID
    operation_id: UUID = Field(description="FK vers MaintenanceOperation du Lot 2")
    operation_code: str = Field(description="Dénormalisé pour l'affichage sans join")
    status: MaintenanceEventStatus = MaintenanceEventStatus.COMPLETED
    planned_date: date | None = None
    started_at: date | None = None
    completed_at: date | None = None
    workshop_name: str | None = Field(default=None, description="Ex. Akiem Oberursel, DB Cottbus")
    workshop_country_iso: str | None = None
    ecm_provider_id: UUID | None = None

    # Valeurs compteurs à l'intervention (pour corréler avec AssetMeterReading)
    mileage_km_at_event: float | None = Field(default=None, ge=0)
    engine_hours_at_event: float | None = Field(default=None, ge=0)

    # Coûts (optionnels, peuvent être masqués au KAM selon permissions)
    actual_cost_amount: float | None = Field(default=None, ge=0)
    billed_amount: float | None = Field(default=None, ge=0)

    technician_notes: str = ""
    recorded_by: str = "system"
    recorded_at: datetime = Field(default_factory=_now_utc)


class FleetAssetSummary(BaseModel):
    """Vue agrégée d'un FleetAsset pour les listings et dashboards.

    Combine l'état courant + les prochaines échéances HM calculées à
    partir de l'historique et des intervalles des MaintenanceOperation.
    """

    fleet_asset_id: UUID
    asset_number: str
    vehicle_registration_number: str
    technical_variant_code: str
    operational_status: OperationalStatus
    ownership_status: OwnershipStatus
    current_mileage_km: float
    current_engine_hours: float
    age_years: float
    manufacturing_year: int
    current_country_iso: str | None = None

    # Jalons calculés
    next_hm1_due_km: float | None = None
    next_hm2_due_km: float | None = None
    next_hm3_due_km: float | None = None
    next_vgi_due_date: date | None = None
    km_until_next_hm: float | None = None
