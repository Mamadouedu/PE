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


def make_catalog_session_factory(database_url: str) -> sessionmaker[Session]:
    """Factory helper. Crée l'engine + la sessionmaker en une ligne."""
    from sqlalchemy import create_engine
    engine = create_engine(database_url, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
