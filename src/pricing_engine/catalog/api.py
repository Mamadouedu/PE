"""API REST du catalogue PricingHub (Lot 1).

Routeur FastAPI monté sous `/api/v1/catalog/*`. Hiérarchie complète du
référentiel locomotive : constructeurs, pays, familles, plateformes,
séries, variantes, homologations.

Toutes les routes GET sont publiques (lecture = pas d'auth stricte).
Toutes les routes POST/PUT/DELETE exigent la permission `admin_referentiel`
quand REQUIRE_AUTH est activé.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

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
from .maintenance import (
    EcmProvider,
    MaintenanceOperation,
    MaintenancePlan,
    ServiceLevel,
)
from .pricing import (
    AssetAgeBand,
    CommercialOption,
    CountryGroup,
    DryLeaseRate,
    HeavyMaintenanceRate,
    LeaseBand,
    OperatingMaintenanceRate,
    PriceBook,
    PriceBookVersion,
)
from .pricing_engine_v2 import DemandeChiffrage, MoteurPrixV2
from .quote import (
    AppliedPricingRule,
    PricingCalculation,
    PricingCalculationComponent,
    Quote,
    QuoteLine,
    QuoteLineOption,
    QuoteStatus,
)
from .quote_store import InMemoryQuoteStore, QuoteService, QuoteStore
from .fleet import (
    AssetMaintenanceHistoryEntry,
    AssetMeterReading,
    FleetAsset,
    OperationalStatus,
    OwnershipStatus,
)
from .store import CatalogStore, InMemoryCatalogStore
from .usage import (
    EngineHoursBand,
    MileageBand,
    UsageProfile,
)
from pydantic import BaseModel


class ChiffrageRequest(BaseModel):
    """Payload d'entrée du moteur de prix v2."""
    technical_variant_code: str
    country_iso: str
    duration_months: int
    age_years: float
    annual_mileage_km: int
    annual_engine_hours: float = 0
    ecm_provider_code: str | None = None
    service_level_code: str | None = None
    options_monthly: float = 0


class CreateQuoteRequest(BaseModel):
    client_code: str
    client_name: str


class AddQuoteLineRequest(BaseModel):
    technical_variant_code: str
    country_iso: str
    duration_months: int
    age_years: float
    annual_mileage_km: int
    annual_engine_hours: float = 0
    quantity: int = 1
    ecm_provider_code: str | None = None
    service_level_code: str | None = None


class DecisionQuoteRequest(BaseModel):
    approved: bool
    comment: str = ""


