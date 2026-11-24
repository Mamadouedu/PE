"""Seed Lot 5 : flotte physique réelle Akiem.

Peuple une vingtaine de locomotives avec des numéros UIC / immatriculation
réalistes, des km cumulés plausibles, des historiques HM cohérents.

Le but n'est pas d'avoir la flotte Akiem exacte, mais un échantillon
représentatif permettant de valider la vue "Flotte réelle" et le lien
QuoteLine → FleetAsset.
"""

from __future__ import annotations

from datetime import date, timedelta
from random import Random

from .fleet import (
    AssetMaintenanceHistoryEntry,
    AssetMeterReading,
    FleetAsset,
    MaintenanceEventStatus,
    OperationalStatus,
    OwnershipStatus,
)
from .store import CatalogStore


# (asset_number, UIC registration, variant_code, manuf_year, operational_status)
LOCOMOTIVES_FLOTTE = [
    # TRAXX AC - série E185
    ("AK-00101", "91 80 6185 101-2 D-AKIEM", "E185-DA", 2008, OperationalStatus.LEASED),
    ("AK-00102", "91 80 6185 102-0 D-AKIEM", "E185-DACH", 2009, OperationalStatus.LEASED),
    ("AK-00103", "91 80 6185 103-8 D-AKIEM", "E185-DAHU", 2010, OperationalStatus.AVAILABLE),
    # TRAXX MS - série E186 (la star du doc)
    ("AK-00201", "91 80 6186 201-9 D-AKIEM", "E186-DABNL", 2011, OperationalStatus.LEASED),
    ("AK-00202", "91 80 6186 202-7 D-AKIEM", "E186-DABNL", 2012, OperationalStatus.LEASED),
    ("AK-00203", "91 80 6186 203-5 D-AKIEM", "E186-DABNL", 2012, OperationalStatus.IN_MAINTENANCE),
    ("AK-00204", "91 80 6186 204-3 D-AKIEM", "E186-DABF", 2013, OperationalStatus.LEASED),
    ("AK-00205", "91 80 6186 205-1 D-AKIEM", "E186-DBF", 2014, OperationalStatus.AVAILABLE),
    # TRAXX MS2e - E187
    ("AK-00301", "91 80 6187 301-5 D-AKIEM", "E187-DACHI", 2017, OperationalStatus.LEASED),
    # TRAXX MS3 - E188
    ("AK-00401", "91 80 6188 401-2 D-AKIEM", "E188-DACHI", 2021, OperationalStatus.LEASED),
    ("AK-00402", "91 80 6188 402-0 D-AKIEM", "E188-PLCZSK", 2022, OperationalStatus.LEASED),
    # VECTRON MS - 193
    ("AK-00501", "91 80 6193 501-8 D-AKIEM", "193-DACHI", 2015, OperationalStatus.LEASED),
    ("AK-00502", "91 80 6193 502-6 D-AKIEM", "193-DABNL", 2016, OperationalStatus.LEASED),
    ("AK-00503", "91 80 6193 503-4 D-AKIEM", "193-PLCZSK", 2019, OperationalStatus.AVAILABLE),
    # VECTRON AC - 191
    ("AK-00601", "91 80 6191 601-3 D-AKIEM", "191-DA", 2016, OperationalStatus.LEASED),
    # Eurodual 159 (dual-mode)
    ("AK-00701", "92 80 1159 701-0 D-AKIEM", "159-DABF", 2020, OperationalStatus.AVAILABLE),
    ("AK-00702", "92 80 1159 702-8 D-AKIEM", "159-DACH", 2021, OperationalStatus.STORED),
]


