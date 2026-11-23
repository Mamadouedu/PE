"""Seed Lot 3 : PriceBooks, versions, et tarifs réalistes.

Publie une version 2026-v1 pour chaque type de PriceBook (DL, HM, OM), peuplée
avec des tarifs couvrant les 15 variantes du Lot 1 × les dimensions pertinentes.

Ordres de grandeur (pour la vraisemblance) :
- Loyer DL VECTRON/TRAXX MS : 18 000 - 24 000 €/mois selon âge et durée
- Prix HM-1 (révision 600k) : 180 000 - 220 000 € par intervention
- Prix HM-2 (révision 1.2M) : 400 000 - 480 000 €
- OM mensuel fixe : 1 500 - 3 500 €
- OM par km : 0.08 - 0.15 €
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from .maintenance import MaintenancePlan
from .pricing import (
    AssetAgeBand,
    BillingUnit,
    CalculationMethodHM,
    CommercialOption,
    CountryGroup,
    DryLeaseRate,
    HeavyMaintenanceRate,
    LeaseBand,
    OperatingMaintenanceRate,
    PriceBook,
    PriceBookStatus,
    PriceBookVersion,
    PriceType,
)
from .store import CatalogStore


# Paliers durée de contrat
LEASE_BANDS = [
    ("SHORT", "Court terme (0-11 mois)", 0, 11),
    ("MEDIUM", "Moyen terme (12-36 mois)", 12, 36),
    ("LONG", "Long terme (37-60 mois)", 37, 60),
    ("VERY_LONG", "Très long terme (61+ mois)", 61, None),
]

# Paliers âge
ASSET_AGE_BANDS = [
    ("NEW", "Neuve (0-5 ans)", 0, 5),
    ("YOUNG", "Récente (5-10 ans)", 5, 10),
    ("MATURE", "Mature (10-15 ans)", 10, 15),
    ("OLD", "Ancienne (15+ ans)", 15, None),
]

# Groupes pays
COUNTRY_GROUPS = [
    ("CORE_DACH", "Core DACH", ["DE", "AT", "CH"], "Marché principal, tarifs premium"),
    ("BENELUX", "Benelux", ["NL", "BE", "LU"], "Zone Rhin, tarifs standards"),
    ("FRET_EST", "Fret Est européen", ["PL", "CZ", "SK", "HU", "RO"], "Tarifs compétitifs"),
    ("FRET_SUD", "Fret Sud", ["FR", "IT", "ES", "PT"], "France et Méditerranée"),
    ("SCANDI", "Scandinavie", ["DK", "SE", "NO", "FI"], "Nord de l'Europe"),
    ("UK_ONLY", "Royaume-Uni", ["UK"], "Post-Brexit, tarifs spécifiques"),
]

# Options commerciales
COMMERCIAL_OPTIONS = [
    ("ECM_SERVICE", "Service ECM complet", "service", BillingUnit.MONTHLY),
    ("LAST_MILE", "Last-mile (zones non électrifiées)", "service", BillingUnit.MONTHLY),
    ("HOTLINE_24_7", "Hotline 24/7", "service", BillingUnit.MONTHLY),
    ("WHEEL_REPROFILING", "Reprofilage de roues inclus", "maintenance", BillingUnit.MONTHLY),
    ("INSURANCE_COVER", "Assurance étendue", "insurance", BillingUnit.MONTHLY),
    ("SPECIFIC_COMMITMENT", "Engagement spécifique (kilométrage garanti)", "service", BillingUnit.MONTHLY),
    ("WORKSHOP_PACKAGE", "Pack atelier (temps réservé)", "maintenance", BillingUnit.YEARLY),
]

# PriceBooks principaux
PRICE_BOOKS = [
    ("DL_STANDARD", "Dry Lease standard", PriceType.DRY_LEASE),
    ("HM_STANDARD", "Heavy Maintenance standard", PriceType.HEAVY_MAINTENANCE),
    ("OM_STANDARD", "Operating Maintenance standard", PriceType.OPERATING_MAINTENANCE),
]

# Loyers DL de base par plateforme (€/mois), avant modulation âge × durée
LOYER_DL_PLATFORM = {
    "TRAXX_AC": 20_000,
    "TRAXX_MS": 22_000,
    "TRAXX_DC": 20_000,
    "TRAXX_DE": 18_500,
    "VECTRON_AC": 21_000,
    "VECTRON_MS": 23_000,
    "VECTRON_DC": 21_000,
    "VECTRON_DE": 19_000,
    "EURODUAL": 24_500,
    "SMARTRON": 17_500,
}

# Prix HM par opération (€ par intervention)
PRIX_HM_PAR_OPERATION = {
    "HM1": 200_000,
    "HM2": 450_000,
    "HM3": 850_000,
    "BOGIE_SWAP": 380_000,
    "VGI": 8_000,
    "WHEEL_REPROFILING": 35_000,
    "DIESEL_OVERHAUL": 95_000,
}

# Paramètres OM par palier mileage (fixé mensuel, prix par km)
# Section 11 du doc — valeurs cohérentes avec les paliers Lot 2
OM_PARAMS_PAR_PALIER = {
    "OM_000_080": {"monthly_fixed": 1_500, "per_km": 0.085},
    "OM_080_120": {"monthly_fixed": 1_800, "per_km": 0.080},
    "OM_120_160": {"monthly_fixed": 2_100, "per_km": 0.075},
    "OM_160_200": {"monthly_fixed": 2_400, "per_km": 0.072},
    "OM_200_240": {"monthly_fixed": 2_800, "per_km": 0.070},
    "OM_240_PLUS": {"monthly_fixed": 3_400, "per_km": 0.068},
}

# Multiplicateurs pays (modulation DL)
MULTIPLICATEUR_PAYS = {
    "CORE_DACH": 1.10,
    "BENELUX": 1.05,
    "FRET_EST": 0.92,
    "FRET_SUD": 1.00,
    "SCANDI": 1.08,
    "UK_ONLY": 1.15,
}

# Multiplicateurs durée (modulation DL)
MULTIPLICATEUR_DUREE = {
    "SHORT": 1.15,
    "MEDIUM": 1.00,
    "LONG": 0.95,
    "VERY_LONG": 0.90,
}

# Multiplicateurs âge (modulation DL — plus vieux = moins cher)
MULTIPLICATEUR_AGE = {
    "NEW": 1.10,
    "YOUNG": 1.00,
    "MATURE": 0.90,
    "OLD": 0.78,
}


def seed_lot3(store: CatalogStore) -> dict:
    """Peuple le store avec les tarifs Lot 3. Retourne les versions
    publiées pour chaque PriceBook."""

    # Dimensions
    lease_bands = {}
    for code, name, dmin, dmax in LEASE_BANDS:
        lease_bands[code] = store.upsert_lease_band(LeaseBand(
            band_code=code, band_name=name,
            min_duration_months=dmin, max_duration_months=dmax,
        ))

    age_bands = {}
    for code, name, amin, amax in ASSET_AGE_BANDS:
        age_bands[code] = store.upsert_asset_age_band(AssetAgeBand(
            band_code=code, band_name=name,
            min_age_years=amin, max_age_years=amax,
        ))

    country_groups = {}
    for code, name, iso_list, desc in COUNTRY_GROUPS:
        country_groups[code] = store.upsert_country_group(CountryGroup(
            group_code=code, group_name=name,
            country_iso_codes=iso_list, description=desc,
        ))

    for code, name, type_, unit in COMMERCIAL_OPTIONS:
        store.upsert_commercial_option(CommercialOption(
            option_code=code, option_name=name,
            option_type=type_, default_billing_unit=unit,
        ))

    # PriceBooks + versions
    price_books = {}
    for code, name, type_ in PRICE_BOOKS:
        price_books[code] = store.upsert_price_book(PriceBook(
            price_book_code=code, price_book_name=name, price_type=type_,
        ))

    versions = {}
    for code in ["DL_STANDARD", "HM_STANDARD", "OM_STANDARD"]:
        v = store.upsert_price_book_version(PriceBookVersion(
            price_book_id=price_books[code].price_book_id,
            year=2026, version_number=1,
            status=PriceBookStatus.PUBLISHED,
            valid_from=date(2026, 1, 1),
            approved_by="head@akiem.com",
            approved_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
        ))
        versions[code] = v

    # Index helpers
    variants = store.list_technical_variants()
    mileage_bands = {b.band_code: b for b in store.list_mileage_bands()}
    operations = {o.operation_code: o for o in store.list_maintenance_operations()}
    ecm_providers = {e.provider_code: e for e in store.list_ecm_providers()}
    service_levels = {s.service_level_code.value: s for s in store.list_service_levels()}

    # ---------------- DL rates ----------------
    nb_dl = 0
    for variant in variants:
        series = store.get_series(variant.series_id)
        platform = store.get_product_platform(series.product_platform_id) if series else None
        if platform is None:
            continue
        loyer_base = LOYER_DL_PLATFORM.get(platform.platform_code, 20_000)
        for cg_code, cg in country_groups.items():
            for lb_code, lb in lease_bands.items():
                for ab_code, ab in age_bands.items():
                    multiplicateur = (
                        MULTIPLICATEUR_PAYS.get(cg_code, 1.0)
                        * MULTIPLICATEUR_DUREE.get(lb_code, 1.0)
                        * MULTIPLICATEUR_AGE.get(ab_code, 1.0)
                    )
                    monthly_rent = round(loyer_base * multiplicateur, 2)
                    insurance = round(monthly_rent * 0.03, 2)
                    risk = round(monthly_rent * 0.015, 2)
                    store.add_dry_lease_rate(DryLeaseRate(
                        price_book_version_id=versions["DL_STANDARD"].price_book_version_id,
                        technical_variant_id=variant.technical_variant_id,
                        country_group_id=cg.country_group_id,
                        lease_band_id=lb.lease_band_id,
                        asset_age_band_id=ab.asset_age_band_id,
                        monthly_base_rent=monthly_rent,
                        insurance_amount=insurance,
                        risk_provision_amount=risk,
                        specific_commitment_rate=0,
                        minimum_price=round(monthly_rent * 0.75, 2),
                        valid_from=date(2026, 1, 1),
                    ))
                    nb_dl += 1

    # ---------------- HM rates ----------------
    nb_hm = 0
    for variant in variants:
        series = store.get_series(variant.series_id)
        platform = store.get_product_platform(series.product_platform_id) if series else None
        is_dual = platform.platform_code == "EURODUAL" if platform else False
        for op_code, prix_base in PRIX_HM_PAR_OPERATION.items():
            # EURODUAL inclut DIESEL_OVERHAUL, les autres non
            if op_code == "DIESEL_OVERHAUL" and not is_dual:
                continue
            op = operations.get(op_code)
            if op is None:
                continue
            # Petit ajustement par plateforme
            multiplier = 1.0
            if platform and platform.platform_code.startswith("VECTRON"):
                multiplier = 1.05
            elif platform and platform.platform_code == "EURODUAL":
                multiplier = 1.15
            selling = round(prix_base * multiplier, 2)
            cost = round(selling * 0.78, 2)
            # Provision mensuelle = selling / intervalle en années
            provision = None
            if op.interval_mileage_km:
                # Supposons 150k km/an moyen → intervalle en mois ~= interval_km / 12_500
                annees = op.interval_mileage_km / (150_000 or 1)
                provision = round(selling / (annees * 12), 2) if annees > 0 else None
            store.add_heavy_maintenance_rate(HeavyMaintenanceRate(
                price_book_version_id=versions["HM_STANDARD"].price_book_version_id,
                technical_variant_id=variant.technical_variant_id,
                operation_id=op.operation_id,
                calculation_method=CalculationMethodHM.MONTHLY_PROVISION,
                cost_amount=cost,
                selling_price=selling,
                monthly_provision_amount=provision,
                billing_unit=BillingUnit.PER_OPERATION,
                valid_from=date(2026, 1, 1),
            ))
            nb_hm += 1

    # ---------------- OM rates ----------------
    nb_om = 0
    for variant in variants:
        for band_code, band in mileage_bands.items():
            params = OM_PARAMS_PAR_PALIER.get(band_code, {"monthly_fixed": 2000, "per_km": 0.08})
            # Un tarif OM générique (tous pays, ECM par défaut, SL STANDARD)
            store.add_operating_maintenance_rate(OperatingMaintenanceRate(
                price_book_version_id=versions["OM_STANDARD"].price_book_version_id,
                technical_variant_id=variant.technical_variant_id,
                mileage_band_id=band.mileage_band_id,
                ecm_provider_id=ecm_providers.get("AMS").ecm_provider_id if ecm_providers.get("AMS") else None,
                service_level_id=service_levels.get("STANDARD").service_level_id if service_levels.get("STANDARD") else None,
                monthly_fixed_amount=params["monthly_fixed"],
                price_per_kilometer=params["per_km"],
                price_per_engine_hour=0.0,
                ecm_monthly_amount=250,
                last_mile_monthly_amount=0,
                minimum_monthly_amount=params["monthly_fixed"] * 1.1,
                valid_from=date(2026, 1, 1),
            ))
            nb_om += 1

    return {
        "DL_STANDARD": versions["DL_STANDARD"],
        "HM_STANDARD": versions["HM_STANDARD"],
        "OM_STANDARD": versions["OM_STANDARD"],
        "counts": {"dl_rates": nb_dl, "hm_rates": nb_hm, "om_rates": nb_om},
    }
