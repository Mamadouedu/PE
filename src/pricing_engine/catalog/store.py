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
