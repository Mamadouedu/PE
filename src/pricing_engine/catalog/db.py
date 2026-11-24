"""Tables SQLAlchemy du catalog PricingHub (Lots 1→5).

Pattern identique à `src/pricing_engine/db.py` du Lot 1 original :
mapping SQLAlchemy 2.0 avec `DeclarativeBase` + `Mapped[]` + `mapped_column()`.
Les Pydantic models restent pour l'API (validation en entrée/sortie), les
rows SQLA servent uniquement à la persistance.

Les clés étrangères utilisent `ON DELETE RESTRICT` par défaut pour éviter
les suppressions en cascade qui perdraient l'historique. `PriceBookVersion`
→ `DryLeaseRate` est l'exception : `ON DELETE CASCADE` parce qu'une version
supprimée doit emporter ses lignes.

Les JSON columns (configuration gelée, warnings, détails OM) utilisent
`JSON` neutre : PostgreSQL le stocke en jsonb, SQLite en TEXT.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base déclarative dédiée au catalog (séparée de l'ancienne Base du
    Lot 1 pour que l'autogenerate Alembic ne les mélange pas par erreur)."""


# =========================================================================
# Lot 1 : Référentiel locomotive
# =========================================================================


class ManufacturerRow(Base):
    __tablename__ = "catalog_manufacturers"
    manufacturer_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_of_origin_iso: Mapped[str] = mapped_column(String(2), nullable=False)
    parent_company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    statut: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CountryRow(Base):
    __tablename__ = "catalog_countries"
    country_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    iso_alpha2: Mapped[str] = mapped_column(String(2), nullable=False, unique=True, index=True)
    name_fr: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    default_network_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_eu_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductFamilyRow(Base):
    __tablename__ = "catalog_product_families"
    product_family_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    family_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductPlatformRow(Base):
    __tablename__ = "catalog_product_platforms"
    product_platform_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_family_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_product_families.product_family_id"), nullable=False, index=True
    )
    platform_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    platform_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_manufacturers.manufacturer_id"), nullable=False, index=True
    )
    traction_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LocomotiveSeriesRow(Base):
    __tablename__ = "catalog_locomotive_series"
    series_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_product_platforms.product_platform_id"), nullable=False, index=True
    )
    series_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    series_name: Mapped[str] = mapped_column(String(200), nullable=False)
    nominal_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_speed_kmh: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starting_tractive_effort_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    traction_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    production_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    production_end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TechnicalVariantRow(Base):
    __tablename__ = "catalog_technical_variants"
    technical_variant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_locomotive_series.series_id"), nullable=False, index=True
    )
    variant_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    variant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer_model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    technical_configuration_code: Mapped[str] = mapped_column(String(200), nullable=False)
    traction_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nominal_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_speed_kmh: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starting_tractive_effort_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    manufacturing_year_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manufacturing_year_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_ecm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HomologationRow(Base):
    __tablename__ = "catalog_homologations"
    homologation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    homologation_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    homologation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="approved")


class VariantHomologationRow(Base):
    __tablename__ = "catalog_variant_homologations"
    technical_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_technical_variants.technical_variant_id"), primary_key=True
    )
    homologation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_homologations.homologation_id"), primary_key=True
    )
    is_standard: Mapped[bool] = mapped_column(Boolean, default=True)
    additional_cost: Mapped[float] = mapped_column(Float, default=0)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class HomologationCountryRow(Base):
    __tablename__ = "catalog_homologation_countries"
    homologation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_homologations.homologation_id"), primary_key=True
    )
    country_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_countries.country_id"), primary_key=True
    )
    network_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


# =========================================================================
# Lot 2 : Usage & maintenance
# =========================================================================


class UsageProfileRow(Base):
    __tablename__ = "catalog_usage_profiles"
    usage_profile_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usage_profile_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    usage_profile_name: Mapped[str] = mapped_column(String(200), nullable=False)
    annual_mileage_min_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_mileage_max_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_engine_hours_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_engine_hours_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_mileage_min_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_mileage_max_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    utilisation_type: Mapped[str] = mapped_column(String(20), default="freight")
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MileageBandRow(Base):
    __tablename__ = "catalog_mileage_bands"
    mileage_band_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    band_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    band_name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_annual_mileage_km: Mapped[int] = mapped_column(Integer, nullable=False)
    max_annual_mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculation_method: Mapped[str] = mapped_column(String(20), default="linear")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_mileage_bands_range", "min_annual_mileage_km", "max_annual_mileage_km"),
    )


