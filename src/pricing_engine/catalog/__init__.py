"""Catalog PricingHub — référentiel locomotive hiérarchique.

Implémente l'architecture cible du document Architecture_Cible_PricingHub :
le configurateur actuel mélange produit, série, homologation, sous-série,
configuration technique et mileage. Ce package sépare proprement :

    ProductFamily
        └── ProductPlatform        (constructeur, mode traction)
            └── LocomotiveSeries   (puissance, vitesse, effort)
                └── TechnicalVariant (la vraie clé de calcul)
                    ├── Homologations (M2M via VariantHomologations)
                    └── (Lot 2+) UsageProfiles, MaintenancePlans,
                                 CommercialOptions, FleetAssets

Règles fondamentales (section 16 du doc) :
    Locomotive ≠ Mileage
    Locomotive ≠ Prix
    Série     ≠ Homologation
    Sous-série ≠ Asset physique
    Prix OM   ≠ propriété permanente de la sous-série

Coexiste avec l'ancien modèle `Serie` (src/pricing_engine/models.py) :
le moteur de prix reste sur Serie tant que les Lots 3 (tarifs versionnés)
et 4 (configurateur refondu) ne sont pas livrés. Pas de régression.
"""

from .entities import (
    Country,
    Homologation,
    HomologationCountry,
    LocomotiveSeries,
    Manufacturer,
    ProductFamily,
    ProductPlatform,
    StatutHomologation,
    TechnicalVariant,
    TractionMode,
    VariantHomologation,
)
from .store import CatalogStore, InMemoryCatalogStore

__all__ = [
    "Country",
    "Homologation",
    "HomologationCountry",
    "LocomotiveSeries",
    "Manufacturer",
    "ProductFamily",
    "ProductPlatform",
    "StatutHomologation",
    "TechnicalVariant",
    "TractionMode",
    "VariantHomologation",
    "CatalogStore",
    "InMemoryCatalogStore",
]
