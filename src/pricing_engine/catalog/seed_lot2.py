"""Seed Lot 2 : profils d'usage, paliers, opérations et plans de maintenance.

Les seuils des `MileageBand` sont les paliers observés dans le configurateur
Excel analysé (section 6 du doc) : 80, 120, 160, 200, 240 x 1000 km/an.

Les profils d'usage correspondent aux catégories standard du marché :
- LOW_MILEAGE   : fret occasionnel, trafic local
- STANDARD_MILEAGE : fret régional / national (profil dominant)
- HIGH_MILEAGE  : international, corridors Rhin-Alpes
- VERY_HIGH_MILEAGE : rotations intensives, exige une approbation

Les opérations HM sont celles du plan standard TRAXX (HM-1 à 600k km,
HM-2 à 1 200k km, HM-3 à 1 800k km, swap bogies à 2 400k km) et des
contrôles réglementaires (VGI annuelle, reprofilage roues).
"""

from __future__ import annotations

from datetime import date

from .maintenance import (
    EcmProvider,
    MaintenanceOperation,
    MaintenancePlan,
    MaintenancePlanOperation,
    OperationType,
    ServiceLevel,
    ServiceLevelCode,
    TriggerType,
    VariantMaintenancePlan,
)
from .store import CatalogStore
from .usage import (
    CalculationMethod,
    EngineHoursBand,
    MileageBand,
    UsageProfile,
    UtilisationType,
    VariantMileageBand,
    VariantUsageProfile,
)


# Profils d'usage standards
USAGE_PROFILES = [
    ("LOW_MILEAGE", "Low mileage (fret occasionnel)", 0, 80_000, 0, 500, UtilisationType.FREIGHT),
    ("STANDARD_MILEAGE", "Standard mileage (fret régional)", 80_000, 160_000, 500, 2_000, UtilisationType.FREIGHT),
    ("HIGH_MILEAGE", "High mileage (international)", 160_000, 220_000, 2_000, 4_000, UtilisationType.FREIGHT),
    ("VERY_HIGH_MILEAGE", "Very high mileage (rotations intensives)", 220_000, None, 4_000, None, UtilisationType.FREIGHT),
    ("SHUNTING_INTENSE", "Shunting intensif (manœuvres)", 0, 40_000, 2_000, 6_000, UtilisationType.SHUNTING),
    ("LAST_MILE", "Last-mile (zones non électrifiées)", 0, 60_000, 500, 2_500, UtilisationType.LAST_MILE),
]

# Paliers de mileage OM (section 6)
MILEAGE_BANDS = [
    ("OM_000_080", "0 à 80 000 km/an", 0, 80_000, CalculationMethod.LINEAR),
    ("OM_080_120", "80 000 à 120 000 km/an", 80_000, 120_000, CalculationMethod.LINEAR),
    ("OM_120_160", "120 000 à 160 000 km/an", 120_000, 160_000, CalculationMethod.LINEAR),
    ("OM_160_200", "160 000 à 200 000 km/an", 160_000, 200_000, CalculationMethod.LINEAR),
    ("OM_200_240", "200 000 à 240 000 km/an", 200_000, 240_000, CalculationMethod.LINEAR),
    ("OM_240_PLUS", "Au-delà de 240 000 km/an", 240_000, None, CalculationMethod.PROGRESSIVE),
]

# Paliers d'heures moteur annuelles
ENGINE_HOURS_BANDS = [
    ("EH_0000_0500", "0 à 500 h/an", 0, 500),
    ("EH_0500_1500", "500 à 1 500 h/an", 500, 1_500),
    ("EH_1500_3000", "1 500 à 3 000 h/an", 1_500, 3_000),
    ("EH_3000_6000", "3 000 à 6 000 h/an", 3_000, 6_000),
    ("EH_6000_PLUS", "Au-delà de 6 000 h/an", 6_000, None),
]

