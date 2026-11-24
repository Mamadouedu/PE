"""SqlAlchemyCatalogStore — persistance SQL du catalog.

Implémente le même protocol `CatalogStore` que `InMemoryCatalogStore`
mais écrit dans PostgreSQL (ou SQLite en dev/test). Chaque opération ouvre
une session courte, commit immédiatement — simple et correct pour le
volume attendu, à revoir si les reporting lourds l'exigent.

Les méthodes miroir l'API in-memory : upsert_*, get_*, list_*, les M2M et
les helpers de résolution (`get_mileage_band_for_annual_km`, etc.).

Mapping Pydantic ↔ Row : deux helpers par type (`_to_row`, `_from_row`).
Pas d'ORM-level cascade ; les deletes cascade sont déclarés en DB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .db import (
    AssetAgeBandRow,
    AssetMaintenanceHistoryRow,
    AssetMeterReadingRow,
    CommercialOptionRow,
    CountryGroupRow,
    CountryRow,
    DryLeaseRateRow,
    EcmProviderRow,
    EngineHoursBandRow,
    FleetAssetRow,
    HeavyMaintenanceRateRow,
    HomologationCountryRow,
    HomologationRow,
    LeaseBandRow,
    LocomotiveSeriesRow,
    MaintenanceOperationRow,
    MaintenancePlanOperationRow,
    MaintenancePlanRow,
    ManufacturerRow,
    MileageBandRow,
    OperatingMaintenanceRateRow,
    PriceBookRow,
    PriceBookVersionRow,
    ProductFamilyRow,
    ProductPlatformRow,
    ServiceLevelRow,
    TechnicalVariantRow,
    UsageProfileRow,
    VariantHomologationRow,
    VariantMaintenancePlanRow,
    VariantMileageBandRow,
    VariantUsageProfileRow,
)
from .entities import (
    Country,
    Homologation,
    HomologationCountry,
    LocomotiveSeries,
    Manufacturer,
    ManufacturerStatut,
    ProductFamily,
    ProductPlatform,
    StatutHomologation,
    TechnicalVariant,
    TractionMode,
    VariantHomologation,
)
from .fleet import (
    AssetMaintenanceHistoryEntry,
    AssetMeterReading,
    FleetAsset,
    FleetAssetSummary,
    MaintenanceEventStatus,
    OperationalStatus,
    OwnershipStatus,
)
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
from .usage import (
    CalculationMethod,
    EngineHoursBand,
    MileageBand,
    UsageProfile,
    UtilisationType,
    VariantMileageBand,
    VariantUsageProfile,
)


def _s(u: UUID | str) -> str:
    """UUID → string pour les colonnes String(36)."""
    return str(u) if isinstance(u, UUID) else u


class SqlAlchemyCatalogStore:
    """Persistance SQL du catalog. Instancié avec une `sessionmaker` liée
    à une Engine SQLAlchemy (SQLite en test, PostgreSQL en prod)."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # ---------------- Manufacturers ----------------

    def upsert_manufacturer(self, m: Manufacturer) -> Manufacturer:
        with self._sf() as session:
            existing = session.execute(
                select(ManufacturerRow).where(ManufacturerRow.code == m.code.upper())
            ).scalar_one_or_none()
            if existing is not None:
                existing.name = m.name
                existing.country_of_origin_iso = m.country_of_origin_iso
                existing.parent_company = m.parent_company
                existing.statut = m.statut.value
                existing.is_active = m.is_active
                session.commit()
                return self._row_to_manufacturer(existing)
            row = ManufacturerRow(
                manufacturer_id=_s(m.manufacturer_id),
                code=m.code.upper(),
                name=m.name,
                country_of_origin_iso=m.country_of_origin_iso,
                parent_company=m.parent_company,
                statut=m.statut.value,
                is_active=m.is_active,
            )
            session.add(row)
            session.commit()
            return m

    def get_manufacturer(self, mid: UUID) -> Manufacturer | None:
        with self._sf() as session:
            row = session.get(ManufacturerRow, _s(mid))
            return self._row_to_manufacturer(row) if row else None

    def get_manufacturer_by_code(self, code: str) -> Manufacturer | None:
        with self._sf() as session:
            row = session.execute(
                select(ManufacturerRow).where(ManufacturerRow.code == code.upper())
            ).scalar_one_or_none()
            return self._row_to_manufacturer(row) if row else None

    def list_manufacturers(self) -> list[Manufacturer]:
        with self._sf() as session:
            rows = session.execute(select(ManufacturerRow).order_by(ManufacturerRow.name)).scalars().all()
            return [self._row_to_manufacturer(r) for r in rows]

    @staticmethod
    def _row_to_manufacturer(r: ManufacturerRow) -> Manufacturer:
        return Manufacturer(
            manufacturer_id=UUID(r.manufacturer_id),
            code=r.code,
            name=r.name,
            country_of_origin_iso=r.country_of_origin_iso,
            parent_company=r.parent_company,
            statut=ManufacturerStatut(r.statut),
            is_active=r.is_active,
        )

    # ---------------- Countries ----------------

    def upsert_country(self, c: Country) -> Country:
        iso = c.iso_alpha2.upper()
        with self._sf() as session:
            existing = session.execute(
                select(CountryRow).where(CountryRow.iso_alpha2 == iso)
            ).scalar_one_or_none()
            if existing is not None:
                existing.name_fr = c.name_fr
                existing.name_en = c.name_en
                existing.default_network_code = c.default_network_code
                existing.is_eu_member = c.is_eu_member
                existing.is_active = c.is_active
                session.commit()
                return self._row_to_country(existing)
            row = CountryRow(
                country_id=_s(c.country_id),
                iso_alpha2=iso,
                name_fr=c.name_fr,
                name_en=c.name_en,
                default_network_code=c.default_network_code,
                is_eu_member=c.is_eu_member,
                is_active=c.is_active,
            )
            session.add(row)
            session.commit()
            return c.model_copy(update={"iso_alpha2": iso})

    def get_country(self, cid: UUID) -> Country | None:
        with self._sf() as session:
            row = session.get(CountryRow, _s(cid))
            return self._row_to_country(row) if row else None

    def get_country_by_iso(self, iso: str) -> Country | None:
        with self._sf() as session:
            row = session.execute(
                select(CountryRow).where(CountryRow.iso_alpha2 == iso.upper())
            ).scalar_one_or_none()
            return self._row_to_country(row) if row else None

    def list_countries(self) -> list[Country]:
        with self._sf() as session:
            rows = session.execute(select(CountryRow).order_by(CountryRow.iso_alpha2)).scalars().all()
            return [self._row_to_country(r) for r in rows]

    @staticmethod
    def _row_to_country(r: CountryRow) -> Country:
        return Country(
            country_id=UUID(r.country_id),
            iso_alpha2=r.iso_alpha2,
            name_fr=r.name_fr,
            name_en=r.name_en,
            default_network_code=r.default_network_code,
            is_eu_member=r.is_eu_member,
            is_active=r.is_active,
        )

    # ---------------- Product Families ----------------

    def upsert_product_family(self, f: ProductFamily) -> ProductFamily:
        with self._sf() as session:
            existing = session.execute(
                select(ProductFamilyRow).where(ProductFamilyRow.family_code == f.family_code.upper())
            ).scalar_one_or_none()
            if existing is not None:
                existing.family_name = f.family_name
                existing.description = f.description
                existing.is_active = f.is_active
                session.commit()
                return self._row_to_family(existing)
            row = ProductFamilyRow(
                product_family_id=_s(f.product_family_id),
                family_code=f.family_code.upper(),
                family_name=f.family_name,
                description=f.description,
                is_active=f.is_active,
            )
            session.add(row)
            session.commit()
            return f

    def get_product_family(self, fid: UUID) -> ProductFamily | None:
        with self._sf() as session:
            row = session.get(ProductFamilyRow, _s(fid))
            return self._row_to_family(row) if row else None

    def list_product_families(self) -> list[ProductFamily]:
        with self._sf() as session:
            rows = session.execute(select(ProductFamilyRow).order_by(ProductFamilyRow.family_name)).scalars().all()
            return [self._row_to_family(r) for r in rows]

    @staticmethod
    def _row_to_family(r: ProductFamilyRow) -> ProductFamily:
        return ProductFamily(
            product_family_id=UUID(r.product_family_id),
            family_code=r.family_code,
            family_name=r.family_name,
            description=r.description,
            is_active=r.is_active,
        )

    # ---------------- Product Platforms ----------------

    def upsert_product_platform(self, p: ProductPlatform) -> ProductPlatform:
        with self._sf() as session:
            # Vérif FK côté application pour messages clairs
            if session.get(ProductFamilyRow, _s(p.product_family_id)) is None:
                raise ValueError(f"ProductFamily {p.product_family_id} inconnue")
            if session.get(ManufacturerRow, _s(p.manufacturer_id)) is None:
                raise ValueError(f"Manufacturer {p.manufacturer_id} inconnu")
            existing = session.execute(
                select(ProductPlatformRow).where(ProductPlatformRow.platform_code == p.platform_code.upper())
            ).scalar_one_or_none()
            if existing is not None:
                existing.product_family_id = _s(p.product_family_id)
                existing.platform_name = p.platform_name
                existing.manufacturer_id = _s(p.manufacturer_id)
                existing.traction_mode = p.traction_mode.value
                existing.description = p.description
                existing.is_active = p.is_active
                session.commit()
                return self._row_to_platform(existing)
            row = ProductPlatformRow(
                product_platform_id=_s(p.product_platform_id),
                product_family_id=_s(p.product_family_id),
                platform_code=p.platform_code.upper(),
                platform_name=p.platform_name,
                manufacturer_id=_s(p.manufacturer_id),
                traction_mode=p.traction_mode.value,
                description=p.description,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
                is_active=p.is_active,
            )
            session.add(row)
            session.commit()
            return p

    def get_product_platform(self, pid: UUID) -> ProductPlatform | None:
        with self._sf() as session:
            row = session.get(ProductPlatformRow, _s(pid))
            return self._row_to_platform(row) if row else None

    def list_product_platforms(self, *, family_id: UUID | None = None) -> list[ProductPlatform]:
        with self._sf() as session:
            stmt = select(ProductPlatformRow)
            if family_id is not None:
                stmt = stmt.where(ProductPlatformRow.product_family_id == _s(family_id))
            rows = session.execute(stmt.order_by(ProductPlatformRow.platform_code)).scalars().all()
            return [self._row_to_platform(r) for r in rows]

    @staticmethod
    def _row_to_platform(r: ProductPlatformRow) -> ProductPlatform:
        return ProductPlatform(
            product_platform_id=UUID(r.product_platform_id),
            product_family_id=UUID(r.product_family_id),
            platform_code=r.platform_code,
            platform_name=r.platform_name,
            manufacturer_id=UUID(r.manufacturer_id),
            traction_mode=TractionMode(r.traction_mode),
            description=r.description,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
            is_active=r.is_active,
        )

    # ---------------- Series ----------------

    def upsert_series(self, s: LocomotiveSeries) -> LocomotiveSeries:
        with self._sf() as session:
            if session.get(ProductPlatformRow, _s(s.product_platform_id)) is None:
                raise ValueError(f"ProductPlatform {s.product_platform_id} inconnue")
            existing = session.execute(
                select(LocomotiveSeriesRow).where(LocomotiveSeriesRow.series_code == s.series_code.upper())
            ).scalar_one_or_none()
            if existing is not None:
                for k, v in {
                    "product_platform_id": _s(s.product_platform_id),
                    "series_name": s.series_name,
                    "nominal_power_kw": s.nominal_power_kw,
                    "maximum_speed_kmh": s.maximum_speed_kmh,
                    "starting_tractive_effort_kn": s.starting_tractive_effort_kn,
                    "traction_mode": s.traction_mode.value if s.traction_mode else None,
                    "production_start_year": s.production_start_year,
                    "production_end_year": s.production_end_year,
                    "is_active": s.is_active,
                }.items():
                    setattr(existing, k, v)
                session.commit()
                return self._row_to_series(existing)
            row = LocomotiveSeriesRow(
                series_id=_s(s.series_id),
                product_platform_id=_s(s.product_platform_id),
                series_code=s.series_code.upper(),
                series_name=s.series_name,
                nominal_power_kw=s.nominal_power_kw,
                maximum_speed_kmh=s.maximum_speed_kmh,
                starting_tractive_effort_kn=s.starting_tractive_effort_kn,
                traction_mode=s.traction_mode.value if s.traction_mode else None,
                production_start_year=s.production_start_year,
                production_end_year=s.production_end_year,
                is_active=s.is_active,
            )
            session.add(row)
            session.commit()
            return s

    def get_series(self, sid: UUID) -> LocomotiveSeries | None:
        with self._sf() as session:
            row = session.get(LocomotiveSeriesRow, _s(sid))
            return self._row_to_series(row) if row else None

    def get_series_by_code(self, code: str) -> LocomotiveSeries | None:
        with self._sf() as session:
            row = session.execute(
                select(LocomotiveSeriesRow).where(LocomotiveSeriesRow.series_code == code.upper())
            ).scalar_one_or_none()
            return self._row_to_series(row) if row else None

    def list_series(self, *, platform_id: UUID | None = None) -> list[LocomotiveSeries]:
        with self._sf() as session:
            stmt = select(LocomotiveSeriesRow)
            if platform_id is not None:
                stmt = stmt.where(LocomotiveSeriesRow.product_platform_id == _s(platform_id))
            rows = session.execute(stmt.order_by(LocomotiveSeriesRow.series_code)).scalars().all()
            return [self._row_to_series(r) for r in rows]

    @staticmethod
    def _row_to_series(r: LocomotiveSeriesRow) -> LocomotiveSeries:
        return LocomotiveSeries(
            series_id=UUID(r.series_id),
            product_platform_id=UUID(r.product_platform_id),
            series_code=r.series_code,
            series_name=r.series_name,
            nominal_power_kw=r.nominal_power_kw,
            maximum_speed_kmh=r.maximum_speed_kmh,
            starting_tractive_effort_kn=r.starting_tractive_effort_kn,
            traction_mode=TractionMode(r.traction_mode) if r.traction_mode else None,
            production_start_year=r.production_start_year,
            production_end_year=r.production_end_year,
            is_active=r.is_active,
        )

    # ---------------- Technical Variants ----------------

    def upsert_technical_variant(self, v: TechnicalVariant) -> TechnicalVariant:
        with self._sf() as session:
            if session.get(LocomotiveSeriesRow, _s(v.series_id)) is None:
                raise ValueError(f"Series {v.series_id} inconnue")
            existing = session.execute(
                select(TechnicalVariantRow).where(TechnicalVariantRow.variant_code == v.variant_code.upper())
            ).scalar_one_or_none()
            attrs = {
                "series_id": _s(v.series_id),
                "variant_name": v.variant_name,
                "manufacturer_model_name": v.manufacturer_model_name,
                "technical_configuration_code": v.technical_configuration_code,
                "traction_mode": v.traction_mode.value if v.traction_mode else None,
                "nominal_power_kw": v.nominal_power_kw,
                "maximum_speed_kmh": v.maximum_speed_kmh,
                "starting_tractive_effort_kn": v.starting_tractive_effort_kn,
                "manufacturing_year_from": v.manufacturing_year_from,
                "manufacturing_year_to": v.manufacturing_year_to,
                "default_ecm_provider_id": _s(v.default_ecm_provider_id) if v.default_ecm_provider_id else None,
                "is_active": v.is_active,
            }
            if existing is not None:
                for k, val in attrs.items():
                    setattr(existing, k, val)
                session.commit()
                return self._row_to_variant(existing)
            row = TechnicalVariantRow(
                technical_variant_id=_s(v.technical_variant_id),
                variant_code=v.variant_code.upper(),
                **attrs,
            )
            session.add(row)
            session.commit()
            return v

    def get_technical_variant(self, vid: UUID) -> TechnicalVariant | None:
        with self._sf() as session:
            row = session.get(TechnicalVariantRow, _s(vid))
            return self._row_to_variant(row) if row else None

    def get_variant_by_code(self, code: str) -> TechnicalVariant | None:
        with self._sf() as session:
            row = session.execute(
                select(TechnicalVariantRow).where(TechnicalVariantRow.variant_code == code.upper())
            ).scalar_one_or_none()
            return self._row_to_variant(row) if row else None

    def list_technical_variants(self, *, series_id: UUID | None = None) -> list[TechnicalVariant]:
        with self._sf() as session:
            stmt = select(TechnicalVariantRow)
            if series_id is not None:
                stmt = stmt.where(TechnicalVariantRow.series_id == _s(series_id))
            rows = session.execute(stmt.order_by(TechnicalVariantRow.variant_code)).scalars().all()
            return [self._row_to_variant(r) for r in rows]

    @staticmethod
    def _row_to_variant(r: TechnicalVariantRow) -> TechnicalVariant:
        return TechnicalVariant(
            technical_variant_id=UUID(r.technical_variant_id),
            series_id=UUID(r.series_id),
            variant_code=r.variant_code,
            variant_name=r.variant_name,
            manufacturer_model_name=r.manufacturer_model_name,
            technical_configuration_code=r.technical_configuration_code,
            traction_mode=TractionMode(r.traction_mode) if r.traction_mode else None,
            nominal_power_kw=r.nominal_power_kw,
            maximum_speed_kmh=r.maximum_speed_kmh,
            starting_tractive_effort_kn=r.starting_tractive_effort_kn,
            manufacturing_year_from=r.manufacturing_year_from,
            manufacturing_year_to=r.manufacturing_year_to,
            default_ecm_provider_id=UUID(r.default_ecm_provider_id) if r.default_ecm_provider_id else None,
            is_active=r.is_active,
        )

    # ---------------- Homologations ----------------

    def upsert_homologation(self, h: Homologation) -> Homologation:
        with self._sf() as session:
            existing = session.execute(
                select(HomologationRow).where(HomologationRow.homologation_code == h.homologation_code.upper())
            ).scalar_one_or_none()
            if existing is not None:
                existing.homologation_name = h.homologation_name
                existing.description = h.description
                existing.valid_from = h.valid_from
                existing.valid_to = h.valid_to
                existing.status = h.status.value
                session.commit()
                return self._row_to_homologation(existing)
            row = HomologationRow(
                homologation_id=_s(h.homologation_id),
                homologation_code=h.homologation_code.upper(),
                homologation_name=h.homologation_name,
                description=h.description,
                valid_from=h.valid_from,
                valid_to=h.valid_to,
                status=h.status.value,
            )
            session.add(row)
            session.commit()
            return h

    def get_homologation(self, hid: UUID) -> Homologation | None:
        with self._sf() as session:
            row = session.get(HomologationRow, _s(hid))
            return self._row_to_homologation(row) if row else None

    def get_homologation_by_code(self, code: str) -> Homologation | None:
        with self._sf() as session:
            row = session.execute(
                select(HomologationRow).where(HomologationRow.homologation_code == code.upper())
            ).scalar_one_or_none()
            return self._row_to_homologation(row) if row else None

    def list_homologations(self) -> list[Homologation]:
        with self._sf() as session:
            rows = session.execute(
                select(HomologationRow).order_by(HomologationRow.homologation_code)
            ).scalars().all()
            return [self._row_to_homologation(r) for r in rows]

    @staticmethod
    def _row_to_homologation(r: HomologationRow) -> Homologation:
        return Homologation(
            homologation_id=UUID(r.homologation_id),
            homologation_code=r.homologation_code,
            homologation_name=r.homologation_name,
            description=r.description,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
            status=StatutHomologation(r.status),
        )

    # ---------------- M2M : Variant-Homologation ----------------

    def set_variant_homologation(self, link: VariantHomologation) -> VariantHomologation:
        with self._sf() as session:
            if session.get(TechnicalVariantRow, _s(link.technical_variant_id)) is None:
                raise ValueError(f"Variant {link.technical_variant_id} inconnue")
            if session.get(HomologationRow, _s(link.homologation_id)) is None:
                raise ValueError(f"Homologation {link.homologation_id} inconnue")
            existing = session.get(
                VariantHomologationRow,
                (_s(link.technical_variant_id), _s(link.homologation_id)),
            )
            if existing:
                existing.is_standard = link.is_standard
                existing.additional_cost = link.additional_cost
                existing.valid_from = link.valid_from
                existing.valid_to = link.valid_to
            else:
                session.add(VariantHomologationRow(
                    technical_variant_id=_s(link.technical_variant_id),
                    homologation_id=_s(link.homologation_id),
                    is_standard=link.is_standard,
                    additional_cost=link.additional_cost,
                    valid_from=link.valid_from,
                    valid_to=link.valid_to,
                ))
            session.commit()
            return link

    def remove_variant_homologation(self, variant_id: UUID, homologation_id: UUID) -> bool:
        with self._sf() as session:
            existing = session.get(
                VariantHomologationRow, (_s(variant_id), _s(homologation_id))
            )
            if existing is None:
                return False
            session.delete(existing)
            session.commit()
            return True

    def list_homologations_for_variant(self, technical_variant_id: UUID) -> list[Homologation]:
        with self._sf() as session:
            rows = session.execute(
                select(HomologationRow).join(
                    VariantHomologationRow,
                    VariantHomologationRow.homologation_id == HomologationRow.homologation_id,
                ).where(VariantHomologationRow.technical_variant_id == _s(technical_variant_id))
            ).scalars().all()
            return [self._row_to_homologation(r) for r in rows]

    def list_variants_for_homologation(self, homologation_id: UUID) -> list[TechnicalVariant]:
        with self._sf() as session:
            rows = session.execute(
                select(TechnicalVariantRow).join(
                    VariantHomologationRow,
                    VariantHomologationRow.technical_variant_id == TechnicalVariantRow.technical_variant_id,
                ).where(VariantHomologationRow.homologation_id == _s(homologation_id))
            ).scalars().all()
            return [self._row_to_variant(r) for r in rows]

    def set_homologation_country(self, link: HomologationCountry) -> HomologationCountry:
        with self._sf() as session:
            if session.get(HomologationRow, _s(link.homologation_id)) is None:
                raise ValueError(f"Homologation {link.homologation_id} inconnue")
            if session.get(CountryRow, _s(link.country_id)) is None:
                raise ValueError(f"Country {link.country_id} inconnu")
            existing = session.get(
                HomologationCountryRow, (_s(link.homologation_id), _s(link.country_id))
            )
            if existing:
                existing.network_code = link.network_code
                existing.is_approved = link.is_approved
                existing.valid_from = link.valid_from
                existing.valid_to = link.valid_to
            else:
                session.add(HomologationCountryRow(
                    homologation_id=_s(link.homologation_id),
                    country_id=_s(link.country_id),
                    network_code=link.network_code,
                    is_approved=link.is_approved,
                    valid_from=link.valid_from,
                    valid_to=link.valid_to,
                ))
            session.commit()
            return link

    def list_countries_for_homologation(self, homologation_id: UUID) -> list[Country]:
        with self._sf() as session:
            rows = session.execute(
                select(CountryRow).join(
                    HomologationCountryRow,
                    HomologationCountryRow.country_id == CountryRow.country_id,
                ).where(HomologationCountryRow.homologation_id == _s(homologation_id))
            ).scalars().all()
            return [self._row_to_country(r) for r in rows]

    def list_variant_homologation_links(self) -> list[VariantHomologation]:
        with self._sf() as session:
            rows = session.execute(select(VariantHomologationRow)).scalars().all()
            return [
                VariantHomologation(
                    technical_variant_id=UUID(r.technical_variant_id),
                    homologation_id=UUID(r.homologation_id),
                    is_standard=r.is_standard,
                    additional_cost=r.additional_cost,
                    valid_from=r.valid_from,
                    valid_to=r.valid_to,
                )
                for r in rows
            ]

    def list_homologation_country_links(self) -> list[HomologationCountry]:
        with self._sf() as session:
            rows = session.execute(select(HomologationCountryRow)).scalars().all()
            return [
                HomologationCountry(
                    homologation_id=UUID(r.homologation_id),
                    country_id=UUID(r.country_id),
                    network_code=r.network_code,
                    is_approved=r.is_approved,
                    valid_from=r.valid_from,
                    valid_to=r.valid_to,
                )
                for r in rows
            ]

    # =========================================================================
    # Lot 2 — Usage & Maintenance
    # =========================================================================

    def _ensure_lot2(self):
        """Compat API in-memory : SQL n'a pas d'init paresseuse à faire."""
        pass

    # --- UsageProfile ---

    def upsert_usage_profile(self, u: UsageProfile) -> UsageProfile:
        with self._sf() as session:
            existing = session.execute(
                select(UsageProfileRow).where(UsageProfileRow.usage_profile_code == u.usage_profile_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                usage_profile_name=u.usage_profile_name,
                annual_mileage_min_km=u.annual_mileage_min_km,
                annual_mileage_max_km=u.annual_mileage_max_km,
                annual_engine_hours_min=u.annual_engine_hours_min,
                annual_engine_hours_max=u.annual_engine_hours_max,
                monthly_mileage_min_km=u.monthly_mileage_min_km,
                monthly_mileage_max_km=u.monthly_mileage_max_km,
                utilisation_type=u.utilisation_type.value,
                description=u.description,
                is_active=u.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_usage_profile(existing)
            session.add(UsageProfileRow(
                usage_profile_id=_s(u.usage_profile_id),
                usage_profile_code=u.usage_profile_code.upper(),
                **attrs,
            ))
            session.commit()
            return u

    def get_usage_profile(self, uid: UUID) -> UsageProfile | None:
        with self._sf() as session:
            row = session.get(UsageProfileRow, _s(uid))
            return self._row_to_usage_profile(row) if row else None

    def get_usage_profile_by_code(self, code: str) -> UsageProfile | None:
        with self._sf() as session:
            row = session.execute(
                select(UsageProfileRow).where(UsageProfileRow.usage_profile_code == code.upper())
            ).scalar_one_or_none()
            return self._row_to_usage_profile(row) if row else None

    def list_usage_profiles(self) -> list[UsageProfile]:
        with self._sf() as session:
            rows = session.execute(
                select(UsageProfileRow).order_by(UsageProfileRow.annual_mileage_min_km.nulls_first())
            ).scalars().all()
            return [self._row_to_usage_profile(r) for r in rows]

    @staticmethod
    def _row_to_usage_profile(r: UsageProfileRow) -> UsageProfile:
        return UsageProfile(
            usage_profile_id=UUID(r.usage_profile_id),
            usage_profile_code=r.usage_profile_code,
            usage_profile_name=r.usage_profile_name,
            annual_mileage_min_km=r.annual_mileage_min_km,
            annual_mileage_max_km=r.annual_mileage_max_km,
            annual_engine_hours_min=r.annual_engine_hours_min,
            annual_engine_hours_max=r.annual_engine_hours_max,
            monthly_mileage_min_km=r.monthly_mileage_min_km,
            monthly_mileage_max_km=r.monthly_mileage_max_km,
            utilisation_type=UtilisationType(r.utilisation_type),
            description=r.description,
            is_active=r.is_active,
        )

    # --- MileageBand ---

    def upsert_mileage_band(self, b: MileageBand) -> MileageBand:
        with self._sf() as session:
            existing = session.execute(
                select(MileageBandRow).where(MileageBandRow.band_code == b.band_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                band_name=b.band_name,
                min_annual_mileage_km=b.min_annual_mileage_km,
                max_annual_mileage_km=b.max_annual_mileage_km,
                calculation_method=b.calculation_method.value,
                is_active=b.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_mileage_band(existing)
            session.add(MileageBandRow(
                mileage_band_id=_s(b.mileage_band_id),
                band_code=b.band_code.upper(),
                **attrs,
            ))
            session.commit()
            return b

    def list_mileage_bands(self) -> list[MileageBand]:
        with self._sf() as session:
            rows = session.execute(
                select(MileageBandRow).order_by(MileageBandRow.min_annual_mileage_km)
            ).scalars().all()
            return [self._row_to_mileage_band(r) for r in rows]

    def get_mileage_band_for_annual_km(self, annual_km: int) -> MileageBand | None:
        """Résolution : SQL côté serveur plutôt que full-scan Python."""
        with self._sf() as session:
            from sqlalchemy import or_, and_
            rows = session.execute(
                select(MileageBandRow).where(and_(
                    MileageBandRow.min_annual_mileage_km <= annual_km,
                    or_(
                        MileageBandRow.max_annual_mileage_km.is_(None),
                        MileageBandRow.max_annual_mileage_km > annual_km,
                    ),
                )).order_by(MileageBandRow.min_annual_mileage_km.desc())
            ).scalars().first()
            return self._row_to_mileage_band(rows) if rows else None

    @staticmethod
    def _row_to_mileage_band(r: MileageBandRow) -> MileageBand:
        return MileageBand(
            mileage_band_id=UUID(r.mileage_band_id),
            band_code=r.band_code,
            band_name=r.band_name,
            min_annual_mileage_km=r.min_annual_mileage_km,
            max_annual_mileage_km=r.max_annual_mileage_km,
            calculation_method=CalculationMethod(r.calculation_method),
            is_active=r.is_active,
        )

    # --- EngineHoursBand ---

    def upsert_engine_hours_band(self, b: EngineHoursBand) -> EngineHoursBand:
        with self._sf() as session:
            existing = session.execute(
                select(EngineHoursBandRow).where(EngineHoursBandRow.band_code == b.band_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                band_name=b.band_name,
                min_annual_engine_hours=b.min_annual_engine_hours,
                max_annual_engine_hours=b.max_annual_engine_hours,
                is_active=b.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return EngineHoursBand(
                    engine_hours_band_id=UUID(existing.engine_hours_band_id),
                    band_code=existing.band_code, **attrs,
                )
            session.add(EngineHoursBandRow(
                engine_hours_band_id=_s(b.engine_hours_band_id),
                band_code=b.band_code.upper(),
                **attrs,
            ))
            session.commit()
            return b

    def list_engine_hours_bands(self) -> list[EngineHoursBand]:
        with self._sf() as session:
            rows = session.execute(
                select(EngineHoursBandRow).order_by(EngineHoursBandRow.min_annual_engine_hours)
            ).scalars().all()
            return [
                EngineHoursBand(
                    engine_hours_band_id=UUID(r.engine_hours_band_id),
                    band_code=r.band_code, band_name=r.band_name,
                    min_annual_engine_hours=r.min_annual_engine_hours,
                    max_annual_engine_hours=r.max_annual_engine_hours,
                    is_active=r.is_active,
                )
                for r in rows
            ]

    # --- MaintenanceOperation ---

    def upsert_maintenance_operation(self, o: MaintenanceOperation) -> MaintenanceOperation:
        with self._sf() as session:
            existing = session.execute(
                select(MaintenanceOperationRow).where(MaintenanceOperationRow.operation_code == o.operation_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                operation_name=o.operation_name,
                operation_type=o.operation_type.value,
                trigger_type=o.trigger_type.value,
                interval_mileage_km=o.interval_mileage_km,
                interval_engine_hours=o.interval_engine_hours,
                interval_months=o.interval_months,
                standard_duration_hours=o.standard_duration_hours,
                description=o.description,
                is_active=o.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_operation(existing)
            session.add(MaintenanceOperationRow(
                operation_id=_s(o.operation_id),
                operation_code=o.operation_code.upper(),
                **attrs,
            ))
            session.commit()
            return o

    def list_maintenance_operations(self) -> list[MaintenanceOperation]:
        with self._sf() as session:
            rows = session.execute(
                select(MaintenanceOperationRow).order_by(MaintenanceOperationRow.operation_code)
            ).scalars().all()
            return [self._row_to_operation(r) for r in rows]

    @staticmethod
    def _row_to_operation(r: MaintenanceOperationRow) -> MaintenanceOperation:
        return MaintenanceOperation(
            operation_id=UUID(r.operation_id),
            operation_code=r.operation_code,
            operation_name=r.operation_name,
            operation_type=OperationType(r.operation_type),
            trigger_type=TriggerType(r.trigger_type),
            interval_mileage_km=r.interval_mileage_km,
            interval_engine_hours=r.interval_engine_hours,
            interval_months=r.interval_months,
            standard_duration_hours=r.standard_duration_hours,
            description=r.description,
            is_active=r.is_active,
        )

    # --- MaintenancePlan ---

    def upsert_maintenance_plan(self, p: MaintenancePlan) -> MaintenancePlan:
        with self._sf() as session:
            existing = session.execute(
                select(MaintenancePlanRow).where(MaintenancePlanRow.plan_code == p.plan_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                plan_name=p.plan_name,
                manufacturer_id=_s(p.manufacturer_id) if p.manufacturer_id else None,
                description=p.description,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
                is_active=p.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_plan(existing)
            session.add(MaintenancePlanRow(
                maintenance_plan_id=_s(p.maintenance_plan_id),
                plan_code=p.plan_code.upper(),
                **attrs,
            ))
            session.commit()
            return p

    def list_maintenance_plans(self) -> list[MaintenancePlan]:
        with self._sf() as session:
            rows = session.execute(
                select(MaintenancePlanRow).order_by(MaintenancePlanRow.plan_code)
            ).scalars().all()
            return [self._row_to_plan(r) for r in rows]

    @staticmethod
    def _row_to_plan(r: MaintenancePlanRow) -> MaintenancePlan:
        return MaintenancePlan(
            maintenance_plan_id=UUID(r.maintenance_plan_id),
            plan_code=r.plan_code, plan_name=r.plan_name,
            manufacturer_id=UUID(r.manufacturer_id) if r.manufacturer_id else None,
            description=r.description, valid_from=r.valid_from, valid_to=r.valid_to,
            is_active=r.is_active,
        )

    def add_plan_operation(self, link: MaintenancePlanOperation) -> MaintenancePlanOperation:
        with self._sf() as session:
            if session.get(MaintenancePlanRow, _s(link.maintenance_plan_id)) is None:
                raise ValueError(f"MaintenancePlan {link.maintenance_plan_id} inconnu")
            if session.get(MaintenanceOperationRow, _s(link.operation_id)) is None:
                raise ValueError(f"MaintenanceOperation {link.operation_id} inconnue")
            existing = session.get(
                MaintenancePlanOperationRow, (_s(link.maintenance_plan_id), _s(link.operation_id))
            )
            if existing:
                existing.sequence_order = link.sequence_order
                existing.is_optional = link.is_optional
                existing.frequency_multiplier = link.frequency_multiplier
            else:
                session.add(MaintenancePlanOperationRow(
                    maintenance_plan_id=_s(link.maintenance_plan_id),
                    operation_id=_s(link.operation_id),
                    sequence_order=link.sequence_order,
                    is_optional=link.is_optional,
                    frequency_multiplier=link.frequency_multiplier,
                ))
            session.commit()
            return link

    def list_operations_for_plan(self, plan_id: UUID) -> list[MaintenanceOperation]:
        with self._sf() as session:
            rows = session.execute(
                select(MaintenanceOperationRow).join(
                    MaintenancePlanOperationRow,
                    MaintenancePlanOperationRow.operation_id == MaintenanceOperationRow.operation_id,
                ).where(MaintenancePlanOperationRow.maintenance_plan_id == _s(plan_id))
                .order_by(MaintenancePlanOperationRow.sequence_order)
            ).scalars().all()
            return [self._row_to_operation(r) for r in rows]

    # --- ECM Providers ---

    def upsert_ecm_provider(self, e: EcmProvider) -> EcmProvider:
        with self._sf() as session:
            existing = session.execute(
                select(EcmProviderRow).where(EcmProviderRow.provider_code == e.provider_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                provider_name=e.provider_name,
                certification_number=e.certification_number,
                certification_valid_from=e.certification_valid_from,
                certification_valid_to=e.certification_valid_to,
                description=e.description,
                is_active=e.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_ecm(existing)
            session.add(EcmProviderRow(
                ecm_provider_id=_s(e.ecm_provider_id),
                provider_code=e.provider_code.upper(),
                **attrs,
            ))
            session.commit()
            return e

    def list_ecm_providers(self) -> list[EcmProvider]:
        with self._sf() as session:
            rows = session.execute(
                select(EcmProviderRow).order_by(EcmProviderRow.provider_code)
            ).scalars().all()
            return [self._row_to_ecm(r) for r in rows]

    @staticmethod
    def _row_to_ecm(r: EcmProviderRow) -> EcmProvider:
        return EcmProvider(
            ecm_provider_id=UUID(r.ecm_provider_id),
            provider_code=r.provider_code, provider_name=r.provider_name,
            certification_number=r.certification_number,
            certification_valid_from=r.certification_valid_from,
            certification_valid_to=r.certification_valid_to,
            description=r.description, is_active=r.is_active,
        )

    # --- Service Levels ---

    def upsert_service_level(self, s: ServiceLevel) -> ServiceLevel:
        with self._sf() as session:
            existing = session.execute(
                select(ServiceLevelRow).where(ServiceLevelRow.service_level_code == s.service_level_code.value.upper())
            ).scalar_one_or_none()
            attrs = dict(
                service_level_name=s.service_level_name,
                hotline_included=s.hotline_included,
                hotline_coverage=s.hotline_coverage,
                response_time_hours=s.response_time_hours,
                description=s.description,
                is_active=s.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_sl(existing)
            session.add(ServiceLevelRow(
                service_level_id=_s(s.service_level_id),
                service_level_code=s.service_level_code.value.upper(),
                **attrs,
            ))
            session.commit()
            return s

    def list_service_levels(self) -> list[ServiceLevel]:
        with self._sf() as session:
            rows = session.execute(
                select(ServiceLevelRow).order_by(ServiceLevelRow.service_level_code)
            ).scalars().all()
            return [self._row_to_sl(r) for r in rows]

    @staticmethod
    def _row_to_sl(r: ServiceLevelRow) -> ServiceLevel:
        return ServiceLevel(
            service_level_id=UUID(r.service_level_id),
            service_level_code=ServiceLevelCode(r.service_level_code),
            service_level_name=r.service_level_name,
            hotline_included=r.hotline_included,
            hotline_coverage=r.hotline_coverage,
            response_time_hours=r.response_time_hours,
            description=r.description, is_active=r.is_active,
        )

    # --- Associations variantes ↔ (usage, mileage, maintenance) ---

    def set_variant_usage_profile(self, link: VariantUsageProfile) -> VariantUsageProfile:
        with self._sf() as session:
            existing = session.get(VariantUsageProfileRow, (_s(link.technical_variant_id), _s(link.usage_profile_id)))
            attrs = dict(
                is_supported=link.is_supported,
                warning_threshold_km=link.warning_threshold_km,
                maximum_contractual_mileage_km=link.maximum_contractual_mileage_km,
                requires_specific_approval=link.requires_specific_approval,
                valid_from=link.valid_from, valid_to=link.valid_to,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(VariantUsageProfileRow(
                    technical_variant_id=_s(link.technical_variant_id),
                    usage_profile_id=_s(link.usage_profile_id),
                    **attrs,
                ))
            session.commit()
            return link

    def list_usage_profiles_for_variant(self, variant_id: UUID) -> list[tuple[UsageProfile, VariantUsageProfile]]:
        with self._sf() as session:
            rows = session.execute(
                select(UsageProfileRow, VariantUsageProfileRow).join(
                    VariantUsageProfileRow,
                    VariantUsageProfileRow.usage_profile_id == UsageProfileRow.usage_profile_id,
                ).where(VariantUsageProfileRow.technical_variant_id == _s(variant_id))
            ).all()
            return [
                (
                    self._row_to_usage_profile(up),
                    VariantUsageProfile(
                        technical_variant_id=UUID(link.technical_variant_id),
                        usage_profile_id=UUID(link.usage_profile_id),
                        is_supported=link.is_supported,
                        warning_threshold_km=link.warning_threshold_km,
                        maximum_contractual_mileage_km=link.maximum_contractual_mileage_km,
                        requires_specific_approval=link.requires_specific_approval,
                        valid_from=link.valid_from, valid_to=link.valid_to,
                    ),
                )
                for up, link in rows
            ]

    def set_variant_mileage_band(self, link: VariantMileageBand) -> VariantMileageBand:
        with self._sf() as session:
            existing = session.get(VariantMileageBandRow, (_s(link.technical_variant_id), _s(link.mileage_band_id)))
            if existing:
                existing.is_supported = link.is_supported
                existing.valid_from = link.valid_from
                existing.valid_to = link.valid_to
            else:
                session.add(VariantMileageBandRow(
                    technical_variant_id=_s(link.technical_variant_id),
                    mileage_band_id=_s(link.mileage_band_id),
                    is_supported=link.is_supported,
                    valid_from=link.valid_from, valid_to=link.valid_to,
                ))
            session.commit()
            return link

    def list_mileage_bands_for_variant(self, variant_id: UUID) -> list[MileageBand]:
        with self._sf() as session:
            rows = session.execute(
                select(MileageBandRow).join(
                    VariantMileageBandRow,
                    VariantMileageBandRow.mileage_band_id == MileageBandRow.mileage_band_id,
                ).where(VariantMileageBandRow.technical_variant_id == _s(variant_id))
            ).scalars().all()
            return [self._row_to_mileage_band(r) for r in rows]

    def set_variant_maintenance_plan(self, link: VariantMaintenancePlan) -> VariantMaintenancePlan:
        with self._sf() as session:
            existing = session.get(VariantMaintenancePlanRow, (_s(link.technical_variant_id), _s(link.maintenance_plan_id)))
            if existing:
                existing.is_default = link.is_default
                existing.valid_from = link.valid_from
                existing.valid_to = link.valid_to
            else:
                session.add(VariantMaintenancePlanRow(
                    technical_variant_id=_s(link.technical_variant_id),
                    maintenance_plan_id=_s(link.maintenance_plan_id),
                    is_default=link.is_default,
                    valid_from=link.valid_from, valid_to=link.valid_to,
                ))
            session.commit()
            return link

    def list_maintenance_plans_for_variant(self, variant_id: UUID) -> list[MaintenancePlan]:
        with self._sf() as session:
            rows = session.execute(
                select(MaintenancePlanRow).join(
                    VariantMaintenancePlanRow,
                    VariantMaintenancePlanRow.maintenance_plan_id == MaintenancePlanRow.maintenance_plan_id,
                ).where(VariantMaintenancePlanRow.technical_variant_id == _s(variant_id))
            ).scalars().all()
            return [self._row_to_plan(r) for r in rows]

    # =========================================================================
    # Lot 3 — Tarifs versionnés
    # =========================================================================

    def _ensure_lot3(self):
        pass

    # --- Dimensions ---

    def upsert_lease_band(self, b: LeaseBand) -> LeaseBand:
        with self._sf() as session:
            existing = session.execute(
                select(LeaseBandRow).where(LeaseBandRow.band_code == b.band_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                band_name=b.band_name,
                min_duration_months=b.min_duration_months,
                max_duration_months=b.max_duration_months,
                is_active=b.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(LeaseBandRow(
                    lease_band_id=_s(b.lease_band_id),
                    band_code=b.band_code.upper(),
                    **attrs,
                ))
            session.commit()
            return b

    def list_lease_bands(self) -> list[LeaseBand]:
        with self._sf() as session:
            rows = session.execute(
                select(LeaseBandRow).order_by(LeaseBandRow.min_duration_months)
            ).scalars().all()
            return [
                LeaseBand(
                    lease_band_id=UUID(r.lease_band_id),
                    band_code=r.band_code, band_name=r.band_name,
                    min_duration_months=r.min_duration_months,
                    max_duration_months=r.max_duration_months,
                    is_active=r.is_active,
                )
                for r in rows
            ]

    def get_lease_band_for_duration(self, months: int) -> LeaseBand | None:
        with self._sf() as session:
            from sqlalchemy import or_, and_
            row = session.execute(
                select(LeaseBandRow).where(and_(
                    LeaseBandRow.min_duration_months <= months,
                    or_(
                        LeaseBandRow.max_duration_months.is_(None),
                        LeaseBandRow.max_duration_months >= months,
                    ),
                )).order_by(LeaseBandRow.min_duration_months.desc())
            ).scalars().first()
            return LeaseBand(
                lease_band_id=UUID(row.lease_band_id),
                band_code=row.band_code, band_name=row.band_name,
                min_duration_months=row.min_duration_months,
                max_duration_months=row.max_duration_months,
                is_active=row.is_active,
            ) if row else None

    def upsert_asset_age_band(self, b: AssetAgeBand) -> AssetAgeBand:
        with self._sf() as session:
            existing = session.execute(
                select(AssetAgeBandRow).where(AssetAgeBandRow.band_code == b.band_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                band_name=b.band_name,
                min_age_years=b.min_age_years,
                max_age_years=b.max_age_years,
                is_active=b.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(AssetAgeBandRow(
                    asset_age_band_id=_s(b.asset_age_band_id),
                    band_code=b.band_code.upper(),
                    **attrs,
                ))
            session.commit()
            return b

    def list_asset_age_bands(self) -> list[AssetAgeBand]:
        with self._sf() as session:
            rows = session.execute(
                select(AssetAgeBandRow).order_by(AssetAgeBandRow.min_age_years)
            ).scalars().all()
            return [
                AssetAgeBand(
                    asset_age_band_id=UUID(r.asset_age_band_id),
                    band_code=r.band_code, band_name=r.band_name,
                    min_age_years=r.min_age_years,
                    max_age_years=r.max_age_years,
                    is_active=r.is_active,
                )
                for r in rows
            ]

    def get_asset_age_band_for_age(self, age_years: float) -> AssetAgeBand | None:
        with self._sf() as session:
            from sqlalchemy import or_, and_
            row = session.execute(
                select(AssetAgeBandRow).where(and_(
                    AssetAgeBandRow.min_age_years <= age_years,
                    or_(
                        AssetAgeBandRow.max_age_years.is_(None),
                        AssetAgeBandRow.max_age_years > age_years,
                    ),
                )).order_by(AssetAgeBandRow.min_age_years.desc())
            ).scalars().first()
            return AssetAgeBand(
                asset_age_band_id=UUID(row.asset_age_band_id),
                band_code=row.band_code, band_name=row.band_name,
                min_age_years=row.min_age_years,
                max_age_years=row.max_age_years,
                is_active=row.is_active,
            ) if row else None

    def upsert_country_group(self, g: CountryGroup) -> CountryGroup:
        with self._sf() as session:
            existing = session.execute(
                select(CountryGroupRow).where(CountryGroupRow.group_code == g.group_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                group_name=g.group_name,
                country_iso_codes=list(g.country_iso_codes),
                description=g.description,
                is_active=g.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(CountryGroupRow(
                    country_group_id=_s(g.country_group_id),
                    group_code=g.group_code.upper(),
                    **attrs,
                ))
            session.commit()
            return g

    def list_country_groups(self) -> list[CountryGroup]:
        with self._sf() as session:
            rows = session.execute(
                select(CountryGroupRow).order_by(CountryGroupRow.group_code)
            ).scalars().all()
            return [
                CountryGroup(
                    country_group_id=UUID(r.country_group_id),
                    group_code=r.group_code, group_name=r.group_name,
                    country_iso_codes=list(r.country_iso_codes or []),
                    description=r.description, is_active=r.is_active,
                )
                for r in rows
            ]

    def get_country_group_for_iso(self, iso: str) -> CountryGroup | None:
        iso_u = iso.upper()
        for g in self.list_country_groups():
            if g.contient_pays(iso_u):
                return g
        return None

    def upsert_commercial_option(self, c: CommercialOption) -> CommercialOption:
        with self._sf() as session:
            existing = session.execute(
                select(CommercialOptionRow).where(CommercialOptionRow.option_code == c.option_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                option_name=c.option_name,
                option_type=c.option_type,
                default_billing_unit=c.default_billing_unit.value,
                description=c.description,
                is_active=c.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(CommercialOptionRow(
                    commercial_option_id=_s(c.commercial_option_id),
                    option_code=c.option_code.upper(),
                    **attrs,
                ))
            session.commit()
            return c

    def list_commercial_options(self) -> list[CommercialOption]:
        with self._sf() as session:
            rows = session.execute(
                select(CommercialOptionRow).order_by(CommercialOptionRow.option_code)
            ).scalars().all()
            return [
                CommercialOption(
                    commercial_option_id=UUID(r.commercial_option_id),
                    option_code=r.option_code, option_name=r.option_name,
                    option_type=r.option_type,
                    default_billing_unit=BillingUnit(r.default_billing_unit),
                    description=r.description, is_active=r.is_active,
                )
                for r in rows
            ]

    # --- PriceBooks + Versions ---

    def upsert_price_book(self, pb: PriceBook) -> PriceBook:
        with self._sf() as session:
            existing = session.execute(
                select(PriceBookRow).where(PriceBookRow.price_book_code == pb.price_book_code.upper())
            ).scalar_one_or_none()
            attrs = dict(
                price_book_name=pb.price_book_name,
                price_type=pb.price_type.value,
                currency_iso=pb.currency_iso,
                description=pb.description,
                is_active=pb.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
            else:
                session.add(PriceBookRow(
                    price_book_id=_s(pb.price_book_id),
                    price_book_code=pb.price_book_code.upper(),
                    **attrs,
                ))
            session.commit()
            return pb

    def list_price_books(self) -> list[PriceBook]:
        with self._sf() as session:
            rows = session.execute(
                select(PriceBookRow).order_by(PriceBookRow.price_book_code)
            ).scalars().all()
            return [
                PriceBook(
                    price_book_id=UUID(r.price_book_id),
                    price_book_code=r.price_book_code,
                    price_book_name=r.price_book_name,
                    price_type=PriceType(r.price_type),
                    currency_iso=r.currency_iso,
                    description=r.description, is_active=r.is_active,
                )
                for r in rows
            ]

    def get_price_book_by_code(self, code: str) -> PriceBook | None:
        with self._sf() as session:
            row = session.execute(
                select(PriceBookRow).where(PriceBookRow.price_book_code == code.upper())
            ).scalar_one_or_none()
            if row is None: return None
            return PriceBook(
                price_book_id=UUID(row.price_book_id),
                price_book_code=row.price_book_code,
                price_book_name=row.price_book_name,
                price_type=PriceType(row.price_type),
                currency_iso=row.currency_iso,
                description=row.description, is_active=row.is_active,
            )

    def upsert_price_book_version(self, v: PriceBookVersion) -> PriceBookVersion:
        with self._sf() as session:
            if session.get(PriceBookRow, _s(v.price_book_id)) is None:
                raise ValueError(f"PriceBook {v.price_book_id} inconnu")
            existing = session.get(PriceBookVersionRow, _s(v.price_book_version_id))
            attrs = dict(
                price_book_id=_s(v.price_book_id),
                year=v.year, version_number=v.version_number,
                status=v.status.value,
                valid_from=v.valid_from, valid_to=v.valid_to,
                currency_iso=v.currency_iso,
                approved_by=v.approved_by, approved_at=v.approved_at,
                published_at=v.published_at, description=v.description,
            )
            if existing:
                for k, val in attrs.items(): setattr(existing, k, val)
            else:
                session.add(PriceBookVersionRow(
                    price_book_version_id=_s(v.price_book_version_id),
                    **attrs,
                ))
            session.commit()
            return v

    def list_price_book_versions(self, *, price_book_id: UUID | None = None) -> list[PriceBookVersion]:
        with self._sf() as session:
            stmt = select(PriceBookVersionRow)
            if price_book_id is not None:
                stmt = stmt.where(PriceBookVersionRow.price_book_id == _s(price_book_id))
            rows = session.execute(
                stmt.order_by(PriceBookVersionRow.year.desc(), PriceBookVersionRow.version_number.desc())
            ).scalars().all()
            return [self._row_to_pbv(r) for r in rows]

    def get_current_published_version(self, price_book_code: str, at_date=None) -> PriceBookVersion | None:
        """Résolution SQL : prend la version publiée la plus récente qui
        couvre la date demandée."""
        from datetime import date as date_cls
        from sqlalchemy import or_, and_
        if at_date is None:
            at_date = date_cls.today()
        with self._sf() as session:
            pb = session.execute(
                select(PriceBookRow).where(PriceBookRow.price_book_code == price_book_code.upper())
            ).scalar_one_or_none()
            if pb is None: return None
            row = session.execute(
                select(PriceBookVersionRow).where(and_(
                    PriceBookVersionRow.price_book_id == pb.price_book_id,
                    PriceBookVersionRow.status == "published",
                    PriceBookVersionRow.valid_from <= at_date,
                    or_(
                        PriceBookVersionRow.valid_to.is_(None),
                        PriceBookVersionRow.valid_to >= at_date,
                    ),
                )).order_by(
                    PriceBookVersionRow.year.desc(),
                    PriceBookVersionRow.version_number.desc(),
                )
            ).scalars().first()
            return self._row_to_pbv(row) if row else None

    @staticmethod
    def _row_to_pbv(r: PriceBookVersionRow) -> PriceBookVersion:
        return PriceBookVersion(
            price_book_version_id=UUID(r.price_book_version_id),
            price_book_id=UUID(r.price_book_id),
            year=r.year, version_number=r.version_number,
            status=PriceBookStatus(r.status),
            valid_from=r.valid_from, valid_to=r.valid_to,
            currency_iso=r.currency_iso,
            approved_by=r.approved_by, approved_at=r.approved_at,
            published_at=r.published_at, description=r.description,
        )

    # --- Rates ---

    def add_dry_lease_rate(self, r: DryLeaseRate) -> DryLeaseRate:
        with self._sf() as session:
            if session.get(PriceBookVersionRow, _s(r.price_book_version_id)) is None:
                raise ValueError(f"PriceBookVersion {r.price_book_version_id} inconnue")
            session.add(DryLeaseRateRow(
                dry_lease_rate_id=_s(r.dry_lease_rate_id),
                price_book_version_id=_s(r.price_book_version_id),
                technical_variant_id=_s(r.technical_variant_id),
                country_group_id=_s(r.country_group_id),
                lease_band_id=_s(r.lease_band_id),
                asset_age_band_id=_s(r.asset_age_band_id),
                monthly_base_rent=r.monthly_base_rent,
                insurance_amount=r.insurance_amount,
                risk_provision_amount=r.risk_provision_amount,
                specific_commitment_rate=r.specific_commitment_rate,
                minimum_price=r.minimum_price,
                currency_iso=r.currency_iso,
                valid_from=r.valid_from, valid_to=r.valid_to,
            ))
            session.commit()
            return r

    def list_dry_lease_rates(self, *, version_id: UUID | None = None) -> list[DryLeaseRate]:
        with self._sf() as session:
            stmt = select(DryLeaseRateRow)
            if version_id is not None:
                stmt = stmt.where(DryLeaseRateRow.price_book_version_id == _s(version_id))
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_dl(r) for r in rows]

    def find_dry_lease_rate(self, version_id, variant_id, country_group_id,
                            lease_band_id, asset_age_band_id) -> DryLeaseRate | None:
        """Lookup unique via l'index composite ix_dl_lookup."""
        with self._sf() as session:
            from sqlalchemy import and_
            row = session.execute(
                select(DryLeaseRateRow).where(and_(
                    DryLeaseRateRow.price_book_version_id == _s(version_id),
                    DryLeaseRateRow.technical_variant_id == _s(variant_id),
                    DryLeaseRateRow.country_group_id == _s(country_group_id),
                    DryLeaseRateRow.lease_band_id == _s(lease_band_id),
                    DryLeaseRateRow.asset_age_band_id == _s(asset_age_band_id),
                ))
            ).scalar_one_or_none()
            return self._row_to_dl(row) if row else None

    @staticmethod
    def _row_to_dl(r: DryLeaseRateRow) -> DryLeaseRate:
        return DryLeaseRate(
            dry_lease_rate_id=UUID(r.dry_lease_rate_id),
            price_book_version_id=UUID(r.price_book_version_id),
            technical_variant_id=UUID(r.technical_variant_id),
            country_group_id=UUID(r.country_group_id),
            lease_band_id=UUID(r.lease_band_id),
            asset_age_band_id=UUID(r.asset_age_band_id),
            monthly_base_rent=r.monthly_base_rent,
            insurance_amount=r.insurance_amount,
            risk_provision_amount=r.risk_provision_amount,
            specific_commitment_rate=r.specific_commitment_rate,
            minimum_price=r.minimum_price,
            currency_iso=r.currency_iso,
            valid_from=r.valid_from, valid_to=r.valid_to,
        )

    def add_heavy_maintenance_rate(self, r: HeavyMaintenanceRate) -> HeavyMaintenanceRate:
        with self._sf() as session:
            if session.get(PriceBookVersionRow, _s(r.price_book_version_id)) is None:
                raise ValueError(f"PriceBookVersion {r.price_book_version_id} inconnue")
            session.add(HeavyMaintenanceRateRow(
                heavy_maintenance_rate_id=_s(r.heavy_maintenance_rate_id),
                price_book_version_id=_s(r.price_book_version_id),
                technical_variant_id=_s(r.technical_variant_id),
                operation_id=_s(r.operation_id),
                country_group_id=_s(r.country_group_id) if r.country_group_id else None,
                workshop_id=_s(r.workshop_id) if r.workshop_id else None,
                calculation_method=r.calculation_method.value,
                cost_amount=r.cost_amount,
                selling_price=r.selling_price,
                billing_unit=r.billing_unit.value,
                monthly_provision_amount=r.monthly_provision_amount,
                currency_iso=r.currency_iso,
                valid_from=r.valid_from, valid_to=r.valid_to,
            ))
            session.commit()
            return r

    def list_heavy_maintenance_rates(self, *, version_id: UUID | None = None) -> list[HeavyMaintenanceRate]:
        with self._sf() as session:
            stmt = select(HeavyMaintenanceRateRow)
            if version_id is not None:
                stmt = stmt.where(HeavyMaintenanceRateRow.price_book_version_id == _s(version_id))
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_hm(r) for r in rows]

    def find_heavy_maintenance_rates(self, version_id, variant_id) -> list[HeavyMaintenanceRate]:
        with self._sf() as session:
            from sqlalchemy import and_
            rows = session.execute(
                select(HeavyMaintenanceRateRow).where(and_(
                    HeavyMaintenanceRateRow.price_book_version_id == _s(version_id),
                    HeavyMaintenanceRateRow.technical_variant_id == _s(variant_id),
                ))
            ).scalars().all()
            return [self._row_to_hm(r) for r in rows]

    @staticmethod
    def _row_to_hm(r: HeavyMaintenanceRateRow) -> HeavyMaintenanceRate:
        return HeavyMaintenanceRate(
            heavy_maintenance_rate_id=UUID(r.heavy_maintenance_rate_id),
            price_book_version_id=UUID(r.price_book_version_id),
            technical_variant_id=UUID(r.technical_variant_id),
            operation_id=UUID(r.operation_id),
            country_group_id=UUID(r.country_group_id) if r.country_group_id else None,
            workshop_id=UUID(r.workshop_id) if r.workshop_id else None,
            calculation_method=CalculationMethodHM(r.calculation_method),
            cost_amount=r.cost_amount,
            selling_price=r.selling_price,
            billing_unit=BillingUnit(r.billing_unit),
            monthly_provision_amount=r.monthly_provision_amount,
            currency_iso=r.currency_iso,
            valid_from=r.valid_from, valid_to=r.valid_to,
        )

    def add_operating_maintenance_rate(self, r: OperatingMaintenanceRate) -> OperatingMaintenanceRate:
        with self._sf() as session:
            if session.get(PriceBookVersionRow, _s(r.price_book_version_id)) is None:
                raise ValueError(f"PriceBookVersion {r.price_book_version_id} inconnue")
            session.add(OperatingMaintenanceRateRow(
                operating_maintenance_rate_id=_s(r.operating_maintenance_rate_id),
                price_book_version_id=_s(r.price_book_version_id),
                technical_variant_id=_s(r.technical_variant_id),
                country_id=_s(r.country_id) if r.country_id else None,
                mileage_band_id=_s(r.mileage_band_id),
                engine_hours_band_id=_s(r.engine_hours_band_id) if r.engine_hours_band_id else None,
                ecm_provider_id=_s(r.ecm_provider_id) if r.ecm_provider_id else None,
                service_level_id=_s(r.service_level_id) if r.service_level_id else None,
                monthly_fixed_amount=r.monthly_fixed_amount,
                price_per_kilometer=r.price_per_kilometer,
                price_per_engine_hour=r.price_per_engine_hour,
                ecm_monthly_amount=r.ecm_monthly_amount,
                last_mile_monthly_amount=r.last_mile_monthly_amount,
                minimum_monthly_amount=r.minimum_monthly_amount,
                maximum_annual_amount=r.maximum_annual_amount,
                currency_iso=r.currency_iso,
                valid_from=r.valid_from, valid_to=r.valid_to,
            ))
            session.commit()
            return r

    def list_operating_maintenance_rates(self, *, version_id: UUID | None = None) -> list[OperatingMaintenanceRate]:
        with self._sf() as session:
            stmt = select(OperatingMaintenanceRateRow)
            if version_id is not None:
                stmt = stmt.where(OperatingMaintenanceRateRow.price_book_version_id == _s(version_id))
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_om(r) for r in rows]

    def find_operating_maintenance_rate(self, version_id, variant_id, mileage_band_id,
                                        country_id=None, ecm_provider_id=None,
                                        service_level_id=None) -> OperatingMaintenanceRate | None:
        """Résolution avec fallback + scoring. Pour simplicité, on prend
        tous les candidats et on score côté Python (volume faible : qq
        dizaines de rates par variante max)."""
        with self._sf() as session:
            from sqlalchemy import and_
            rows = session.execute(
                select(OperatingMaintenanceRateRow).where(and_(
                    OperatingMaintenanceRateRow.price_book_version_id == _s(version_id),
                    OperatingMaintenanceRateRow.technical_variant_id == _s(variant_id),
                    OperatingMaintenanceRateRow.mileage_band_id == _s(mileage_band_id),
                ))
            ).scalars().all()
            if not rows:
                return None

            def match_score(r) -> int:
                score = 0
                if country_id is not None:
                    if r.country_id == _s(country_id): score += 4
                    elif r.country_id is None: score += 1
                    else: return -1
                if ecm_provider_id is not None:
                    if r.ecm_provider_id == _s(ecm_provider_id): score += 2
                    elif r.ecm_provider_id is None: score += 1
                    else: return -1
                if service_level_id is not None:
                    if r.service_level_id == _s(service_level_id): score += 1
                    elif r.service_level_id is None: score += 1
                    else: return -1
                return score

            scored = [(match_score(r), r) for r in rows]
            scored = [(s, r) for s, r in scored if s >= 0]
            if not scored:
                return None
            scored.sort(key=lambda x: x[0], reverse=True)
            return self._row_to_om(scored[0][1])

    @staticmethod
    def _row_to_om(r: OperatingMaintenanceRateRow) -> OperatingMaintenanceRate:
        return OperatingMaintenanceRate(
            operating_maintenance_rate_id=UUID(r.operating_maintenance_rate_id),
            price_book_version_id=UUID(r.price_book_version_id),
            technical_variant_id=UUID(r.technical_variant_id),
            country_id=UUID(r.country_id) if r.country_id else None,
            mileage_band_id=UUID(r.mileage_band_id),
            engine_hours_band_id=UUID(r.engine_hours_band_id) if r.engine_hours_band_id else None,
            ecm_provider_id=UUID(r.ecm_provider_id) if r.ecm_provider_id else None,
            service_level_id=UUID(r.service_level_id) if r.service_level_id else None,
            monthly_fixed_amount=r.monthly_fixed_amount,
            price_per_kilometer=r.price_per_kilometer,
            price_per_engine_hour=r.price_per_engine_hour,
            ecm_monthly_amount=r.ecm_monthly_amount,
            last_mile_monthly_amount=r.last_mile_monthly_amount,
            minimum_monthly_amount=r.minimum_monthly_amount,
            maximum_annual_amount=r.maximum_annual_amount,
            currency_iso=r.currency_iso,
            valid_from=r.valid_from, valid_to=r.valid_to,
        )


    # =========================================================================
    # Lot 5 — Flotte réelle
    # =========================================================================

    def _ensure_lot5(self):
        pass

    def upsert_fleet_asset(self, a: FleetAsset) -> FleetAsset:
        with self._sf() as session:
            if session.get(TechnicalVariantRow, _s(a.technical_variant_id)) is None:
                raise ValueError(f"TechnicalVariant {a.technical_variant_id} inconnue")
            existing = session.execute(
                select(FleetAssetRow).where(FleetAssetRow.asset_number == a.asset_number.upper())
            ).scalar_one_or_none()
            attrs = dict(
                vehicle_registration_number=a.vehicle_registration_number,
                technical_variant_id=_s(a.technical_variant_id),
                manufacturing_year=a.manufacturing_year,
                commissioning_date=a.commissioning_date,
                ownership_status=a.ownership_status.value,
                operational_status=a.operational_status.value,
                current_country_id=_s(a.current_country_id) if a.current_country_id else None,
                current_mileage_km=a.current_mileage_km,
                current_engine_hours=a.current_engine_hours,
                current_ecm_provider_id=_s(a.current_ecm_provider_id) if a.current_ecm_provider_id else None,
                last_hm1_date=a.last_hm1_date,
                last_hm2_date=a.last_hm2_date,
                last_hm3_date=a.last_hm3_date,
                last_bogie_swap_date=a.last_bogie_swap_date,
                last_vgi_date=a.last_vgi_date,
                notes=a.notes,
                is_active=a.is_active,
            )
            if existing:
                for k, v in attrs.items(): setattr(existing, k, v)
                session.commit()
                return self._row_to_fleet_asset(existing)
            session.add(FleetAssetRow(
                fleet_asset_id=_s(a.fleet_asset_id),
                asset_number=a.asset_number.upper(),
                **attrs,
            ))
            session.commit()
            return a

    def get_fleet_asset(self, aid: UUID, *, include_deleted: bool = False) -> FleetAsset | None:
        with self._sf() as session:
            row = session.get(FleetAssetRow, _s(aid))
            if row is None:
                return None
            if row.deleted_at is not None and not include_deleted:
                return None
            return self._row_to_fleet_asset(row)

    def get_fleet_asset_by_asset_number(self, asset_number: str, *,
                                        include_deleted: bool = False) -> FleetAsset | None:
        with self._sf() as session:
            stmt = select(FleetAssetRow).where(FleetAssetRow.asset_number == asset_number.upper())
            if not include_deleted:
                stmt = stmt.where(FleetAssetRow.deleted_at.is_(None))
            row = session.execute(stmt).scalar_one_or_none()
            return self._row_to_fleet_asset(row) if row else None

    def list_fleet_assets(self, *, variant_id: UUID | None = None,
                          operational_status=None,
                          include_deleted: bool = False) -> list[FleetAsset]:
        with self._sf() as session:
            stmt = select(FleetAssetRow)
            if not include_deleted:
                stmt = stmt.where(FleetAssetRow.deleted_at.is_(None))
            if variant_id is not None:
                stmt = stmt.where(FleetAssetRow.technical_variant_id == _s(variant_id))
            if operational_status is not None:
                val = operational_status.value if hasattr(operational_status, "value") else operational_status
                stmt = stmt.where(FleetAssetRow.operational_status == val)
            rows = session.execute(stmt.order_by(FleetAssetRow.asset_number)).scalars().all()
            return [self._row_to_fleet_asset(r) for r in rows]

    def soft_delete_fleet_asset(self, aid: UUID, actor_email: str) -> bool:
        """Marque la loco comme supprimée sans détruire ses données.
        L'historique (relevés, maintenance, chiffrages passés) reste
        disponible pour l'audit. Retourne False si déjà supprimée ou
        inexistante."""
        with self._sf() as session:
            row = session.get(FleetAssetRow, _s(aid))
            if row is None or row.deleted_at is not None:
                return False
            row.deleted_at = datetime.now(timezone.utc)
            row.deleted_by = actor_email
            session.commit()
        return True

    def restore_fleet_asset(self, aid: UUID) -> bool:
        """Annule un soft delete. Retourne False si pas supprimée ou
        inexistante."""
        with self._sf() as session:
            row = session.get(FleetAssetRow, _s(aid))
            if row is None or row.deleted_at is None:
                return False
            row.deleted_at = None
            row.deleted_by = None
            session.commit()
        return True

    @staticmethod
    def _row_to_fleet_asset(r: FleetAssetRow) -> FleetAsset:
        return FleetAsset(
            fleet_asset_id=UUID(r.fleet_asset_id),
            asset_number=r.asset_number,
            vehicle_registration_number=r.vehicle_registration_number,
            technical_variant_id=UUID(r.technical_variant_id),
            manufacturing_year=r.manufacturing_year,
            commissioning_date=r.commissioning_date,
            ownership_status=OwnershipStatus(r.ownership_status),
            operational_status=OperationalStatus(r.operational_status),
            current_country_id=UUID(r.current_country_id) if r.current_country_id else None,
            current_mileage_km=r.current_mileage_km,
            current_engine_hours=r.current_engine_hours,
            current_ecm_provider_id=UUID(r.current_ecm_provider_id) if r.current_ecm_provider_id else None,
            last_hm1_date=r.last_hm1_date,
            last_hm2_date=r.last_hm2_date,
            last_hm3_date=r.last_hm3_date,
            last_bogie_swap_date=r.last_bogie_swap_date,
            last_vgi_date=r.last_vgi_date,
            notes=r.notes,
            is_active=r.is_active,
            deleted_at=r.deleted_at,
            deleted_by=r.deleted_by,
        )

    def add_meter_reading(self, r: AssetMeterReading) -> AssetMeterReading:
        with self._sf() as session:
            asset = session.get(FleetAssetRow, _s(r.fleet_asset_id))
            if asset is None:
                raise ValueError(f"FleetAsset {r.fleet_asset_id} inconnu")
            session.add(AssetMeterReadingRow(
                meter_reading_id=_s(r.meter_reading_id),
                fleet_asset_id=_s(r.fleet_asset_id),
                reading_date=r.reading_date,
                mileage_km=r.mileage_km,
                engine_hours=r.engine_hours,
                country_iso=r.country_iso,
                source=r.source,
                recorded_by=r.recorded_by,
                recorded_at=r.recorded_at,
                notes=r.notes,
            ))
            # Compteurs monotones croissants : on ne met à jour que si >
            if r.mileage_km >= asset.current_mileage_km:
                asset.current_mileage_km = r.mileage_km
            if r.engine_hours >= asset.current_engine_hours:
                asset.current_engine_hours = r.engine_hours
            if r.country_iso:
                country = self.get_country_by_iso(r.country_iso)
                if country:
                    asset.current_country_id = _s(country.country_id)
            session.commit()
            return r

    def list_meter_readings(self, fleet_asset_id: UUID) -> list[AssetMeterReading]:
        with self._sf() as session:
            rows = session.execute(
                select(AssetMeterReadingRow).where(
                    AssetMeterReadingRow.fleet_asset_id == _s(fleet_asset_id)
                ).order_by(AssetMeterReadingRow.reading_date.desc())
            ).scalars().all()
            return [
                AssetMeterReading(
                    meter_reading_id=UUID(r.meter_reading_id),
                    fleet_asset_id=UUID(r.fleet_asset_id),
                    reading_date=r.reading_date,
                    mileage_km=r.mileage_km,
                    engine_hours=r.engine_hours,
                    country_iso=r.country_iso,
                    source=r.source,
                    recorded_by=r.recorded_by,
                    recorded_at=r.recorded_at,
                    notes=r.notes,
                )
                for r in rows
            ]

    def add_maintenance_history(self, h: AssetMaintenanceHistoryEntry) -> AssetMaintenanceHistoryEntry:
        with self._sf() as session:
            asset = session.get(FleetAssetRow, _s(h.fleet_asset_id))
            if asset is None:
                raise ValueError(f"FleetAsset {h.fleet_asset_id} inconnu")
            session.add(AssetMaintenanceHistoryRow(
                maintenance_history_id=_s(h.maintenance_history_id),
                fleet_asset_id=_s(h.fleet_asset_id),
                operation_id=_s(h.operation_id),
                operation_code=h.operation_code,
                status=h.status.value,
                planned_date=h.planned_date,
                started_at=h.started_at,
                completed_at=h.completed_at,
                workshop_name=h.workshop_name,
                workshop_country_iso=h.workshop_country_iso,
                ecm_provider_id=_s(h.ecm_provider_id) if h.ecm_provider_id else None,
                mileage_km_at_event=h.mileage_km_at_event,
                engine_hours_at_event=h.engine_hours_at_event,
                actual_cost_amount=h.actual_cost_amount,
                billed_amount=h.billed_amount,
                technician_notes=h.technician_notes,
                recorded_by=h.recorded_by,
                recorded_at=h.recorded_at,
            ))
            # Mise à jour des last_X_date
            if h.status.value == "completed" and h.completed_at:
                mapping = {
                    "HM1": "last_hm1_date",
                    "HM2": "last_hm2_date",
                    "HM3": "last_hm3_date",
                    "BOGIE_SWAP": "last_bogie_swap_date",
                    "VGI": "last_vgi_date",
                }
                attr = mapping.get(h.operation_code.upper())
                if attr:
                    setattr(asset, attr, h.completed_at)
            session.commit()
            return h

    def list_maintenance_history(self, fleet_asset_id: UUID) -> list[AssetMaintenanceHistoryEntry]:
        with self._sf() as session:
            rows = session.execute(
                select(AssetMaintenanceHistoryRow).where(
                    AssetMaintenanceHistoryRow.fleet_asset_id == _s(fleet_asset_id)
                )
            ).scalars().all()
            entries = [
                AssetMaintenanceHistoryEntry(
                    maintenance_history_id=UUID(r.maintenance_history_id),
                    fleet_asset_id=UUID(r.fleet_asset_id),
                    operation_id=UUID(r.operation_id),
                    operation_code=r.operation_code,
                    status=MaintenanceEventStatus(r.status),
                    planned_date=r.planned_date,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                    workshop_name=r.workshop_name,
                    workshop_country_iso=r.workshop_country_iso,
                    ecm_provider_id=UUID(r.ecm_provider_id) if r.ecm_provider_id else None,
                    mileage_km_at_event=r.mileage_km_at_event,
                    engine_hours_at_event=r.engine_hours_at_event,
                    actual_cost_amount=r.actual_cost_amount,
                    billed_amount=r.billed_amount,
                    technician_notes=r.technician_notes,
                    recorded_by=r.recorded_by,
                    recorded_at=r.recorded_at,
                )
                for r in rows
            ]
            return sorted(
                entries,
                key=lambda x: x.completed_at or x.planned_date or x.recorded_at.date(),
                reverse=True,
            )

    def compute_fleet_asset_summary(self, fleet_asset_id: UUID) -> FleetAssetSummary | None:
        """Même logique que InMemory ; les lookups font quelques requêtes
        SQL, à grouper si volume devient critique."""
        asset = self.get_fleet_asset(fleet_asset_id)
        if asset is None:
            return None
        variant = self.get_technical_variant(asset.technical_variant_id)
        variant_code = variant.variant_code if variant else "?"

        country_iso = None
        if asset.current_country_id:
            country = self.get_country(asset.current_country_id)
            if country:
                country_iso = country.iso_alpha2

        summary = FleetAssetSummary(
            fleet_asset_id=asset.fleet_asset_id,
            asset_number=asset.asset_number,
            vehicle_registration_number=asset.vehicle_registration_number,
            technical_variant_code=variant_code,
            operational_status=asset.operational_status,
            ownership_status=asset.ownership_status,
            current_mileage_km=asset.current_mileage_km,
            current_engine_hours=asset.current_engine_hours,
            age_years=round(asset.age_years(), 2),
            manufacturing_year=asset.manufacturing_year,
            current_country_iso=country_iso,
        )

        for op in self.list_maintenance_operations():
            code = op.operation_code.upper()
            if code == "HM1" and op.interval_mileage_km:
                base_km = 0
                if asset.last_hm1_date:
                    base_km = max(0, asset.current_mileage_km - op.interval_mileage_km)
                summary.next_hm1_due_km = (base_km // op.interval_mileage_km + 1) * op.interval_mileage_km
            elif code == "HM2" and op.interval_mileage_km:
                summary.next_hm2_due_km = (
                    (asset.current_mileage_km // op.interval_mileage_km) + 1
                ) * op.interval_mileage_km
            elif code == "HM3" and op.interval_mileage_km:
                summary.next_hm3_due_km = (
                    (asset.current_mileage_km // op.interval_mileage_km) + 1
                ) * op.interval_mileage_km
            elif code == "VGI" and op.interval_months:
                from datetime import timedelta
                base_date = asset.last_vgi_date or asset.commissioning_date
                summary.next_vgi_due_date = base_date + timedelta(days=op.interval_months * 30)

        candidates = [v for v in [summary.next_hm1_due_km, summary.next_hm2_due_km, summary.next_hm3_due_km] if v]
        if candidates:
            summary.km_until_next_hm = max(0, min(candidates) - asset.current_mileage_km)

        return summary


def make_catalog_session_factory(database_url: str) -> sessionmaker[Session]:
    """Factory helper. Crée l'engine + la sessionmaker en une ligne.
    Active aussi les FK sur SQLite pour que les CASCADE jouent."""
    from sqlalchemy import create_engine
    from .db import enable_sqlite_foreign_keys
    engine = create_engine(database_url, future=True)
    enable_sqlite_foreign_keys(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
