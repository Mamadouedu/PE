"""Seed de référence Akiem — données tirées du doc Architecture Cible
et du configurateur Excel analysé.

Peuple un CatalogStore avec :
- 4 constructeurs (Bombardier/Alstom, Siemens, Stadler Rail, Vossloh)
- 17 pays européens (DE, AT, CH, IT, FR, PL, CZ, SK, HU, RO, NL, BE, LU, DK, SE, NO, UK)
- 4 familles produit
- 5 plateformes (TRAXX_AC, TRAXX_MS, VECTRON_MS, VECTRON_AC, EURODUAL)
- 7 séries (E185, E186, E187, 193, 159, F140, Smartron)
- ~20 variantes techniques (E185-DA, E186-DABNL, 193-MS-DEATNLBECZ...)
- 6 packages d'homologation (DABNL, DABF, DACH, DACHIN, DEATCH, FR_ONLY...)

Ces identifiants sont ceux du configurateur réel, pas des placeholders.
"""

from __future__ import annotations

from datetime import date

from .entities import (
    Country,
    Homologation,
    HomologationCountry,
    LocomotiveSeries,
    Manufacturer,
    ProductFamily,
    ProductPlatform,
    TechnicalVariant,
    TractionMode,
    VariantHomologation,
)
from .store import CatalogStore, InMemoryCatalogStore


# ---------------- Données brutes ----------------

PAYS = [
    ("DE", "Allemagne", "Germany", "DB_NETZ"),
    ("AT", "Autriche", "Austria", "OBB_INFRA"),
    ("CH", "Suisse", "Switzerland", "SBB_INFRA"),
    ("IT", "Italie", "Italy", "RFI"),
    ("FR", "France", "France", "SNCF_RESEAU"),
    ("PL", "Pologne", "Poland", "PKP_PLK"),
    ("CZ", "République tchèque", "Czechia", "SZDC"),
    ("SK", "Slovaquie", "Slovakia", "ZSR"),
    ("HU", "Hongrie", "Hungary", "MAV"),
    ("RO", "Roumanie", "Romania", "CFR"),
    ("NL", "Pays-Bas", "Netherlands", "PRORAIL"),
    ("BE", "Belgique", "Belgium", "INFRABEL"),
    ("LU", "Luxembourg", "Luxembourg", "CFL_INFRA"),
    ("DK", "Danemark", "Denmark", "BANEDANMARK"),
    ("SE", "Suède", "Sweden", "TRAFIKVERKET"),
    ("NO", "Norvège", "Norway", "BANENOR"),
    ("UK", "Royaume-Uni", "United Kingdom", "NETWORK_RAIL"),
]

CONSTRUCTEURS = [
    ("BOMBARDIER", "Bombardier Transportation", "CA", "Alstom (depuis 2021)"),
    ("ALSTOM", "Alstom", "FR", None),
    ("SIEMENS", "Siemens Mobility", "DE", None),
    ("STADLER", "Stadler Rail", "CH", None),
    ("VOSSLOH", "Vossloh Locomotives", "DE", None),
]

FAMILLES = [
    ("ELECTRIC_LOCO", "Electric Locomotive"),
    ("DIESEL_LOCO", "Diesel Locomotive"),
    ("DUAL_MODE_LOCO", "Dual-Mode Locomotive"),
    ("PASSENGER_RS", "Passenger Rolling Stock"),
]

# Plateformes : (code, nom, famille, constructeur, mode traction)
PLATEFORMES = [
    ("TRAXX_AC", "Traxx AC", "ELECTRIC_LOCO", "BOMBARDIER", TractionMode.AC),
    ("TRAXX_MS", "Traxx Multi-System", "ELECTRIC_LOCO", "BOMBARDIER", TractionMode.MS),
    ("TRAXX_DC", "Traxx DC", "ELECTRIC_LOCO", "BOMBARDIER", TractionMode.DC),
    ("TRAXX_DE", "Traxx Diesel-Électrique", "DIESEL_LOCO", "BOMBARDIER", TractionMode.DE),
    ("VECTRON_AC", "Vectron AC", "ELECTRIC_LOCO", "SIEMENS", TractionMode.AC),
    ("VECTRON_MS", "Vectron Multi-System", "ELECTRIC_LOCO", "SIEMENS", TractionMode.MS),
    ("VECTRON_DC", "Vectron DC", "ELECTRIC_LOCO", "SIEMENS", TractionMode.DC),
    ("VECTRON_DE", "Vectron Diesel", "DIESEL_LOCO", "SIEMENS", TractionMode.DE),
    ("EURODUAL", "Eurodual", "DUAL_MODE_LOCO", "STADLER", TractionMode.DUAL),
    ("SMARTRON", "Smartron", "ELECTRIC_LOCO", "SIEMENS", TractionMode.AC),
]

