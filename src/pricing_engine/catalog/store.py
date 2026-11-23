"""Stockage du catalogue — backend pluggable (in-memory + SQL plus tard).

Même pattern que `ReferentielBackend` dans referentiel.py : un Protocol
qui décrit l'API attendue, une implémentation in-memory pour les tests et
le développement rapide, une implémentation SQLAlchemy à ajouter dans un
lot ultérieur quand on migrera PostgreSQL.

Chaque méthode qui modifie l'état respecte l'unicité des codes métier
(code platforme, code série, code variante…) et lève `ValueError` si on
essaie de créer un doublon.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .entities import (
    Country,
    Homologation,
    HomologationCountry,
    LocomotiveSeries,
    Manufacturer,
    ProductFamily,
    ProductPlatform,
    TechnicalVariant,
    VariantHomologation,
)
from .usage import (
    EngineHoursBand,
    MileageBand,
    UsageProfile,
    VariantMileageBand,
    VariantUsageProfile,
)
from .maintenance import (
    EcmProvider,
    MaintenanceOperation,
    MaintenancePlan,
    MaintenancePlanOperation,
    ServiceLevel,
    VariantMaintenancePlan,
)


class CatalogStore(Protocol):
    # Constructeurs
    def upsert_manufacturer(self, m: Manufacturer) -> Manufacturer: ...
    def get_manufacturer(self, manufacturer_id: UUID) -> Manufacturer | None: ...
    def list_manufacturers(self) -> list[Manufacturer]: ...

    # Pays
    def upsert_country(self, c: Country) -> Country: ...
    def get_country(self, country_id: UUID) -> Country | None: ...
    def get_country_by_iso(self, iso: str) -> Country | None: ...
    def list_countries(self) -> list[Country]: ...

    # Familles
    def upsert_product_family(self, f: ProductFamily) -> ProductFamily: ...
    def get_product_family(self, product_family_id: UUID) -> ProductFamily | None: ...
    def list_product_families(self) -> list[ProductFamily]: ...

    # Plateformes
    def upsert_product_platform(self, p: ProductPlatform) -> ProductPlatform: ...
    def get_product_platform(self, product_platform_id: UUID) -> ProductPlatform | None: ...
    def list_product_platforms(self, *, family_id: UUID | None = None) -> list[ProductPlatform]: ...

    # Séries
    def upsert_series(self, s: LocomotiveSeries) -> LocomotiveSeries: ...
    def get_series(self, series_id: UUID) -> LocomotiveSeries | None: ...
    def list_series(self, *, platform_id: UUID | None = None) -> list[LocomotiveSeries]: ...

    # Variantes
    def upsert_technical_variant(self, v: TechnicalVariant) -> TechnicalVariant: ...
    def get_technical_variant(self, technical_variant_id: UUID) -> TechnicalVariant | None: ...
    def get_variant_by_code(self, variant_code: str) -> TechnicalVariant | None: ...
    def list_technical_variants(self, *, series_id: UUID | None = None) -> list[TechnicalVariant]: ...

    # Homologations
    def upsert_homologation(self, h: Homologation) -> Homologation: ...
    def list_homologations(self) -> list[Homologation]: ...

    # Associations M2M
    def set_variant_homologation(self, link: VariantHomologation) -> VariantHomologation: ...
    def list_homologations_for_variant(self, technical_variant_id: UUID) -> list[Homologation]: ...
    def list_variants_for_homologation(self, homologation_id: UUID) -> list[TechnicalVariant]: ...

    def set_homologation_country(self, link: HomologationCountry) -> HomologationCountry: ...
    def list_countries_for_homologation(self, homologation_id: UUID) -> list[Country]: ...


class InMemoryCatalogStore:
    """Implémentation in-memory du CatalogStore.

    Toutes les données vivent dans des dicts Python. Thread-safe au sens
    où CPython garde le GIL, mais pas correct en multi-process. Suffisant
    pour les tests et le mode dev local.
    """

    def __init__(self) -> None:
        self._manufacturers: dict[UUID, Manufacturer] = {}
        self._countries: dict[UUID, Country] = {}
        self._families: dict[UUID, ProductFamily] = {}
        self._platforms: dict[UUID, ProductPlatform] = {}
        self._series: dict[UUID, LocomotiveSeries] = {}
        self._variants: dict[UUID, TechnicalVariant] = {}
        self._homologations: dict[UUID, Homologation] = {}
        self._variant_homologations: dict[tuple[UUID, UUID], VariantHomologation] = {}
        self._homologation_countries: dict[tuple[UUID, UUID], HomologationCountry] = {}

        # Indexes secondaires (codes métier → id) pour faire des get rapides.
        self._manufacturer_by_code: dict[str, UUID] = {}
        self._country_by_iso: dict[str, UUID] = {}
        self._family_by_code: dict[str, UUID] = {}
        self._platform_by_code: dict[str, UUID] = {}
        self._series_by_code: dict[str, UUID] = {}
        self._variant_by_code: dict[str, UUID] = {}
        self._homologation_by_code: dict[str, UUID] = {}

    # ---------------- Constructeurs ----------------

    def upsert_manufacturer(self, m: Manufacturer) -> Manufacturer:
        existing_id = self._manufacturer_by_code.get(m.code.upper())
        if existing_id is not None and existing_id != m.manufacturer_id:
            # Doublon de code sur une autre entité : on réutilise l'ID existant
            m = m.model_copy(update={"manufacturer_id": existing_id})
        self._manufacturers[m.manufacturer_id] = m
        self._manufacturer_by_code[m.code.upper()] = m.manufacturer_id
        return m

    def get_manufacturer(self, manufacturer_id: UUID) -> Manufacturer | None:
        return self._manufacturers.get(manufacturer_id)

    def get_manufacturer_by_code(self, code: str) -> Manufacturer | None:
        mid = self._manufacturer_by_code.get(code.upper())
        return self._manufacturers.get(mid) if mid else None

    def list_manufacturers(self) -> list[Manufacturer]:
        return sorted(self._manufacturers.values(), key=lambda x: x.name)

    # ---------------- Pays ----------------

    def upsert_country(self, c: Country) -> Country:
        iso = c.iso_alpha2.upper()
        existing_id = self._country_by_iso.get(iso)
        if existing_id is not None and existing_id != c.country_id:
            c = c.model_copy(update={"country_id": existing_id, "iso_alpha2": iso})
        else:
            c = c.model_copy(update={"iso_alpha2": iso})
        self._countries[c.country_id] = c
        self._country_by_iso[iso] = c.country_id
        return c

    def get_country(self, country_id: UUID) -> Country | None:
        return self._countries.get(country_id)

    def get_country_by_iso(self, iso: str) -> Country | None:
        cid = self._country_by_iso.get(iso.upper())
        return self._countries.get(cid) if cid else None

    def list_countries(self) -> list[Country]:
        return sorted(self._countries.values(), key=lambda x: x.iso_alpha2)

    # ---------------- Familles ----------------

    def upsert_product_family(self, f: ProductFamily) -> ProductFamily:
        existing_id = self._family_by_code.get(f.family_code.upper())
        if existing_id is not None and existing_id != f.product_family_id:
            f = f.model_copy(update={"product_family_id": existing_id})
        self._families[f.product_family_id] = f
        self._family_by_code[f.family_code.upper()] = f.product_family_id
        return f

    def get_product_family(self, pid: UUID) -> ProductFamily | None:
        return self._families.get(pid)

    def list_product_families(self) -> list[ProductFamily]:
        return sorted(self._families.values(), key=lambda x: x.family_name)

    # ---------------- Plateformes ----------------

    def upsert_product_platform(self, p: ProductPlatform) -> ProductPlatform:
        if p.product_family_id not in self._families:
            raise ValueError(f"ProductFamily {p.product_family_id} inconnue")
        if p.manufacturer_id not in self._manufacturers:
            raise ValueError(f"Manufacturer {p.manufacturer_id} inconnu")
        existing_id = self._platform_by_code.get(p.platform_code.upper())
        if existing_id is not None and existing_id != p.product_platform_id:
            p = p.model_copy(update={"product_platform_id": existing_id})
        self._platforms[p.product_platform_id] = p
        self._platform_by_code[p.platform_code.upper()] = p.product_platform_id
        return p

    def get_product_platform(self, pid: UUID) -> ProductPlatform | None:
        return self._platforms.get(pid)

    def list_product_platforms(self, *, family_id: UUID | None = None) -> list[ProductPlatform]:
        items = self._platforms.values()
        if family_id is not None:
            items = [p for p in items if p.product_family_id == family_id]
        return sorted(items, key=lambda x: x.platform_code)

    # ---------------- Séries ----------------

    def upsert_series(self, s: LocomotiveSeries) -> LocomotiveSeries:
        if s.product_platform_id not in self._platforms:
            raise ValueError(f"ProductPlatform {s.product_platform_id} inconnue")
        existing_id = self._series_by_code.get(s.series_code.upper())
        if existing_id is not None and existing_id != s.series_id:
            s = s.model_copy(update={"series_id": existing_id})
        self._series[s.series_id] = s
        self._series_by_code[s.series_code.upper()] = s.series_id
        return s

    def get_series(self, sid: UUID) -> LocomotiveSeries | None:
        return self._series.get(sid)

    def get_series_by_code(self, code: str) -> LocomotiveSeries | None:
        sid = self._series_by_code.get(code.upper())
        return self._series.get(sid) if sid else None

    def list_series(self, *, platform_id: UUID | None = None) -> list[LocomotiveSeries]:
        items = self._series.values()
        if platform_id is not None:
            items = [s for s in items if s.product_platform_id == platform_id]
        return sorted(items, key=lambda x: x.series_code)

    # ---------------- Variantes ----------------

    def upsert_technical_variant(self, v: TechnicalVariant) -> TechnicalVariant:
        if v.series_id not in self._series:
            raise ValueError(f"Series {v.series_id} inconnue")
        existing_id = self._variant_by_code.get(v.variant_code.upper())
        if existing_id is not None and existing_id != v.technical_variant_id:
            v = v.model_copy(update={"technical_variant_id": existing_id})
        self._variants[v.technical_variant_id] = v
        self._variant_by_code[v.variant_code.upper()] = v.technical_variant_id
        return v

    def get_technical_variant(self, vid: UUID) -> TechnicalVariant | None:
        return self._variants.get(vid)

    def get_variant_by_code(self, code: str) -> TechnicalVariant | None:
        vid = self._variant_by_code.get(code.upper())
        return self._variants.get(vid) if vid else None

    def list_technical_variants(self, *, series_id: UUID | None = None) -> list[TechnicalVariant]:
        items = self._variants.values()
        if series_id is not None:
            items = [v for v in items if v.series_id == series_id]
        return sorted(items, key=lambda x: x.variant_code)

    # ---------------- Homologations ----------------

    def upsert_homologation(self, h: Homologation) -> Homologation:
        existing_id = self._homologation_by_code.get(h.homologation_code.upper())
        if existing_id is not None and existing_id != h.homologation_id:
            h = h.model_copy(update={"homologation_id": existing_id})
        self._homologations[h.homologation_id] = h
        self._homologation_by_code[h.homologation_code.upper()] = h.homologation_id
        return h

    def get_homologation(self, hid: UUID) -> Homologation | None:
        return self._homologations.get(hid)

    def get_homologation_by_code(self, code: str) -> Homologation | None:
        hid = self._homologation_by_code.get(code.upper())
        return self._homologations.get(hid) if hid else None

    def list_homologations(self) -> list[Homologation]:
        return sorted(self._homologations.values(), key=lambda x: x.homologation_code)

    # ---------------- Associations M2M ----------------

    def set_variant_homologation(self, link: VariantHomologation) -> VariantHomologation:
        if link.technical_variant_id not in self._variants:
            raise ValueError(f"Variant {link.technical_variant_id} inconnue")
        if link.homologation_id not in self._homologations:
            raise ValueError(f"Homologation {link.homologation_id} inconnue")
        self._variant_homologations[(link.technical_variant_id, link.homologation_id)] = link
        return link

    def remove_variant_homologation(self, variant_id: UUID, homologation_id: UUID) -> bool:
        return self._variant_homologations.pop((variant_id, homologation_id), None) is not None

    def list_homologations_for_variant(self, technical_variant_id: UUID) -> list[Homologation]:
        ids = [h_id for (v_id, h_id) in self._variant_homologations if v_id == technical_variant_id]
        return [self._homologations[hid] for hid in ids if hid in self._homologations]

    def list_variants_for_homologation(self, homologation_id: UUID) -> list[TechnicalVariant]:
        ids = [v_id for (v_id, h_id) in self._variant_homologations if h_id == homologation_id]
        return [self._variants[vid] for vid in ids if vid in self._variants]

    def set_homologation_country(self, link: HomologationCountry) -> HomologationCountry:
        if link.homologation_id not in self._homologations:
            raise ValueError(f"Homologation {link.homologation_id} inconnue")
        if link.country_id not in self._countries:
            raise ValueError(f"Country {link.country_id} inconnu")
        self._homologation_countries[(link.homologation_id, link.country_id)] = link
        return link

    def list_countries_for_homologation(self, homologation_id: UUID) -> list[Country]:
        ids = [c_id for (h_id, c_id) in self._homologation_countries if h_id == homologation_id]
        return [self._countries[cid] for cid in ids if cid in self._countries]

    def list_variant_homologation_links(self) -> list[VariantHomologation]:
        return list(self._variant_homologations.values())

    def list_homologation_country_links(self) -> list[HomologationCountry]:
        return list(self._homologation_countries.values())

    # =========================================================================
    # Lot 2 : Usage & Maintenance
    # =========================================================================

    def __post_init_lot2__(self):
        """Initialise les collections Lot 2. Appelé paresseusement via
        _ensure_lot2()."""
        self._usage_profiles: dict[UUID, UsageProfile] = {}
        self._mileage_bands: dict[UUID, MileageBand] = {}
        self._engine_hours_bands: dict[UUID, EngineHoursBand] = {}
        self._maintenance_operations: dict[UUID, MaintenanceOperation] = {}
        self._maintenance_plans: dict[UUID, MaintenancePlan] = {}
        self._ecm_providers: dict[UUID, EcmProvider] = {}
        self._service_levels: dict[UUID, ServiceLevel] = {}
        self._variant_usage_profiles: dict[tuple[UUID, UUID], VariantUsageProfile] = {}
        self._variant_mileage_bands: dict[tuple[UUID, UUID], VariantMileageBand] = {}
        self._variant_maintenance_plans: dict[tuple[UUID, UUID], VariantMaintenancePlan] = {}
        self._plan_operations: dict[tuple[UUID, UUID], MaintenancePlanOperation] = {}
        self._usage_profile_by_code: dict[str, UUID] = {}
        self._mileage_band_by_code: dict[str, UUID] = {}
        self._engine_hours_band_by_code: dict[str, UUID] = {}
        self._operation_by_code: dict[str, UUID] = {}
        self._plan_by_code: dict[str, UUID] = {}
        self._ecm_provider_by_code: dict[str, UUID] = {}
        self._service_level_by_code: dict[str, UUID] = {}

    def _ensure_lot2(self):
        if not hasattr(self, "_usage_profiles"):
            self.__post_init_lot2__()

    # ------- Usage Profiles -------

    def upsert_usage_profile(self, u: UsageProfile) -> UsageProfile:
        self._ensure_lot2()
        existing_id = self._usage_profile_by_code.get(u.usage_profile_code.upper())
        if existing_id and existing_id != u.usage_profile_id:
            u = u.model_copy(update={"usage_profile_id": existing_id})
        self._usage_profiles[u.usage_profile_id] = u
        self._usage_profile_by_code[u.usage_profile_code.upper()] = u.usage_profile_id
        return u

    def list_usage_profiles(self) -> list[UsageProfile]:
        self._ensure_lot2()
        return sorted(self._usage_profiles.values(),
                      key=lambda x: x.annual_mileage_min_km or 0)

    def get_usage_profile(self, uid: UUID) -> UsageProfile | None:
        self._ensure_lot2()
        return self._usage_profiles.get(uid)

    def get_usage_profile_by_code(self, code: str) -> UsageProfile | None:
        self._ensure_lot2()
        uid = self._usage_profile_by_code.get(code.upper())
        return self._usage_profiles.get(uid) if uid else None

    # ------- Mileage Bands -------

    def upsert_mileage_band(self, b: MileageBand) -> MileageBand:
        self._ensure_lot2()
        existing_id = self._mileage_band_by_code.get(b.band_code.upper())
        if existing_id and existing_id != b.mileage_band_id:
            b = b.model_copy(update={"mileage_band_id": existing_id})
        self._mileage_bands[b.mileage_band_id] = b
        self._mileage_band_by_code[b.band_code.upper()] = b.mileage_band_id
        return b

    def list_mileage_bands(self) -> list[MileageBand]:
        self._ensure_lot2()
        return sorted(self._mileage_bands.values(), key=lambda x: x.min_annual_mileage_km)

    def get_mileage_band_for_annual_km(self, annual_km: int) -> MileageBand | None:
        self._ensure_lot2()
        for band in self.list_mileage_bands():
            if band.contient(annual_km):
                return band
        return None

    # ------- Engine Hours Bands -------

    def upsert_engine_hours_band(self, b: EngineHoursBand) -> EngineHoursBand:
        self._ensure_lot2()
        existing_id = self._engine_hours_band_by_code.get(b.band_code.upper())
        if existing_id and existing_id != b.engine_hours_band_id:
            b = b.model_copy(update={"engine_hours_band_id": existing_id})
        self._engine_hours_bands[b.engine_hours_band_id] = b
        self._engine_hours_band_by_code[b.band_code.upper()] = b.engine_hours_band_id
        return b

    def list_engine_hours_bands(self) -> list[EngineHoursBand]:
        self._ensure_lot2()
        return sorted(self._engine_hours_bands.values(), key=lambda x: x.min_annual_engine_hours)

    # ------- Maintenance Operations -------

    def upsert_maintenance_operation(self, o: MaintenanceOperation) -> MaintenanceOperation:
        self._ensure_lot2()
        existing_id = self._operation_by_code.get(o.operation_code.upper())
        if existing_id and existing_id != o.operation_id:
            o = o.model_copy(update={"operation_id": existing_id})
        self._maintenance_operations[o.operation_id] = o
        self._operation_by_code[o.operation_code.upper()] = o.operation_id
        return o

    def list_maintenance_operations(self) -> list[MaintenanceOperation]:
        self._ensure_lot2()
        return sorted(self._maintenance_operations.values(),
                      key=lambda x: x.operation_code)

    # ------- Maintenance Plans -------

    def upsert_maintenance_plan(self, p: MaintenancePlan) -> MaintenancePlan:
        self._ensure_lot2()
        existing_id = self._plan_by_code.get(p.plan_code.upper())
        if existing_id and existing_id != p.maintenance_plan_id:
            p = p.model_copy(update={"maintenance_plan_id": existing_id})
        self._maintenance_plans[p.maintenance_plan_id] = p
        self._plan_by_code[p.plan_code.upper()] = p.maintenance_plan_id
        return p

    def list_maintenance_plans(self) -> list[MaintenancePlan]:
        self._ensure_lot2()
        return sorted(self._maintenance_plans.values(), key=lambda x: x.plan_code)

    def add_plan_operation(self, link: MaintenancePlanOperation) -> MaintenancePlanOperation:
        self._ensure_lot2()
        if link.maintenance_plan_id not in self._maintenance_plans:
            raise ValueError(f"MaintenancePlan {link.maintenance_plan_id} inconnu")
        if link.operation_id not in self._maintenance_operations:
            raise ValueError(f"MaintenanceOperation {link.operation_id} inconnue")
        self._plan_operations[(link.maintenance_plan_id, link.operation_id)] = link
        return link

    def list_operations_for_plan(self, plan_id: UUID) -> list[MaintenanceOperation]:
        self._ensure_lot2()
        op_ids = [op_id for (p_id, op_id) in self._plan_operations if p_id == plan_id]
        return [self._maintenance_operations[o] for o in op_ids if o in self._maintenance_operations]

    # ------- ECM Providers -------

    def upsert_ecm_provider(self, e: EcmProvider) -> EcmProvider:
        self._ensure_lot2()
        existing_id = self._ecm_provider_by_code.get(e.provider_code.upper())
        if existing_id and existing_id != e.ecm_provider_id:
            e = e.model_copy(update={"ecm_provider_id": existing_id})
        self._ecm_providers[e.ecm_provider_id] = e
        self._ecm_provider_by_code[e.provider_code.upper()] = e.ecm_provider_id
        return e

    def list_ecm_providers(self) -> list[EcmProvider]:
        self._ensure_lot2()
        return sorted(self._ecm_providers.values(), key=lambda x: x.provider_code)

    # ------- Service Levels -------

    def upsert_service_level(self, s: ServiceLevel) -> ServiceLevel:
        self._ensure_lot2()
        existing_id = self._service_level_by_code.get(s.service_level_code.value.upper())
        if existing_id and existing_id != s.service_level_id:
            s = s.model_copy(update={"service_level_id": existing_id})
        self._service_levels[s.service_level_id] = s
        self._service_level_by_code[s.service_level_code.value.upper()] = s.service_level_id
        return s

    def list_service_levels(self) -> list[ServiceLevel]:
        self._ensure_lot2()
        return sorted(self._service_levels.values(),
                      key=lambda x: x.service_level_code.value)

    # ------- Associations variantes ↔ (usage, mileage, maintenance) -------

    def set_variant_usage_profile(self, link: VariantUsageProfile) -> VariantUsageProfile:
        self._ensure_lot2()
        if link.technical_variant_id not in self._variants:
            raise ValueError(f"Variant {link.technical_variant_id} inconnue")
        if link.usage_profile_id not in self._usage_profiles:
            raise ValueError(f"UsageProfile {link.usage_profile_id} inconnu")
        self._variant_usage_profiles[(link.technical_variant_id, link.usage_profile_id)] = link
        return link

    def list_usage_profiles_for_variant(self, variant_id: UUID) -> list[tuple[UsageProfile, VariantUsageProfile]]:
        self._ensure_lot2()
        return [
            (self._usage_profiles[u_id], self._variant_usage_profiles[(v_id, u_id)])
            for (v_id, u_id) in self._variant_usage_profiles
            if v_id == variant_id and u_id in self._usage_profiles
        ]

    def set_variant_mileage_band(self, link: VariantMileageBand) -> VariantMileageBand:
        self._ensure_lot2()
        if link.technical_variant_id not in self._variants:
            raise ValueError(f"Variant {link.technical_variant_id} inconnue")
        if link.mileage_band_id not in self._mileage_bands:
            raise ValueError(f"MileageBand {link.mileage_band_id} inconnu")
        self._variant_mileage_bands[(link.technical_variant_id, link.mileage_band_id)] = link
        return link

    def list_mileage_bands_for_variant(self, variant_id: UUID) -> list[MileageBand]:
        self._ensure_lot2()
        return [
            self._mileage_bands[b_id]
            for (v_id, b_id) in self._variant_mileage_bands
            if v_id == variant_id and b_id in self._mileage_bands
        ]

    def set_variant_maintenance_plan(self, link: VariantMaintenancePlan) -> VariantMaintenancePlan:
        self._ensure_lot2()
        if link.technical_variant_id not in self._variants:
            raise ValueError(f"Variant {link.technical_variant_id} inconnue")
        if link.maintenance_plan_id not in self._maintenance_plans:
            raise ValueError(f"MaintenancePlan {link.maintenance_plan_id} inconnu")
        self._variant_maintenance_plans[(link.technical_variant_id, link.maintenance_plan_id)] = link
        return link

    def list_maintenance_plans_for_variant(self, variant_id: UUID) -> list[MaintenancePlan]:
        self._ensure_lot2()
        return [
            self._maintenance_plans[p_id]
            for (v_id, p_id) in self._variant_maintenance_plans
            if v_id == variant_id and p_id in self._maintenance_plans
        ]
