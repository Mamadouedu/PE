"""Moteur de prix v2 — chiffrage basé sur PriceBook versionné.

Prend une configuration d'offre (variante, pays, durée, âge, mileage,
heures moteur) et résout les tarifs applicables dans les PriceBookVersions
publiées au moment de la demande.

Applique la formule OM cible (section 11 du doc) :
    OM = MonthlyFixed
       + (AnnualMileage × PricePerKm / 12)
       + (AnnualEngineHours × PricePerEngineHour / 12)
       + EcmMonthly
       + LastMileMonthly

Coexiste avec le moteur actuel (`src/pricing_engine/engine.py`) qui reste
sur l'ancien modèle Serie. Les deux restent utilisables jusqu'à ce que
Lot 4 (configurateur refondu) bascule le frontend sur le moteur v2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from .pricing import calculer_om_mensuel
from .store import CatalogStore


@dataclass
class DemandeChiffrage:
    """Entrée du moteur v2."""

    technical_variant_code: str
    country_iso: str
    duration_months: int
    age_years: float
    annual_mileage_km: int
    annual_engine_hours: float = 0
    ecm_provider_code: str | None = None
    service_level_code: str | None = None
    options_monthly: float = 0
    at_date: date | None = None


@dataclass
class ResultatChiffrage:
    """Sortie du moteur v2 avec tout le détail explicable (M2-05)."""

    variant_code: str
    dl_mensuel: float | None
    hm_mensuel_provisionne: float
    om_mensuel: float
    total_mensuel: float
    detail_dl: dict
    detail_om: dict
    detail_hm: list[dict]
    warnings: list[str]
    versions_utilisees: dict[str, str]  # pricebook_code → version_number
    plancher_applique: float | None = None


class MoteurPrixV2:
    """Moteur de prix basé sur le nouveau catalog + PriceBook."""

    def __init__(self, store: CatalogStore) -> None:
        self._store = store

    def chiffrer(self, demande: DemandeChiffrage) -> ResultatChiffrage:
        warnings: list[str] = []

        # 1. Résoudre la variante
        variant = self._store.get_variant_by_code(demande.technical_variant_code)
        if variant is None:
            raise ValueError(f"Variante technique {demande.technical_variant_code} inconnue")

        # 2. Résoudre les paliers et dimensions
        country = self._store.get_country_by_iso(demande.country_iso)
        country_group = self._store.get_country_group_for_iso(demande.country_iso)
        if country_group is None:
            raise ValueError(f"Aucun groupe pays pour {demande.country_iso}")

        lease_band = self._store.get_lease_band_for_duration(demande.duration_months)
        if lease_band is None:
            raise ValueError(f"Aucun palier durée pour {demande.duration_months} mois")

        age_band = self._store.get_asset_age_band_for_age(demande.age_years)
        if age_band is None:
            raise ValueError(f"Aucun palier âge pour {demande.age_years} ans")

        mileage_band = self._store.get_mileage_band_for_annual_km(demande.annual_mileage_km)
        if mileage_band is None:
            raise ValueError(f"Aucun palier mileage pour {demande.annual_mileage_km} km/an")

        # 3. Versions publiées
        dl_version = self._store.get_current_published_version("DL_STANDARD", demande.at_date)
        hm_version = self._store.get_current_published_version("HM_STANDARD", demande.at_date)
        om_version = self._store.get_current_published_version("OM_STANDARD", demande.at_date)
        if dl_version is None:
            raise ValueError("Pas de version publiée de DL_STANDARD")
        if om_version is None:
            raise ValueError("Pas de version publiée de OM_STANDARD")

        # 4. DL
        dl_rate = self._store.find_dry_lease_rate(
            version_id=dl_version.price_book_version_id,
            variant_id=variant.technical_variant_id,
            country_group_id=country_group.country_group_id,
            lease_band_id=lease_band.lease_band_id,
            asset_age_band_id=age_band.asset_age_band_id,
        )
        if dl_rate is None:
            raise ValueError(
                f"Aucun tarif DL pour {variant.variant_code} × {country_group.group_code} × "
                f"{lease_band.band_code} × {age_band.band_code}"
            )
        dl_mensuel = dl_rate.total_mensuel()
        detail_dl = {
            "monthly_base_rent": dl_rate.monthly_base_rent,
            "insurance_amount": dl_rate.insurance_amount,
            "risk_provision_amount": dl_rate.risk_provision_amount,
            "specific_commitment_rate": dl_rate.specific_commitment_rate,
            "total_monthly": dl_mensuel,
            "country_group": country_group.group_code,
            "lease_band": lease_band.band_code,
            "asset_age_band": age_band.band_code,
        }

        # 5. HM : provision mensuelle = somme des provisions de chaque opération
        hm_rates = []
        detail_hm = []
        hm_mensuel = 0.0
        if hm_version is not None:
            hm_rates = self._store.find_heavy_maintenance_rates(
                version_id=hm_version.price_book_version_id,
                variant_id=variant.technical_variant_id,
            )
            for hr in hm_rates:
                provision = hr.monthly_provision_amount or 0
                hm_mensuel += provision
                op = self._store._maintenance_operations.get(hr.operation_id)  # type: ignore[attr-defined]
                detail_hm.append({
                    "operation_code": op.operation_code if op else str(hr.operation_id),
                    "selling_price_per_operation": hr.selling_price,
                    "monthly_provision": provision,
                    "calculation_method": hr.calculation_method.value,
                })

        # 6. OM : résolution avec fallback + formule canonique
        ecm_id = None
        if demande.ecm_provider_code:
            for e in self._store.list_ecm_providers():
                if e.provider_code.upper() == demande.ecm_provider_code.upper():
                    ecm_id = e.ecm_provider_id
                    break
        service_id = None
        if demande.service_level_code:
            for s in self._store.list_service_levels():
                if s.service_level_code.value.upper() == demande.service_level_code.upper():
                    service_id = s.service_level_id
                    break

        om_rate = self._store.find_operating_maintenance_rate(
            version_id=om_version.price_book_version_id,
            variant_id=variant.technical_variant_id,
            mileage_band_id=mileage_band.mileage_band_id,
            country_id=country.country_id if country else None,
            ecm_provider_id=ecm_id,
            service_level_id=service_id,
        )
        if om_rate is None:
            raise ValueError(
                f"Aucun tarif OM pour {variant.variant_code} × {mileage_band.band_code}"
            )
        detail_om = calculer_om_mensuel(
            om_rate,
            annual_mileage_km=demande.annual_mileage_km,
            annual_engine_hours=demande.annual_engine_hours,
            options_monthly=demande.options_monthly,
        )
        detail_om["mileage_band"] = mileage_band.band_code
        om_mensuel = detail_om["total_monthly"]

        # 7. Avertissements métier
        if demande.annual_mileage_km > 220_000:
            warnings.append("Très haut mileage (>220k km/an) : dérogation requise (section 5 doc)")
        if demande.duration_months > 120:
            warnings.append("Durée très longue (>10 ans) : approbation Direction recommandée")

        total_mensuel = dl_mensuel + hm_mensuel + om_mensuel

        # 8. Plancher éventuel (contrôle M2-04)
        plancher_applique = None
        if dl_rate.minimum_price is not None and dl_mensuel < dl_rate.minimum_price:
            plancher_applique = dl_rate.minimum_price - dl_mensuel

        return ResultatChiffrage(
            variant_code=variant.variant_code,
            dl_mensuel=dl_mensuel,
            hm_mensuel_provisionne=hm_mensuel,
            om_mensuel=om_mensuel,
            total_mensuel=total_mensuel,
            detail_dl=detail_dl,
            detail_om=detail_om,
            detail_hm=detail_hm,
            warnings=warnings,
            versions_utilisees={
                "DL_STANDARD": f"{dl_version.year}-v{dl_version.version_number}",
                "HM_STANDARD": f"{hm_version.year}-v{hm_version.version_number}" if hm_version else "n/a",
                "OM_STANDARD": f"{om_version.year}-v{om_version.version_number}",
            },
            plancher_applique=plancher_applique,
        )