class EngineHoursBandRow(Base):
    __tablename__ = "catalog_engine_hours_bands"
    engine_hours_band_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    band_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    band_name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_annual_engine_hours: Mapped[float] = mapped_column(Float, nullable=False)
    max_annual_engine_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MaintenanceOperationRow(Base):
    __tablename__ = "catalog_maintenance_operations"
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    operation_name: Mapped[str] = mapped_column(String(200), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(20), default="HM")
    trigger_type: Mapped[str] = mapped_column(String(20), default="mileage")
    interval_mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_engine_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    standard_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MaintenancePlanRow(Base):
    __tablename__ = "catalog_maintenance_plans"
    maintenance_plan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    plan_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("catalog_manufacturers.manufacturer_id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), default="")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MaintenancePlanOperationRow(Base):
    __tablename__ = "catalog_maintenance_plan_operations"
    maintenance_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_maintenance_plans.maintenance_plan_id"), primary_key=True
    )
    operation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_maintenance_operations.operation_id"), primary_key=True
    )
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency_multiplier: Mapped[float] = mapped_column(Float, default=1.0)


class EcmProviderRow(Base):
    __tablename__ = "catalog_ecm_providers"
    ecm_provider_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    certification_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certification_valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    certification_valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ServiceLevelRow(Base):
    __tablename__ = "catalog_service_levels"
    service_level_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_level_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    service_level_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hotline_included: Mapped[bool] = mapped_column(Boolean, default=False)
    hotline_coverage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_time_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class VariantUsageProfileRow(Base):
    __tablename__ = "catalog_variant_usage_profiles"
    technical_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_technical_variants.technical_variant_id"), primary_key=True
    )
    usage_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_usage_profiles.usage_profile_id"), primary_key=True
    )
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_threshold_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_contractual_mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_specific_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class VariantMileageBandRow(Base):
    __tablename__ = "catalog_variant_mileage_bands"
    technical_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_technical_variants.technical_variant_id"), primary_key=True
    )
    mileage_band_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_mileage_bands.mileage_band_id"), primary_key=True
    )
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class VariantMaintenancePlanRow(Base):
    __tablename__ = "catalog_variant_maintenance_plans"
    technical_variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_technical_variants.technical_variant_id"), primary_key=True
    )
    maintenance_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_maintenance_plans.maintenance_plan_id"), primary_key=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


# =========================================================================
# Lot 3 : Tarifs versionnés
# =========================================================================


class LeaseBandRow(Base):
    __tablename__ = "catalog_lease_bands"
    lease_band_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    band_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    band_name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    max_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AssetAgeBandRow(Base):
    __tablename__ = "catalog_asset_age_bands"
    asset_age_band_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    band_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    band_name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_age_years: Mapped[float] = mapped_column(Float, nullable=False)
    max_age_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CountryGroupRow(Base):
    __tablename__ = "catalog_country_groups"
    country_group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_iso_codes: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommercialOptionRow(Base):
    __tablename__ = "catalog_commercial_options"
    commercial_option_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    option_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    option_name: Mapped[str] = mapped_column(String(200), nullable=False)
    option_type: Mapped[str] = mapped_column(String(32), default="service")
    default_billing_unit: Mapped[str] = mapped_column(String(32), default="monthly")
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PriceBookRow(Base):
    __tablename__ = "catalog_price_books"
    price_book_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_book_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    price_book_name: Mapped[str] = mapped_column(String(200), nullable=False)
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PriceBookVersionRow(Base):
    __tablename__ = "catalog_price_book_versions"
    price_book_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_book_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("catalog_price_books.price_book_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")

    __table_args__ = (
        UniqueConstraint("price_book_id", "year", "version_number", name="ux_pbv_pb_year_version"),
        Index("ix_pbv_active", "price_book_id", "status", "valid_from"),
    )