# Séries : (code, nom, plateforme, kW, km/h, kN, mode, prod_from, prod_to)
SERIES = [
    ("E185", "E185 / F140 AC", "TRAXX_AC", 5600, 140, 300, TractionMode.AC, 2005, 2011),
    ("E186", "E186 / F140 MS", "TRAXX_MS", 5600, 140, 300, TractionMode.MS, 2008, 2016),
    ("E187", "E187 / F140 MS2e", "TRAXX_MS", 5600, 160, 300, TractionMode.MS, 2015, 2020),
    ("E188", "E188 / Traxx MS3", "TRAXX_MS", 5600, 160, 300, TractionMode.MS, 2019, None),
    ("193", "Vectron MS", "VECTRON_MS", 6400, 160, 300, TractionMode.MS, 2010, None),
    ("191", "Vectron AC", "VECTRON_AC", 6400, 200, 300, TractionMode.AC, 2010, None),
    ("159", "Eurodual", "EURODUAL", 6150, 160, 500, TractionMode.DUAL, 2018, None),
]

# Homologations : (code, nom, description)
HOMOLOGATIONS = [
    ("DABNL", "DE+AT+BE+NL", "Allemagne, Autriche, Belgique, Pays-Bas (corridor Rhin-Alpes)"),
    ("DABF", "DE+AT+BE+FR", "Ajoute la France au DABN — pour trafic vers Dunkerque / Fos"),
    ("DACH", "DE+AT+CH", "Corridor alpin classique"),
    ("DACHI", "DE+AT+CH+IT", "Corridor alpin + Italie"),
    ("DA", "DE+AT", "Homologation bi-pays minimale, germanophone"),
    ("DAHU", "DE+AT+HU", "Corridor est-européen"),
    ("DBF", "DE+BE+FR", "Corridor Rhin-Seine"),
    ("PL_CZ_SK_HU", "PL+CZ+SK+HU", "Europe centrale"),
    ("FR_ONLY", "FR uniquement", "France seule (Akiem domestic)"),
    ("UK_ONLY", "UK uniquement", "Royaume-Uni post-Brexit"),
    ("SCANDINAVIA", "DK+SE+NO", "Pays nordiques"),
]

# Variantes : (code, nom, série, manufacturer_model, homologations_codes)
VARIANTES = [
    # E185 (Traxx AC)
    ("E185-DA", "Traxx F140 AC - DE/AT", "E185", "TRAXX F140 AC1", ["DA"]),
    ("E185-DACH", "Traxx F140 AC - DE/AT/CH", "E185", "TRAXX F140 AC1", ["DACH"]),
    ("E185-DAHU", "Traxx F140 AC - DE/AT/HU", "E185", "TRAXX F140 AC1", ["DAHU"]),
    # E186 (Traxx MS) — point d'entrée du document
    ("E186-DABNL", "Traxx F140 MS - DE/AT/BE/NL", "E186", "TRAXX F140 MS", ["DABNL"]),
    ("E186-DBF", "Traxx F140 MS - DE/BE/FR", "E186", "TRAXX F140 MS", ["DBF"]),
    ("E186-DABF", "Traxx F140 MS - DE/AT/BE/FR", "E186", "TRAXX F140 MS", ["DABF"]),
    # E187
    ("E187-DACHI", "Traxx MS2e - DACHI", "E187", "TRAXX MS2e", ["DACHI"]),
    # E188 (MS3, dernière génération)
    ("E188-DACHI", "Traxx MS3 - DACHI", "E188", "TRAXX MS3", ["DACHI"]),
    ("E188-PLCZSK", "Traxx MS3 - Est-UE", "E188", "TRAXX MS3", ["PL_CZ_SK_HU"]),
    # Vectron 193 MS
    ("193-DACHI", "Vectron MS - DACHI", "193", "Vectron MS", ["DACHI"]),
    ("193-DABNL", "Vectron MS - DABNL", "193", "Vectron MS", ["DABNL"]),
    ("193-PLCZSK", "Vectron MS - Est-UE", "193", "Vectron MS", ["PL_CZ_SK_HU"]),
    # Vectron 191 AC
    ("191-DA", "Vectron AC - DE/AT", "191", "Vectron AC", ["DA"]),
    # Eurodual 159 (hybride)
    ("159-DABF", "Eurodual - DE/AT/BE/FR", "159", "Eurodual BiMode", ["DABF"]),
    ("159-DACH", "Eurodual - DE/AT/CH", "159", "Eurodual BiMode", ["DACH"]),
]