def build_catalog_router(
    get_store: Callable[[], CatalogStore],
    exiger_permission: Callable[[str], Callable],
    get_quote_store: Callable[[], QuoteStore] | None = None,
    get_current_user: Callable | None = None,
) -> APIRouter:
    """Construit le router. Les dépendances `get_store` et `exiger_permission`
    sont injectées par `api.py` qui est le propriétaire des instances
    globales. `get_quote_store` et `get_current_user` activent les endpoints
    Quote du Lot 4."""

    router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])
    require_admin = exiger_permission("admin_referentiel")

    # =========================================================================
    # Constructeurs
    # =========================================================================

    @router.get("/manufacturers", response_model=list[Manufacturer])
    def list_manufacturers(store: CatalogStore = Depends(get_store)):
        return store.list_manufacturers()

    @router.post("/manufacturers", response_model=Manufacturer)
    def upsert_manufacturer(
        payload: Manufacturer,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        return store.upsert_manufacturer(payload)

    @router.get("/manufacturers/{manufacturer_id}", response_model=Manufacturer)
    def get_manufacturer(manufacturer_id: UUID, store: CatalogStore = Depends(get_store)):
        m = store.get_manufacturer(manufacturer_id)
        if m is None:
            raise HTTPException(404, "Manufacturer inconnu")
        return m

    # =========================================================================
    # Pays
    # =========================================================================

    @router.get("/countries", response_model=list[Country])
    def list_countries(store: CatalogStore = Depends(get_store)):
        return store.list_countries()

    @router.post("/countries", response_model=Country)
    def upsert_country(
        payload: Country,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        return store.upsert_country(payload)

    # =========================================================================
    # Familles produit
    # =========================================================================

    @router.get("/product-families", response_model=list[ProductFamily])
    def list_families(store: CatalogStore = Depends(get_store)):
        return store.list_product_families()

    @router.post("/product-families", response_model=ProductFamily)
    def upsert_family(
        payload: ProductFamily,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        return store.upsert_product_family(payload)

    # =========================================================================
    # Plateformes
    # =========================================================================

    @router.get("/product-platforms", response_model=list[ProductPlatform])
    def list_platforms(
        family_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_product_platforms(family_id=family_id)

    @router.post("/product-platforms", response_model=ProductPlatform)
    def upsert_platform(
        payload: ProductPlatform,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.upsert_product_platform(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.get("/product-platforms/{platform_id}", response_model=ProductPlatform)
    def get_platform(platform_id: UUID, store: CatalogStore = Depends(get_store)):
        p = store.get_product_platform(platform_id)
        if p is None:
            raise HTTPException(404, "ProductPlatform inconnue")
        return p

    # =========================================================================
    # Séries
    # =========================================================================

    @router.get("/series", response_model=list[LocomotiveSeries])
    def list_series(
        platform_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_series(platform_id=platform_id)

    @router.post("/series", response_model=LocomotiveSeries)
    def upsert_series(
        payload: LocomotiveSeries,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.upsert_series(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.get("/series/{series_id}", response_model=LocomotiveSeries)
    def get_series(series_id: UUID, store: CatalogStore = Depends(get_store)):
        s = store.get_series(series_id)
        if s is None:
            raise HTTPException(404, "Series inconnue")
        return s

    # =========================================================================
    # Variantes techniques
    # =========================================================================

    @router.get("/technical-variants", response_model=list[TechnicalVariant])
    def list_variants(
        series_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_technical_variants(series_id=series_id)

    @router.post("/technical-variants", response_model=TechnicalVariant)
    def upsert_variant(
        payload: TechnicalVariant,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.upsert_technical_variant(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.get("/technical-variants/{variant_id}", response_model=TechnicalVariant)
    def get_variant(variant_id: UUID, store: CatalogStore = Depends(get_store)):
        v = store.get_technical_variant(variant_id)
        if v is None:
            raise HTTPException(404, "TechnicalVariant inconnue")
        return v

    @router.get("/technical-variants/{variant_id}/homologations", response_model=list[Homologation])
    def list_variant_homologations(variant_id: UUID, store: CatalogStore = Depends(get_store)):
        if store.get_technical_variant(variant_id) is None:
            raise HTTPException(404, "TechnicalVariant inconnue")
        return store.list_homologations_for_variant(variant_id)

    # =========================================================================
    # Homologations
    # =========================================================================

    @router.get("/homologations", response_model=list[Homologation])
    def list_homologations(store: CatalogStore = Depends(get_store)):
        return store.list_homologations()

    @router.post("/homologations", response_model=Homologation)
    def upsert_homologation(
        payload: Homologation,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        return store.upsert_homologation(payload)

    @router.get("/homologations/{homologation_id}/countries", response_model=list[Country])
    def list_homologation_countries(homologation_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_countries_for_homologation(homologation_id)

    @router.get("/homologations/{homologation_id}/variants", response_model=list[TechnicalVariant])
    def list_homologation_variants(homologation_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_variants_for_homologation(homologation_id)

    # =========================================================================
    # Associations M2M
    # =========================================================================

    @router.post("/variant-homologations", response_model=VariantHomologation)
    def set_variant_homologation(
        payload: VariantHomologation,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.set_variant_homologation(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.delete("/variant-homologations/{variant_id}/{homologation_id}", status_code=204)
    def remove_variant_homologation(
        variant_id: UUID,
        homologation_id: UUID,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        if hasattr(store, "remove_variant_homologation"):
            store.remove_variant_homologation(variant_id, homologation_id)  # type: ignore[attr-defined]
        return Response(status_code=204)

    @router.post("/homologation-countries", response_model=HomologationCountry)
    def set_homologation_country(
        payload: HomologationCountry,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.set_homologation_country(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    # =========================================================================
    # Vue hiérarchique (tree) — pratique pour le frontend
    # =========================================================================

    @router.get("/tree")
    def tree(store: CatalogStore = Depends(get_store)) -> list[dict]:
        """Renvoie toute la hiérarchie en un seul payload : familles →
        plateformes → séries → variantes → homologations. Pensé pour
        alimenter un treeview côté UI sans N+1 requêtes."""
        result = []
        for family in store.list_product_families():
            platforms_data = []
            for platform in store.list_product_platforms(family_id=family.product_family_id):
                series_data = []
                for s in store.list_series(platform_id=platform.product_platform_id):
                    variants_data = []
                    for v in store.list_technical_variants(series_id=s.series_id):
                        homos = store.list_homologations_for_variant(v.technical_variant_id)
                        variants_data.append({
                            "technical_variant_id": str(v.technical_variant_id),
                            "variant_code": v.variant_code,
                            "variant_name": v.variant_name,
                            "manufacturer_model_name": v.manufacturer_model_name,
                            "homologations": [
                                {"code": h.homologation_code, "name": h.homologation_name}
                                for h in homos
                            ],
                        })
                    series_data.append({
                        "series_id": str(s.series_id),
                        "series_code": s.series_code,
                        "series_name": s.series_name,
                        "nominal_power_kw": s.nominal_power_kw,
                        "maximum_speed_kmh": s.maximum_speed_kmh,
                        "starting_tractive_effort_kn": s.starting_tractive_effort_kn,
                        "variants": variants_data,
                    })
                platforms_data.append({
                    "product_platform_id": str(platform.product_platform_id),
                    "platform_code": platform.platform_code,
                    "platform_name": platform.platform_name,
                    "traction_mode": platform.traction_mode.value,
                    "series": series_data,
                })
            result.append({
                "product_family_id": str(family.product_family_id),
                "family_code": family.family_code,
                "family_name": family.family_name,
                "platforms": platforms_data,
            })
        return result

    # =========================================================================
    # Lot 2 — Usage & Maintenance
    # =========================================================================

    @router.get("/usage-profiles", response_model=list[UsageProfile])
    def list_usage_profiles(store: CatalogStore = Depends(get_store)):
        return store.list_usage_profiles()

    @router.post("/usage-profiles", response_model=UsageProfile)
    def upsert_usage_profile(
        payload: UsageProfile,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        return store.upsert_usage_profile(payload)

    @router.get("/mileage-bands", response_model=list[MileageBand])
    def list_mileage_bands(store: CatalogStore = Depends(get_store)):
        return store.list_mileage_bands()

    @router.get("/mileage-bands/for-annual-km/{annual_km}")
    def get_band_for_annual_km(annual_km: int, store: CatalogStore = Depends(get_store)):
        """Résolution : à quel palier appartient tel mileage annuel ?"""
        band = store.get_mileage_band_for_annual_km(annual_km)
        if band is None:
            raise HTTPException(404, "Aucun palier ne couvre ce mileage")
        return band

    @router.get("/engine-hours-bands", response_model=list[EngineHoursBand])
    def list_engine_hours_bands(store: CatalogStore = Depends(get_store)):
        return store.list_engine_hours_bands()

    @router.get("/maintenance-operations", response_model=list[MaintenanceOperation])
    def list_maintenance_operations(store: CatalogStore = Depends(get_store)):
        return store.list_maintenance_operations()

    @router.get("/maintenance-plans", response_model=list[MaintenancePlan])
    def list_maintenance_plans(store: CatalogStore = Depends(get_store)):
        return store.list_maintenance_plans()

    @router.get("/maintenance-plans/{plan_id}/operations", response_model=list[MaintenanceOperation])
    def list_plan_operations(plan_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_operations_for_plan(plan_id)

    @router.get("/ecm-providers", response_model=list[EcmProvider])
    def list_ecm_providers(store: CatalogStore = Depends(get_store)):
        return store.list_ecm_providers()

    @router.get("/service-levels", response_model=list[ServiceLevel])
    def list_service_levels(store: CatalogStore = Depends(get_store)):
        return store.list_service_levels()

    @router.get("/technical-variants/{variant_id}/usage-profiles")
    def variant_usage_profiles(variant_id: UUID, store: CatalogStore = Depends(get_store)) -> list[dict]:
        """Renvoie les profils d'usage supportés par la variante avec les
        contraintes (seuil d'avertissement, plafond, dérogation requise)."""
        if store.get_technical_variant(variant_id) is None:
            raise HTTPException(404, "TechnicalVariant inconnue")
        rows = store.list_usage_profiles_for_variant(variant_id)
        return [
            {
                "usage_profile": profile.model_dump(),
                "constraints": link.model_dump(),
            }
            for profile, link in rows
        ]

    @router.get("/technical-variants/{variant_id}/maintenance-plans",
                response_model=list[MaintenancePlan])
    def variant_maintenance_plans(variant_id: UUID, store: CatalogStore = Depends(get_store)):
        if store.get_technical_variant(variant_id) is None:
            raise HTTPException(404, "TechnicalVariant inconnue")
        return store.list_maintenance_plans_for_variant(variant_id)

    # =========================================================================
    # Lot 3 — PriceBooks & chiffrage v2
    # =========================================================================

    @router.get("/lease-bands", response_model=list[LeaseBand])
    def list_lease_bands(store: CatalogStore = Depends(get_store)):
        return store.list_lease_bands()

    @router.get("/asset-age-bands", response_model=list[AssetAgeBand])
    def list_asset_age_bands(store: CatalogStore = Depends(get_store)):
        return store.list_asset_age_bands()

    @router.get("/country-groups", response_model=list[CountryGroup])
    def list_country_groups(store: CatalogStore = Depends(get_store)):
        return store.list_country_groups()

    @router.get("/commercial-options", response_model=list[CommercialOption])
    def list_commercial_options(store: CatalogStore = Depends(get_store)):
        return store.list_commercial_options()

    @router.get("/price-books", response_model=list[PriceBook])
    def list_price_books(store: CatalogStore = Depends(get_store)):
        return store.list_price_books()

    @router.get("/price-books/{price_book_id}/versions", response_model=list[PriceBookVersion])
    def list_price_book_versions(price_book_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_price_book_versions(price_book_id=price_book_id)

    @router.get("/dry-lease-rates", response_model=list[DryLeaseRate])
    def list_dl_rates(
        version_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_dry_lease_rates(version_id=version_id)

    @router.get("/heavy-maintenance-rates", response_model=list[HeavyMaintenanceRate])
    def list_hm_rates(
        version_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_heavy_maintenance_rates(version_id=version_id)

    @router.get("/operating-maintenance-rates", response_model=list[OperatingMaintenanceRate])
    def list_om_rates(
        version_id: UUID | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_operating_maintenance_rates(version_id=version_id)

    @router.post("/chiffrage")
    def chiffrer_v2(
        body: ChiffrageRequest,
        store: CatalogStore = Depends(get_store),
    ):
        """Moteur de prix v2 : résout les tarifs via PriceBookVersion publiée
        et applique la formule OM cible du doc (section 11)."""
        moteur = MoteurPrixV2(store)
        try:
            res = moteur.chiffrer(DemandeChiffrage(**body.model_dump()))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {
            "variant_code": res.variant_code,
            "dl_mensuel": res.dl_mensuel,
            "hm_mensuel_provisionne": res.hm_mensuel_provisionne,
            "om_mensuel": res.om_mensuel,
            "total_mensuel": res.total_mensuel,
            "detail_dl": res.detail_dl,
            "detail_om": res.detail_om,
            "detail_hm": res.detail_hm,
            "warnings": res.warnings,
            "versions_utilisees": res.versions_utilisees,
            "plancher_applique": res.plancher_applique,
        }

    # =========================================================================
    # Lot 4 — Quote refondu
    # =========================================================================

    if get_quote_store is not None and get_current_user is not None:

        def _service(
            catalog_store: CatalogStore = Depends(get_store),
            quote_store: QuoteStore = Depends(get_quote_store),
        ) -> QuoteService:
            return QuoteService(catalog_store, quote_store)

        @router.post("/quotes", response_model=Quote)
        def create_quote(
            body: CreateQuoteRequest,
            svc: QuoteService = Depends(_service),
            user = Depends(get_current_user),
        ):
            return svc.creer_quote(body.client_code, body.client_name, user.email)

        @router.get("/quotes")
        def list_quotes(
            mine: bool = Query(default=False),
            status: QuoteStatus | None = Query(default=None),
            quote_store: QuoteStore = Depends(get_quote_store),
            user = Depends(get_current_user),
        ):
            # Permission : KAM voit uniquement ses quotes, PRICING/DIRECTION/ADMIN voient tout
            if mine or not user.a_permission("voir_toutes_offres"):
                return quote_store.list_quotes(created_by=user.email, status=status)
            return quote_store.list_quotes(status=status)

        @router.get("/quotes/{quote_id}")
        def get_quote(
            quote_id: UUID,
            quote_store: QuoteStore = Depends(get_quote_store),
            user = Depends(get_current_user),
        ):
            quote = quote_store.get_quote(quote_id)
            if quote is None:
                raise HTTPException(404, "Quote inconnue")
            if not user.a_permission("voir_toutes_offres") and quote.created_by.lower() != user.email.lower():
                raise HTTPException(403, "Pas autorisé à voir cette quote")
            lines = quote_store.list_quote_lines(quote_id)
            # Embed calculations + components
            lines_with_calc = []
            for line in lines:
                calc = quote_store.get_pricing_calculation_for_line(line.quote_line_id)
                components = quote_store.list_components(calc.pricing_calculation_id) if calc else []
                rules = quote_store.list_applied_rules(calc.pricing_calculation_id) if calc else []
                lines_with_calc.append({
                    "line": line.model_dump(mode="json"),
                    "calculation": calc.model_dump(mode="json") if calc else None,
                    "components": [c.model_dump(mode="json") for c in components],
                    "applied_rules": [r.model_dump(mode="json") for r in rules],
                })
            return {"quote": quote.model_dump(mode="json"), "lines": lines_with_calc}

        @router.post("/quotes/{quote_id}/lines")
        def add_line(
            quote_id: UUID,
            body: AddQuoteLineRequest,
            svc: QuoteService = Depends(_service),
            user = Depends(get_current_user),
            quote_store: QuoteStore = Depends(get_quote_store),
        ):
            quote = quote_store.get_quote(quote_id)
            if quote is None:
                raise HTTPException(404, "Quote inconnue")
            if quote.created_by.lower() != user.email.lower() and not user.a_permission("voir_toutes_offres"):
                raise HTTPException(403, "Pas autorisé à modifier cette quote")
            try:
                line, calc = svc.ajouter_ligne_et_chiffrer(
                    quote_id=quote_id,
                    technical_variant_code=body.technical_variant_code,
                    country_iso=body.country_iso,
                    duration_months=body.duration_months,
                    age_years=body.age_years,
                    annual_mileage_km=body.annual_mileage_km,
                    annual_engine_hours=body.annual_engine_hours,
                    quantity=body.quantity,
                    ecm_provider_code=body.ecm_provider_code,
                    service_level_code=body.service_level_code,
                )
            except ValueError as e:
                raise HTTPException(422, str(e))
            return {
                "line": line.model_dump(mode="json"),
                "calculation": calc.model_dump(mode="json"),
            }

        @router.delete("/quotes/{quote_id}/lines/{line_id}", status_code=204)
        def delete_line(
            quote_id: UUID,
            line_id: UUID,
            quote_store: QuoteStore = Depends(get_quote_store),
            user = Depends(get_current_user),
        ):
            quote = quote_store.get_quote(quote_id)
            if quote is None:
                raise HTTPException(404, "Quote inconnue")
            if quote.created_by.lower() != user.email.lower() and not user.a_permission("voir_toutes_offres"):
                raise HTTPException(403, "Pas autorisé")
            quote_store.delete_quote_line(line_id)
            # Recalculer totaux
            svc = QuoteService(get_store(), quote_store)
            svc._recalculer_totaux_quote(quote_id)
            from fastapi import Response
            return Response(status_code=204)

        @router.post("/quotes/{quote_id}/submit", response_model=Quote)
        def submit_quote(
            quote_id: UUID,
            svc: QuoteService = Depends(_service),
            user = Depends(get_current_user),
        ):
            try:
                return svc.soumettre(quote_id, user.email)
            except ValueError as e:
                raise HTTPException(409, str(e))

        @router.post("/quotes/{quote_id}/decision", response_model=Quote)
        def decision_quote(
            quote_id: UUID,
            body: DecisionQuoteRequest,
            svc: QuoteService = Depends(_service),
            user = Depends(get_current_user),
        ):
            if not user.a_permission("decider_derogation"):
                raise HTTPException(403, "Permission `decider_derogation` requise")
            try:
                return svc.decider(quote_id, user.email, body.approved, body.comment)
            except ValueError as e:
                raise HTTPException(409, str(e))

        @router.delete("/quotes/{quote_id}", status_code=204)
        def delete_quote(
            quote_id: UUID,
            quote_store: QuoteStore = Depends(get_quote_store),
            user = Depends(get_current_user),
        ):
            quote = quote_store.get_quote(quote_id)
            if quote is None:
                raise HTTPException(404, "Quote inconnue")
            if quote.created_by.lower() != user.email.lower() and not user.a_permission("gerer_utilisateurs"):
                raise HTTPException(403, "Pas autorisé à supprimer cette quote")
            quote_store.delete_quote(quote_id)
            from fastapi import Response
            return Response(status_code=204)

    # =========================================================================
    # Lot 5 — Flotte réelle (FleetAssets + MeterReadings + MaintenanceHistory)
    # =========================================================================

    @router.get("/fleet-assets", response_model=list[FleetAsset])
    def list_fleet_assets(
        variant_id: UUID | None = Query(default=None),
        operational_status: OperationalStatus | None = Query(default=None),
        store: CatalogStore = Depends(get_store),
    ):
        return store.list_fleet_assets(variant_id=variant_id, operational_status=operational_status)

    @router.get("/fleet-assets/{asset_id}", response_model=FleetAsset)
    def get_fleet_asset(asset_id: UUID, store: CatalogStore = Depends(get_store)):
        a = store.get_fleet_asset(asset_id)
        if a is None:
            raise HTTPException(404, "FleetAsset inconnu")
        return a

    @router.post("/fleet-assets", response_model=FleetAsset)
    def upsert_fleet_asset(
        payload: FleetAsset,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        try:
            return store.upsert_fleet_asset(payload)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.get("/fleet-assets/{asset_id}/summary")
    def get_fleet_asset_summary(asset_id: UUID, store: CatalogStore = Depends(get_store)):
        s = store.compute_fleet_asset_summary(asset_id)
        if s is None:
            raise HTTPException(404, "FleetAsset inconnu")
        return s.model_dump(mode="json")

    @router.get("/fleet-assets/{asset_id}/meter-readings", response_model=list[AssetMeterReading])
    def list_meter_readings(asset_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_meter_readings(asset_id)

    @router.post("/fleet-assets/{asset_id}/meter-readings", response_model=AssetMeterReading)
    def add_meter_reading(
        asset_id: UUID,
        payload: AssetMeterReading,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        # Force la cohérence : le fleet_asset_id du payload doit correspondre
        payload_corrige = payload.model_copy(update={"fleet_asset_id": asset_id})
        try:
            return store.add_meter_reading(payload_corrige)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @router.get("/fleet-assets/{asset_id}/maintenance-history",
                response_model=list[AssetMaintenanceHistoryEntry])
    def list_maintenance_history(asset_id: UUID, store: CatalogStore = Depends(get_store)):
        return store.list_maintenance_history(asset_id)

    @router.post("/fleet-assets/{asset_id}/maintenance-history",
                 response_model=AssetMaintenanceHistoryEntry)
    def add_maintenance_history(
        asset_id: UUID,
        payload: AssetMaintenanceHistoryEntry,
        _=Depends(require_admin),
        store: CatalogStore = Depends(get_store),
    ):
        payload_corrige = payload.model_copy(update={"fleet_asset_id": asset_id})
        try:
            return store.add_maintenance_history(payload_corrige)
        except ValueError as e:
            raise HTTPException(422, str(e))

    return router