class DryLeaseRateRow(Base):
    __tablename__ = "catalog_dry_lease_rates"
    dry_lease_rate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_book_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("catalog_price_book_versions.price_book_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    technical_variant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_group_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lease_band_id: Mapped[str] = mapped_column(String(36), nullable=False)
    asset_age_band_id: Mapped[str] = mapped_column(String(36), nullable=False)
    monthly_base_rent: Mapped[float] = mapped_column(Float, nullable=False)
    insurance_amount: Mapped[float] = mapped_column(Float, default=0)
    risk_provision_amount: Mapped[float] = mapped_column(Float, default=0)
    specific_commitment_rate: Mapped[float] = mapped_column(Float, default=0)
    minimum_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        # Index composite critique pour la résolution du moteur v2
        Index(
            "ix_dl_lookup",
            "price_book_version_id",
            "technical_variant_id",
            "country_group_id",
            "lease_band_id",
            "asset_age_band_id",
            unique=True,
        ),
        CheckConstraint("monthly_base_rent > 0", name="ck_dl_rent_positive"),
    )


class HeavyMaintenanceRateRow(Base):
    __tablename__ = "catalog_heavy_maintenance_rates"
    heavy_maintenance_rate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_book_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("catalog_price_book_versions.price_book_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    technical_variant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workshop_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    calculation_method: Mapped[str] = mapped_column(String(32), default="fixed")
    cost_amount: Mapped[float] = mapped_column(Float, nullable=False)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    billing_unit: Mapped[str] = mapped_column(String(32), default="per_operation")
    monthly_provision_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index("ix_hm_lookup", "price_book_version_id", "technical_variant_id", "operation_id"),
    )


class OperatingMaintenanceRateRow(Base):
    __tablename__ = "catalog_operating_maintenance_rates"
    operating_maintenance_rate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    price_book_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("catalog_price_book_versions.price_book_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    technical_variant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mileage_band_id: Mapped[str] = mapped_column(String(36), nullable=False)
    engine_hours_band_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ecm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    service_level_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    monthly_fixed_amount: Mapped[float] = mapped_column(Float, default=0)
    price_per_kilometer: Mapped[float] = mapped_column(Float, default=0)
    price_per_engine_hour: Mapped[float] = mapped_column(Float, default=0)
    ecm_monthly_amount: Mapped[float] = mapped_column(Float, default=0)
    last_mile_monthly_amount: Mapped[float] = mapped_column(Float, default=0)
    minimum_monthly_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_annual_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index(
            "ix_om_lookup",
            "price_book_version_id",
            "technical_variant_id",
            "mileage_band_id",
        ),
    )


# =========================================================================
# Lot 4 : Quote refondu
# =========================================================================


class QuoteRow(Base):
    __tablename__ = "quotes"
    quote_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    client_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency_iso: Mapped[str] = mapped_column(String(3), default="EUR")
    total_mensuel: Mapped[float] = mapped_column(Float, default=0)
    total_contrat: Mapped[float] = mapped_column(Float, default=0)
    niveau_validation: Mapped[int] = mapped_column(Integer, default=0)
    pipedrive_deal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class QuoteLineRow(Base):
    __tablename__ = "quote_lines"
    quote_line_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.quote_id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_variant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    technical_variant_code: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    contract_duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_mileage_km: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_engine_hours: Mapped[float] = mapped_column(Float, default=0)
    monthly_mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    country_iso: Mapped[str] = mapped_column(String(2), nullable=False)
    homologation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_ecm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_service_level_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    fleet_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str] = mapped_column(String(2000), default="")


class PricingCalculationRow(Base):
    __tablename__ = "pricing_calculations"
    pricing_calculation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    quote_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quote_lines.quote_line_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dl_price_book_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    hm_price_book_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    om_price_book_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dl_version_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hm_version_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    om_version_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dl_monthly: Mapped[float] = mapped_column(Float, default=0)
    hm_monthly_provisioned: Mapped[float] = mapped_column(Float, default=0)
    om_monthly: Mapped[float] = mapped_column(Float, default=0)
    options_monthly: Mapped[float] = mapped_column(Float, default=0)
    total_monthly: Mapped[float] = mapped_column(Float, default=0)
    total_contract: Mapped[float] = mapped_column(Float, default=0)
    floor_applied: Mapped[float] = mapped_column(Float, default=0)
    cap_applied: Mapped[float] = mapped_column(Float, default=0)
    is_under_floor: Mapped[bool] = mapped_column(Boolean, default=False)
    niveau_validation: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)


class PricingCalculationComponentRow(Base):
    """Composant élémentaire du calcul : DL base, OM mileage, HM HM1, etc.
    Permet l'explicabilité M2-05 et le reporting par brique sans
    recalcul."""
    __tablename__ = "pricing_calculation_components"
    component_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pricing_calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pricing_calculations.pricing_calculation_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    monthly_amount: Mapped[float] = mapped_column(Float, default=0)
    annual_amount: Mapped[float] = mapped_column(Float, default=0)
    is_visible_to_client: Mapped[bool] = mapped_column(Boolean, default=True)