# Opérations de maintenance HM typiques TRAXX / VECTRON
MAINTENANCE_OPERATIONS = [
    # HM-1 à 600 000 km (révision intermédiaire)
    ("HM1", "Révision intermédiaire HM-1", OperationType.HM, TriggerType.MIXED,
     600_000, None, 48, 72),
    # HM-2 à 1 200 000 km
    ("HM2", "Révision principale HM-2", OperationType.HM, TriggerType.MIXED,
     1_200_000, None, 96, 240),
    # HM-3 à 1 800 000 km
    ("HM3", "Révision majeure HM-3", OperationType.HM, TriggerType.MIXED,
     1_800_000, None, 144, 480),
    # Changement bogies à 2 400 000 km
    ("BOGIE_SWAP", "Échange bogies", OperationType.HM, TriggerType.MILEAGE,
     2_400_000, None, None, 720),
    # VGI annuelle
    ("VGI", "Visite générale intermédiaire (annuelle)", OperationType.CHECK, TriggerType.CALENDAR,
     None, None, 12, 24),
    # Reprofilage roues
    ("WHEEL_REPROFILING", "Reprofilage de roues", OperationType.PM, TriggerType.MILEAGE,
     300_000, None, None, 48),
    # Révision moteur thermique (dual-mode / diesel)
    ("DIESEL_OVERHAUL", "Révision moteur thermique", OperationType.HM, TriggerType.ENGINE_HOURS,
     None, 12_000, None, 360),
]

# Plans de maintenance
MAINTENANCE_PLANS = [
    ("TRAXX_MS_STANDARD", "TRAXX MS - Plan standard", "BOMBARDIER",
     ["VGI", "WHEEL_REPROFILING", "HM1", "HM2", "HM3"]),
    ("TRAXX_MS_INTENSIVE", "TRAXX MS - Plan intensif haut mileage", "BOMBARDIER",
     ["VGI", "WHEEL_REPROFILING", "HM1", "HM2", "HM3", "BOGIE_SWAP"]),
    ("VECTRON_STANDARD", "VECTRON - Plan standard", "SIEMENS",
     ["VGI", "WHEEL_REPROFILING", "HM1", "HM2", "HM3"]),
    ("EURODUAL_STANDARD", "EURODUAL - Plan dual-mode", "STADLER",
     ["VGI", "WHEEL_REPROFILING", "HM1", "HM2", "DIESEL_OVERHAUL"]),
]

# Fournisseurs ECM
ECM_PROVIDERS = [
    ("AMS", "Akiem Maintenance Services", "FR-ECM-2019-042",
     "ECM interne Akiem, couverture Europe de l'Ouest"),
    ("BOMBARDIER_ECM", "Bombardier ECM (now Alstom Services)", "DE-ECM-2015-018",
     "ECM constructeur, spécialisé TRAXX"),
    ("SIEMENS_ECM", "Siemens Mobility ECM", "DE-ECM-2016-031",
     "ECM constructeur, spécialisé VECTRON"),
    ("STADLER_SERVICE", "Stadler Service", "CH-ECM-2020-005",
     "ECM constructeur, spécialisé EURODUAL"),
    ("DB_MAINTENANCE", "DB Fahrzeuginstandhaltung", "DE-ECM-2012-001",
     "ECM Deutsche Bahn, réseau atelier DE"),
]

# Niveaux de service
SERVICE_LEVELS = [
    (ServiceLevelCode.BASIC, "Basic", False, None, None,
     "Support par ticket, heures ouvrables uniquement"),
    (ServiceLevelCode.STANDARD, "Standard", True, "6h-22h, 7j/7", 24.0,
     "Hotline étendue, RTO 24h"),
    (ServiceLevelCode.PREMIUM, "Premium", True, "24/7", 8.0,
     "Hotline 24/7, RTO 8h, priorité intervention"),
    (ServiceLevelCode.H24, "24/7 garanti", True, "24/7", 4.0,
     "Hotline 24/7, RTO 4h garanti contractuellement"),
]


