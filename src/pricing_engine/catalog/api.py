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
from .store import CatalogStore, InMemoryCatalogStore


def build_catalog_router(
    get_store: Callable[[], CatalogStore],
    exiger_permission: Callable[[str], Callable],
) -> APIRouter:
    """Construit le router. Les dépendances `get_store` et `exiger_permission`
    sont injectées par `api.py` qui est le propriétaire des instances
    globales."""

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

    return router