class AppliedPricingRuleRow(Base):
    """Trace des règles métier appliquées (remise, campagne, dérogation)
    avec qui a validé et quand."""
    __tablename__ = "applied_pricing_rules"
    applied_rule_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pricing_calculation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pricing_calculations.pricing_calculation_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    rule_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_description: Mapped[str] = mapped_column(String(500), default="")
    impact_percentage: Mapped[float] = mapped_column(Float, default=0)
    impact_monthly_amount: Mapped[float] = mapped_column(Float, default=0)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)


class QuoteLineOptionRow(Base):
    __tablename__ = "quote_line_options"
    quote_line_option_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    quote_line_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quote_lines.quote_line_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    commercial_option_id: Mapped[str] = mapped_column(String(36), nullable=False)
    option_code: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    billing_unit: Mapped[str] = mapped_column(String(32), default="monthly")
    total_monthly_impact: Mapped[float] = mapped_column(Float, default=0)
    is_included: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLogRow(Base):
    """Audit trail universel : qui a fait quoi, quand, sur quelle entité.
    Alimenté par `log_audit()` appelé à chaque mutation sensible.
    Permet la compliance (traçabilité) et le forensic en cas d'incident."""
    __tablename__ = "audit_log"
    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
        doc="CREATE, UPDATE, DELETE, SUBMIT, DECIDE, LOGIN...")
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
        doc="Quote, QuoteLine, FleetAsset, Utilisateur...")
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict,
        doc="Payload libre : before/after, raison, IP, user-agent...")
    http_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        Index("ix_audit_occurred", "occurred_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )


# =========================================================================
# Lot 5 : Flotte réelle
# =========================================================================


class FleetAssetRow(Base):
    __tablename__ = "fleet_assets"
    fleet_asset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    vehicle_registration_number: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    technical_variant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    manufacturing_year: Mapped[int] = mapped_column(Integer, nullable=False)
    commissioning_date: Mapped[date] = mapped_column(Date, nullable=False)
    ownership_status: Mapped[str] = mapped_column(String(20), default="owned")
    operational_status: Mapped[str] = mapped_column(String(20), default="available", index=True)
    current_country_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_mileage_km: Mapped[float] = mapped_column(Float, default=0)
    current_engine_hours: Mapped[float] = mapped_column(Float, default=0)
    current_ecm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_hm1_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_hm2_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_hm3_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_bogie_swap_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_vgi_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String(2000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AssetMeterReadingRow(Base):
    __tablename__ = "fleet_meter_readings"
    meter_reading_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fleet_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fleet_assets.fleet_asset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    reading_date: Mapped[date] = mapped_column(Date, nullable=False)
    mileage_km: Mapped[float] = mapped_column(Float, nullable=False)
    engine_hours: Mapped[float] = mapped_column(Float, default=0)
    country_iso: Mapped[str | None] = mapped_column(String(2), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="telemetry")
    recorded_by: Mapped[str] = mapped_column(String(255), default="system")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="")


class AssetMaintenanceHistoryRow(Base):
    __tablename__ = "fleet_maintenance_history"
    maintenance_history_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fleet_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fleet_assets.fleet_asset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    workshop_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    workshop_country_iso: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ecm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mileage_km_at_event: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_hours_at_event: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    billed_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    technician_notes: Mapped[str] = mapped_column(String(2000), default="")
    recorded_by: Mapped[str] = mapped_column(String(255), default="system")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def enable_sqlite_foreign_keys(engine) -> None:
    """Active PRAGMA foreign_keys sur toute connexion SQLite de cet engine.

    SQLite ne vérifie pas les FK par défaut, donc les CASCADE ne
    s'appliquent pas et des orphelins peuvent persister. Pas de no-op
    en PostgreSQL : le listener filtre par dialect.
    """
    from sqlalchemy import event

    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _fk_pragma_on_connect(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_all_catalog_tables(engine) -> None:
    """Helper pour créer toutes les tables du catalog en une fois.

    En prod on utilise Alembic ; ce helper sert aux tests qui veulent une
    base propre sans passer par la CLI. Active aussi les FK SQLite."""
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