def seed_lot2(store: CatalogStore) -> None:
    """Peuple le store avec les données Lot 2. Suppose que le Lot 1 (seed
    catalog Akiem) a déjà été appliqué."""

    # Fournisseurs ECM
    ecm_par_code: dict[str, EcmProvider] = {}
    for code, name, cert, desc in ECM_PROVIDERS:
        e = store.upsert_ecm_provider(EcmProvider(
            provider_code=code, provider_name=name,
            certification_number=cert, description=desc,
            certification_valid_from=date(2020, 1, 1),
        ))
        ecm_par_code[code] = e

    # Niveaux de service
    for code, name, hotline, coverage, rto, desc in SERVICE_LEVELS:
        store.upsert_service_level(ServiceLevel(
            service_level_code=code, service_level_name=name,
            hotline_included=hotline, hotline_coverage=coverage,
            response_time_hours=rto, description=desc,
        ))

    # Profils d'usage
    usage_par_code: dict[str, UsageProfile] = {}
    for code, name, km_min, km_max, h_min, h_max, util in USAGE_PROFILES:
        u = store.upsert_usage_profile(UsageProfile(
            usage_profile_code=code, usage_profile_name=name,
            annual_mileage_min_km=km_min, annual_mileage_max_km=km_max,
            annual_engine_hours_min=h_min, annual_engine_hours_max=h_max,
            monthly_mileage_min_km=km_min // 12 if km_min else 0,
            monthly_mileage_max_km=km_max // 12 if km_max else None,
            utilisation_type=util,
        ))
        usage_par_code[code] = u

    # Paliers mileage
    bands_par_code: dict[str, MileageBand] = {}
    for code, name, k_min, k_max, method in MILEAGE_BANDS:
        b = store.upsert_mileage_band(MileageBand(
            band_code=code, band_name=name,
            min_annual_mileage_km=k_min, max_annual_mileage_km=k_max,
            calculation_method=method,
        ))
        bands_par_code[code] = b

    # Paliers heures moteur
    for code, name, h_min, h_max in ENGINE_HOURS_BANDS:
        store.upsert_engine_hours_band(EngineHoursBand(
            band_code=code, band_name=name,
            min_annual_engine_hours=h_min, max_annual_engine_hours=h_max,
        ))

    # Opérations de maintenance
    op_par_code: dict[str, MaintenanceOperation] = {}
    for code, name, op_type, trig, km, hrs, mo, duree in MAINTENANCE_OPERATIONS:
        o = store.upsert_maintenance_operation(MaintenanceOperation(
            operation_code=code, operation_name=name,
            operation_type=op_type, trigger_type=trig,
            interval_mileage_km=km, interval_engine_hours=hrs,
            interval_months=mo, standard_duration_hours=duree,
        ))
        op_par_code[code] = o

    # Plans de maintenance
    plans_par_code: dict[str, MaintenancePlan] = {}
    mfr_par_code = {m.code: m for m in store.list_manufacturers()}
    for plan_code, plan_name, mfr_code, op_codes in MAINTENANCE_PLANS:
        mfr = mfr_par_code.get(mfr_code)
        p = store.upsert_maintenance_plan(MaintenancePlan(
            plan_code=plan_code, plan_name=plan_name,
            manufacturer_id=mfr.manufacturer_id if mfr else None,
        ))
        plans_par_code[plan_code] = p
        for order, op_code in enumerate(op_codes, start=1):
            store.add_plan_operation(MaintenancePlanOperation(
                maintenance_plan_id=p.maintenance_plan_id,
                operation_id=op_par_code[op_code].operation_id,
                sequence_order=order,
            ))

    # Associe chaque variante aux profils d'usage et aux plans pertinents
    for variant in store.list_technical_variants():
        # Tous les profils fret standards disponibles sur chaque variante
        for code, requires_approval in [
            ("LOW_MILEAGE", False),
            ("STANDARD_MILEAGE", False),
            ("HIGH_MILEAGE", False),
            ("VERY_HIGH_MILEAGE", True),  # Exige dérogation
        ]:
            up = usage_par_code[code]
            store.set_variant_usage_profile(VariantUsageProfile(
                technical_variant_id=variant.technical_variant_id,
                usage_profile_id=up.usage_profile_id,
                is_supported=True,
                warning_threshold_km=up.annual_mileage_max_km,
                maximum_contractual_mileage_km=
                    (up.annual_mileage_max_km or 260_000) + 20_000,
                requires_specific_approval=requires_approval,
            ))

        # Tous les paliers mileage en support
        for band in store.list_mileage_bands():
            store.set_variant_mileage_band(VariantMileageBand(
                technical_variant_id=variant.technical_variant_id,
                mileage_band_id=band.mileage_band_id,
                is_supported=True,
            ))

        # Plan de maintenance par défaut selon la plateforme
        series = store.get_series(variant.series_id)
        if series is None:
            continue
        platform = store.get_product_platform(series.product_platform_id)
        if platform is None:
            continue
        if platform.platform_code.startswith("TRAXX"):
            plan_code = "TRAXX_MS_STANDARD"
        elif platform.platform_code.startswith("VECTRON"):
            plan_code = "VECTRON_STANDARD"
        elif platform.platform_code == "EURODUAL":
            plan_code = "EURODUAL_STANDARD"
        else:
            plan_code = "TRAXX_MS_STANDARD"

        plan = plans_par_code.get(plan_code)
        if plan is not None:
            store.set_variant_maintenance_plan(VariantMaintenancePlan(
                technical_variant_id=variant.technical_variant_id,
                maintenance_plan_id=plan.maintenance_plan_id,
                is_default=True,
            ))
