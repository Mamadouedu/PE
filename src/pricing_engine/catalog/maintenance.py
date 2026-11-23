"""Opérations et plans de maintenance + fournisseurs ECM + niveaux de
service (Lot 2, sections 10 et 11 du doc Architecture Cible).

Décision structurante : HM ne doit PAS être un montant unique porté par
la série. Le HM dépend de :
- la variante technique,
- l'opération (révision HM-1 / HM-2 / HM-3 / changement bogies / ...),
- le cycle ou l'échéance (mileage, engine hours, calendar, mixed),
- le mileage réel,
- les engine hours réelles,
- le pays ou l'atelier,
- la date d'application.

Ce module modélise :
- MaintenanceOperation : la définition d'une opération HM
- MaintenancePlan : groupement d'opérations (ex. plan « Standard TRAXX MS »)
- MaintenancePlanOperation : M2M avec l'ordre et les conditions
- EcmProvider : fournisseurs ECM (AMS, Bombardier ECM, Siemens Mobility ECM)
- ServiceLevel : niveaux de service (Basic, Standard, Premium, 24/7)

Les tarifs (coût € par opération, HeavyMaintenanceRates) vivront dans le
Lot 3 (PriceBook).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OperationType(str, Enum):
    """Catégorie d'opération de maintenance."""

    HM = "HM"           # Heavy Maintenance (révision majeure)
    PM = "PM"           # Preventive Maintenance (entretien courant)
    CM = "CM"           # Corrective Maintenance (réparation)
    CHECK = "CHECK"     # Contrôle / inspection


class TriggerType(str, Enum):
    """Déclencheur d'une opération de maintenance.

    - MILEAGE : tous les N km (ex. HM-2 tous les 1 200 000 km)
    - ENGINE_HOURS : toutes les N heures moteur
    - CALENDAR : tous les N mois (ex. VGI annuelle)
    - MIXED : premier des N déclencheurs qui tombe (le plus courant)
    """

    MILEAGE = "mileage"
    ENGINE_HOURS = "engine_hours"
    CALENDAR = "calendar"
    MIXED = "mixed"


class ServiceLevelCode(str, Enum):
    """Niveau de service d'un contrat."""

    BASIC = "BASIC"             # Heures ouvrables, pas de hotline
    STANDARD = "STANDARD"       # Hotline en heures ouvrables étendues
    PREMIUM = "PREMIUM"         # Hotline 7j/7, priorité intervention
    H24 = "H24"                 # 24/7 incluant garantie de temps de réponse


class MaintenanceOperation(BaseModel):
    """Opération de maintenance individuelle (HM-1, HM-2, HM-3, bogie swap…).

    Chaque opération a un déclencheur et des intervalles. Au moins un
    intervalle doit être renseigné selon le TriggerType :
    - MILEAGE → interval_mileage_km obligatoire
    - ENGINE_HOURS → interval_engine_hours obligatoire
    - CALENDAR → interval_months obligatoire
    - MIXED → au moins deux des trois intervalles doivent être renseignés
    """

    operation_id: UUID = Field(default_factory=uuid4)
    operation_code: str = Field(description="HM1, HM2, HM3, BOGIE_SWAP, VGI, WHEEL_REPROFILING")
    operation_name: str
    operation_type: OperationType = OperationType.HM
    trigger_type: TriggerType = TriggerType.MILEAGE
    interval_mileage_km: int | None = Field(default=None, ge=0)
    interval_engine_hours: float | None = Field(default=None, ge=0)
    interval_months: int | None = Field(default=None, ge=0)
    standard_duration_hours: float | None = Field(default=None, ge=0, description="Temps immobilisation moyen")
    description: str = ""
    is_active: bool = True


class MaintenancePlan(BaseModel):
    """Plan de maintenance : ensemble cohérent d'opérations.

    Un plan nomme la stratégie de maintenance d'une famille de variantes.
    Ex. « TRAXX_MS_STANDARD », « VECTRON_HEAVY_DUTY », « EURODUAL_BIMODE ».
    Les opérations incluses, leur ordre et leurs conditions vivent dans
    MaintenancePlanOperation."""

    maintenance_plan_id: UUID = Field(default_factory=uuid4)
    plan_code: str = Field(description="TRAXX_MS_STANDARD, VECTRON_HEAVY_DUTY")
    plan_name: str
    manufacturer_id: UUID | None = None
    description: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True


class MaintenancePlanOperation(BaseModel):
    """M2M MaintenancePlan ↔ MaintenanceOperation avec contexte.

    - sequence_order : ordre d'application (1, 2, 3...)
    - is_optional : True si l'opération est optionnelle dans ce plan
    - frequency_multiplier : permet de dire « HM-1 tous les 2 cycles »
      sans redéfinir l'opération
    """

    maintenance_plan_id: UUID
    operation_id: UUID
    sequence_order: int = Field(ge=0, default=0)
    is_optional: bool = False
    frequency_multiplier: float = Field(default=1.0, gt=0)


class VariantMaintenancePlan(BaseModel):
    """M2M TechnicalVariant ↔ MaintenancePlan.

    Une variante peut avoir plusieurs plans (standard, intensif, mixte).
    Le plan par défaut est celui avec `is_default=True`."""

    technical_variant_id: UUID
    maintenance_plan_id: UUID
    is_default: bool = False
    valid_from: date | None = None
    valid_to: date | None = None


class EcmProvider(BaseModel):
    """Fournisseur ECM (Entité en Charge de la Maintenance) — règlement
    européen (UE) 445/2011 et évolutions.

    Exemples : AMS, Bombardier ECM, Siemens Mobility ECM, Alstom Services,
    Stadler Service."""

    ecm_provider_id: UUID = Field(default_factory=uuid4)
    provider_code: str = Field(description="AMS, BOMBARDIER_ECM, SIEMENS_ECM, ALSTOM_SERVICES, STADLER_SERVICE")
    provider_name: str
    certification_number: str | None = Field(default=None, description="Numéro de certificat ECM")
    certification_valid_from: date | None = None
    certification_valid_to: date | None = None
    description: str = ""
    is_active: bool = True


class ServiceLevel(BaseModel):
    """Niveau de service inclus dans un contrat.

    Un niveau de service précise :
    - les heures de disponibilité du support
    - le temps de réponse garanti (RTO)
    - la hotline incluse
    - les options (last-mile, reprofilage de roues...)
    """

    service_level_id: UUID = Field(default_factory=uuid4)
    service_level_code: ServiceLevelCode = ServiceLevelCode.STANDARD
    service_level_name: str
    hotline_included: bool = False
    hotline_coverage: str | None = Field(default=None, description="ex. 24/7, 6h-22h, heures ouvrables")
    response_time_hours: float | None = Field(default=None, ge=0, description="RTO garanti")
    description: str = ""
    is_active: bool = True