def seed_lot5(store: CatalogStore) -> dict:
    """Peuple les FleetAssets + relevés compteurs + historique HM.

    Retourne un dict {nb_assets, nb_readings, nb_history}."""

    rng = Random(42)  # Déterministe pour les tests

    # Index des codes
    variant_par_code = {v.variant_code: v for v in store.list_technical_variants()}
    country_par_iso = {c.iso_alpha2: c for c in store.list_countries()}
    ops_par_code = {o.operation_code: o for o in store.list_maintenance_operations()}
    ams = next((e for e in store.list_ecm_providers() if e.provider_code == "AMS"), None)

    nb_assets = 0
    nb_readings = 0
    nb_history = 0

    for asset_number, registration, variant_code, year, op_status in LOCOMOTIVES_FLOTTE:
        variant = variant_par_code.get(variant_code)
        if variant is None:
            continue  # Skip si la variante n'existe pas (ne devrait pas arriver avec seed Lot 1)

        age_years = 2026 - year
        # Km cumulés plausibles : ~130k à 160k par an selon utilisation
        annual = rng.randint(130_000, 170_000)
        current_km = age_years * annual

        # Commissioning entre le 15 et le 25 d'un mois aléatoire de l'année
        commissioning = date(year, rng.randint(1, 12), rng.randint(10, 25))

        # Dernières HM selon km : HM1 tous les 600k, HM2 tous les 1200k, HM3 tous les 1800k
        last_hm1 = commissioning + timedelta(days=int(min(600_000, current_km) / annual * 365.25)) if current_km >= 600_000 else None
        last_hm2 = commissioning + timedelta(days=int(min(1_200_000, current_km) / annual * 365.25)) if current_km >= 1_200_000 else None
        last_hm3 = commissioning + timedelta(days=int(min(1_800_000, current_km) / annual * 365.25)) if current_km >= 1_800_000 else None
        last_vgi = date.today() - timedelta(days=rng.randint(30, 300))  # VGI dans l'année

        # Pays courant : premier pays des homologations de la variante
        homos = store.list_homologations_for_variant(variant.technical_variant_id)
        country_id = None
        if homos:
            countries_of_homo = store.list_countries_for_homologation(homos[0].homologation_id)
            if countries_of_homo:
                country_id = countries_of_homo[0].country_id

        asset = FleetAsset(
            asset_number=asset_number,
            vehicle_registration_number=registration,
            technical_variant_id=variant.technical_variant_id,
            manufacturing_year=year,
            commissioning_date=commissioning,
            ownership_status=OwnershipStatus.OWNED,
            operational_status=op_status,
            current_country_id=country_id,
            current_mileage_km=current_km,
            current_engine_hours=float(rng.randint(500, 3000)) if variant_code.startswith("159") else 0.0,
            current_ecm_provider_id=ams.ecm_provider_id if ams else None,
            last_hm1_date=last_hm1,
            last_hm2_date=last_hm2,
            last_hm3_date=last_hm3,
            last_vgi_date=last_vgi,
        )
        store.upsert_fleet_asset(asset)
        nb_assets += 1

        # 3 relevés compteurs historiques
        for i in range(3):
            days_ago = (i + 1) * 90
            reading_date = date.today() - timedelta(days=days_ago)
            km_at_reading = current_km - (annual / 365.25 * days_ago)
            if km_at_reading < 0:
                continue
            store.add_meter_reading(AssetMeterReading(
                fleet_asset_id=asset.fleet_asset_id,
                reading_date=reading_date,
                mileage_km=round(km_at_reading, 0),
                engine_hours=float(rng.randint(100, 500)) if variant_code.startswith("159") else 0.0,
                source="telemetry",
                recorded_by="telemetry-system@akiem.com",
            ))
            nb_readings += 1

        # Historique HM
        for op_code, event_date in [
            ("HM1", last_hm1),
            ("HM2", last_hm2),
            ("HM3", last_hm3),
            ("VGI", last_vgi),
        ]:
            if event_date is None:
                continue
            op = ops_par_code.get(op_code)
            if op is None:
                continue
            store.add_maintenance_history(AssetMaintenanceHistoryEntry(
                fleet_asset_id=asset.fleet_asset_id,
                operation_id=op.operation_id,
                operation_code=op_code,
                status=MaintenanceEventStatus.COMPLETED,
                planned_date=event_date,
                started_at=event_date,
                completed_at=event_date,
                workshop_name="Akiem Oberursel" if rng.random() > 0.5 else "DB Fahrzeuginstandhaltung Cottbus",
                workshop_country_iso="DE",
                ecm_provider_id=ams.ecm_provider_id if ams else None,
                mileage_km_at_event=round(current_km * 0.85, 0),
                billed_amount=200_000 if op_code == "HM1" else 450_000 if op_code == "HM2" else 850_000 if op_code == "HM3" else 8_000,
            ))
            nb_history += 1

    return {"nb_assets": nb_assets, "nb_readings": nb_readings, "nb_history": nb_history}
