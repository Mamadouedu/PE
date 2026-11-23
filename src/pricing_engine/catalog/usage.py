"""Profils d'usage, paliers de mileage et heures moteur (Lot 2).

Point clé du document Architecture Cible (section 5) :
Le mileage **n'est pas** une propriété fixe de la série. C'est une
caractéristique du contrat, qui dépend :
- du client,
- du pays,
- du rythme d'utilisation,
- du type d'exploitation,
- de la durée,
- du profil de maintenance,
- parfois de l'option ECM.

Donc : TechnicalVariant ↔ UsageProfile est **M2M** (une variante supporte
plusieurs profils d'usage avec contraintes différentes), et MileageBand
définit les paliers tarifaires OM (OM_080_120, OM_120_160, OM_160_200, etc.)
dont les seuils doivent être repris du configurateur réel, pas inventés.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UtilisationType(str, Enum):
    """Type d'exploitation pour lequel un profil d'usage est conçu."""

    FREIGHT = "freight"             # Fret / marchandises
    PASSENGER = "passenger"         # Voyageurs
    SHUNTING = "shunting"           # Manœuvres
    MIXED = "mixed"                 # Mixte
    LAST_MILE = "last_mile"         # Dernier kilomètre (zones non électrifiées)


class CalculationMethod(str, Enum):
    """Méthode de calcul appliquée sur un palier de mileage pour OM.

    - LINEAR : tarif unique à l'intérieur du palier (OM = PricePerKm × km)
    - PROGRESSIVE : tarif croissant par tranche
    - FLAT : montant mensuel fixe, indépendant du km effectif dans le palier
    """

    LINEAR = "linear"
    PROGRESSIVE = "progressive"
    FLAT = "flat"


class UsageProfile(BaseModel):
    """Profil d'usage standardisé (LOW / STANDARD / HIGH / VERY_HIGH mileage).

    Un profil borne un intervalle de mileage annuel et d'heures moteur
    typique. Les seuils ne sont pas inventés : ils doivent être repris
    des valeurs réellement utilisées dans le configurateur Excel actuel.
    """

    usage_profile_id: UUID = Field(default_factory=uuid4)
    usage_profile_code: str = Field(description="LOW_MILEAGE, STANDARD_MILEAGE, HIGH_MILEAGE, VERY_HIGH_MILEAGE")
    usage_profile_name: str
    annual_mileage_min_km: int | None = Field(default=None, ge=0)
    annual_mileage_max_km: int | None = Field(default=None, ge=0)
    annual_engine_hours_min: float | None = Field(default=None, ge=0)
    annual_engine_hours_max: float | None = Field(default=None, ge=0)
    monthly_mileage_min_km: int | None = Field(default=None, ge=0)
    monthly_mileage_max_km: int | None = Field(default=None, ge=0)
    utilisation_type: UtilisationType = UtilisationType.FREIGHT
    description: str = ""
    is_active: bool = True


class MileageBand(BaseModel):
    """Palier de mileage pour les tarifs OM.

    Le configurateur découpe l'espace km/an en paliers dont la granularité
    peut varier selon la série. Les paliers canoniques observés :
    OM_000_080, OM_080_120, OM_120_160, OM_160_200, OM_200_240, OM_240_PLUS.

    Le même palier peut être associé à plusieurs variantes avec des prix
    différents dans les PriceBookLines (Lot 3).
    """

    mileage_band_id: UUID = Field(default_factory=uuid4)
    band_code: str = Field(description="OM_000_080, OM_080_120, OM_120_160, OM_160_200, OM_200_240, OM_240_PLUS")
    band_name: str
    min_annual_mileage_km: int = Field(ge=0)
    max_annual_mileage_km: int | None = Field(default=None, ge=0, description="None = pas de borne haute (OM_240_PLUS)")
    calculation_method: CalculationMethod = CalculationMethod.LINEAR
    is_active: bool = True

    def contient(self, annual_km: int) -> bool:
        if annual_km < self.min_annual_mileage_km:
            return False
        if self.max_annual_mileage_km is None:
            return True
        return annual_km < self.max_annual_mileage_km


class EngineHoursBand(BaseModel):
    """Palier d'heures moteur annuelles (symétrique à MileageBand).

    Utile pour les tarifs OM qui facturent au `PricePerEngineHour` (section
    11 du doc) — typiquement les plans diesel et dual-mode où l'usure du
    moteur thermique ne se corrèle pas 1-1 aux km parcourus."""

    engine_hours_band_id: UUID = Field(default_factory=uuid4)
    band_code: str = Field(description="EH_000_500, EH_500_1500, EH_1500_3000, EH_3000_PLUS")
    band_name: str
    min_annual_engine_hours: float = Field(ge=0)
    max_annual_engine_hours: float | None = Field(default=None, ge=0)
    is_active: bool = True


class VariantUsageProfile(BaseModel):
    """M2M entre TechnicalVariant et UsageProfile avec contraintes.

    Du doc : « une variante peut accepter Standard Mileage, High Mileage,
    Very High Mileage avec validation ». Ce record porte cette information :
    - is_supported : la variante accepte-t-elle ce profil
    - warning_threshold_km : au-delà, l'offre génère un avertissement
    - maximum_contractual_mileage_km : plafond contractuel absolu
    - requires_specific_approval : la combinaison exige une dérogation
    """

    technical_variant_id: UUID
    usage_profile_id: UUID
    is_supported: bool = True
    warning_threshold_km: int | None = Field(default=None, ge=0)
    maximum_contractual_mileage_km: int | None = Field(default=None, ge=0)
    requires_specific_approval: bool = False
    valid_from: date | None = None
    valid_to: date | None = None


class VariantMileageBand(BaseModel):
    """M2M entre TechnicalVariant et MileageBand.

    Certaines variantes ne supportent qu'un sous-ensemble des paliers
    (ex. une TRAXX AC dédiée fret léger peut ne pas accepter le palier
    OM_240_PLUS)."""

    technical_variant_id: UUID
    mileage_band_id: UUID
    is_supported: bool = True
    valid_from: date | None = None
    valid_to: date | None = None