# Pays couverts par chaque homologation (code homologation → liste iso)
HOMOLOGATION_PAYS = {
    "DABNL": ["DE", "AT", "BE", "NL"],
    "DABF": ["DE", "AT", "BE", "FR"],
    "DACH": ["DE", "AT", "CH"],
    "DACHI": ["DE", "AT", "CH", "IT"],
    "DA": ["DE", "AT"],
    "DAHU": ["DE", "AT", "HU"],
    "DBF": ["DE", "BE", "FR"],
    "PL_CZ_SK_HU": ["PL", "CZ", "SK", "HU"],
    "FR_ONLY": ["FR"],
    "UK_ONLY": ["UK"],
    "SCANDINAVIA": ["DK", "SE", "NO"],
}


def seed_catalog_akiem(store: CatalogStore | None = None) -> InMemoryCatalogStore:
    """Peuple un CatalogStore avec le référentiel Akiem par défaut.

    Si aucun store n'est passé, en crée un en mémoire. Retourne le store
    peuplé pour que l'appelant puisse l'injecter dans l'API."""

    s = store if store is not None else InMemoryCatalogStore()

    # Pays
    pays_par_iso = {}
    for iso, name_fr, name_en, network in PAYS:
        c = s.upsert_country(Country(
            iso_alpha2=iso, name_fr=name_fr, name_en=name_en,
            default_network_code=network,
        ))
        pays_par_iso[iso] = c

    # Constructeurs
    manufacturer_par_code = {}
    for code, name, origin, parent in CONSTRUCTEURS:
        m = s.upsert_manufacturer(Manufacturer(
            code=code, name=name, country_of_origin_iso=origin, parent_company=parent,
        ))
        manufacturer_par_code[code] = m

    # Familles
    famille_par_code = {}
    for code, name in FAMILLES:
        f = s.upsert_product_family(ProductFamily(family_code=code, family_name=name))
        famille_par_code[code] = f

    # Plateformes
    plateforme_par_code = {}
    for code, name, famille_code, cnst_code, tm in PLATEFORMES:
        p = s.upsert_product_platform(ProductPlatform(
            product_family_id=famille_par_code[famille_code].product_family_id,
            platform_code=code, platform_name=name,
            manufacturer_id=manufacturer_par_code[cnst_code].manufacturer_id,
            traction_mode=tm,
        ))
        plateforme_par_code[code] = p

    # Séries
    serie_par_code = {}
    for code, name, platform_code, kw, kmh, kn, tm, pf, pt in SERIES:
        serie = s.upsert_series(LocomotiveSeries(
            product_platform_id=plateforme_par_code[platform_code].product_platform_id,
            series_code=code, series_name=name,
            nominal_power_kw=kw, maximum_speed_kmh=kmh, starting_tractive_effort_kn=kn,
            traction_mode=tm, production_start_year=pf, production_end_year=pt,
        ))
        serie_par_code[code] = serie

    # Homologations
    homologation_par_code = {}
    for code, name, description in HOMOLOGATIONS:
        h = s.upsert_homologation(Homologation(
            homologation_code=code, homologation_name=name, description=description,
            valid_from=date(2015, 1, 1),
        ))
        homologation_par_code[code] = h

    # Variantes techniques + leurs homologations (M2M)
    for code, name, serie_code, model, homo_codes in VARIANTES:
        serie = serie_par_code[serie_code]
        # Retrouve la plateforme de cette série pour construire le config_code
        platform = next(
            p for p in plateforme_par_code.values()
            if p.product_platform_id == serie.product_platform_id
        )
        config_code = f"{platform.platform_code}|{code}"
        variant = s.upsert_technical_variant(TechnicalVariant(
            series_id=serie.series_id,
            variant_code=code, variant_name=name,
            manufacturer_model_name=model,
            technical_configuration_code=config_code,
            traction_mode=serie.traction_mode,
            nominal_power_kw=serie.nominal_power_kw,
            maximum_speed_kmh=serie.maximum_speed_kmh,
            starting_tractive_effort_kn=serie.starting_tractive_effort_kn,
        ))
        for hc in homo_codes:
            s.set_variant_homologation(VariantHomologation(
                technical_variant_id=variant.technical_variant_id,
                homologation_id=homologation_par_code[hc].homologation_id,
                is_standard=True,
            ))

    # Homologation → Pays
    for homo_code, iso_list in HOMOLOGATION_PAYS.items():
        h = homologation_par_code[homo_code]
        for iso in iso_list:
            c = pays_par_iso[iso]
            s.set_homologation_country(HomologationCountry(
                homologation_id=h.homologation_id,
                country_id=c.country_id,
                network_code=c.default_network_code,
                is_approved=True,
            ))

    return s  # type: ignore[return-value]
