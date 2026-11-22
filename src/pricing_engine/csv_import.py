"""Import CSV en masse du référentiel.

Trois imports supportés :
- Grille Dry lease (série × tranche durée → loyer)
- Budget Plan (série × tranche km → BP HM / OM / exercice)
- Flotte (locomotives avec produit, sous-série, homologations)

Chaque import remplace entièrement la section correspondante du brouillon
(écrasement, pas fusion) : c'est la sémantique de `PUT` des endpoints
existants, à laquelle les CSV se substituent.

Format : CSV avec en-tête, séparateur virgule, encodage UTF-8. Les
colonnes sont listées en tête de chaque parseur ; les champs numériques
acceptent le séparateur décimal "." et un vide = None pour les bornes
ouvertes. Pour les listes (homologations), séparateur `;` dans la cellule.

Les erreurs de ligne sont accumulées (`ResultatImport.erreurs`) plutôt que
de lever à la première : l'équipe pricing voit tout d'un coup, corrige et
réimporte.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .models import (
    BudgetPlanEntry,
    GrilleDryLeaseEntry,
    Locomotive,
    StatutLocomotive,
    TrancheDuree,
    TrancheKm,
)


@dataclass
class ResultatImport:
    nb_lignes_lues: int = 0
    nb_lignes_importees: int = 0
    erreurs: list[str] = field(default_factory=list)
    grille_dry_lease: list[GrilleDryLeaseEntry] = field(default_factory=list)
    budget_plan: list[BudgetPlanEntry] = field(default_factory=list)
    tranches_km: list[TrancheKm] = field(default_factory=list)
    locomotives: list[Locomotive] = field(default_factory=list)


def _parse_float_optionnel(valeur: str | None) -> float | None:
    if valeur is None:
        return None
    v = valeur.strip()
    if not v:
        return None
    return float(v.replace(",", "."))


def _parse_int_optionnel(valeur: str | None) -> int | None:
    f = _parse_float_optionnel(valeur)
    return int(f) if f is not None else None


def _lecteur(contenu: str) -> csv.DictReader:
    """Lecteur CSV tolérant :
    - mange le BOM UTF-8 (Excel en met toujours un)
    - détecte automatiquement le séparateur `,` ou `;` (Excel français
      utilise `;` par défaut parce que `,` sert au décimal)
    - détecte aussi tabulation et pipe au cas où
    """
    if contenu.startswith("﻿"):
        contenu = contenu.lstrip("﻿")
    # Sniffer échoue parfois sur des CSV courts : on regarde la 1re ligne
    # à la main et on pique le séparateur qui apparaît le plus souvent.
    premiere_ligne = contenu.split("\n", 1)[0]
    separateurs = {",": premiere_ligne.count(","), ";": premiere_ligne.count(";"),
                   "\t": premiere_ligne.count("\t"), "|": premiere_ligne.count("|")}
    separateur = max(separateurs, key=lambda k: separateurs[k])
    if separateurs[separateur] == 0:
        separateur = ","
    return csv.DictReader(io.StringIO(contenu), delimiter=separateur)


# Signatures de reconnaissance : colonne caractéristique → type d'import.
# L'ordre compte : on teste du plus spécifique au plus général.
SIGNATURES = [
    ("flotte", {"numero", "produit", "homologations"}),
    ("flotte", {"numero", "mise_en_service", "km_cumules"}),
    ("budget-plan", {"serie_code", "bp_hm", "bp_om"}),
    ("dry-lease-grille", {"serie_code", "duree_min_mois", "loyer_mensuel"}),
    ("dry-lease-grille", {"serie_code", "loyer_mensuel"}),
]


def detecter_type_import(contenu: str) -> str | None:
    """Regarde les colonnes de l'en-tête et renvoie "dry-lease-grille",
    "budget-plan", "flotte" ou None si rien ne correspond."""
    lecteur = _lecteur(contenu)
    champs = {(c or "").strip().lower() for c in (lecteur.fieldnames or [])}
    if not champs:
        return None
    for type_import, colonnes_requises in SIGNATURES:
        if colonnes_requises.issubset(champs):
            return type_import
    return None


def importer_grille_dry_lease(contenu: str) -> ResultatImport:
    """Colonnes attendues : serie_code, duree_min_mois, duree_max_mois,
    loyer_mensuel. duree_max_mois vide = pas de borne haute."""
    r = ResultatImport()
    lecteur = _lecteur(contenu)
    for i, ligne in enumerate(lecteur, start=2):  # ligne 1 = en-tête
        r.nb_lignes_lues += 1
        try:
            entree = GrilleDryLeaseEntry(
                serie_code=(ligne.get("serie_code") or "").strip().upper(),
                tranche_duree=TrancheDuree(
                    duree_min_mois=_parse_int_optionnel(ligne.get("duree_min_mois")) or 0,
                    duree_max_mois=_parse_int_optionnel(ligne.get("duree_max_mois")),
                ),
                loyer_mensuel=_parse_float_optionnel(ligne.get("loyer_mensuel")) or 0,
            )
            if not entree.serie_code:
                raise ValueError("serie_code manquant")
            r.grille_dry_lease.append(entree)
            r.nb_lignes_importees += 1
        except (ValueError, TypeError) as exc:
            r.erreurs.append(f"Ligne {i} : {exc}")
    return r


def importer_budget_plan(contenu: str) -> ResultatImport:
    """Colonnes : serie_code, km_min, km_max, bp_hm, bp_om, exercice."""
    r = ResultatImport()
    lecteur = _lecteur(contenu)
    tranches_vues: dict[tuple[int, int | None], TrancheKm] = {}

    for i, ligne in enumerate(lecteur, start=2):
        r.nb_lignes_lues += 1
        try:
            serie_code = (ligne.get("serie_code") or "").strip().upper()
            if not serie_code:
                raise ValueError("serie_code manquant")

            km_min = _parse_int_optionnel(ligne.get("km_min"))
            km_max = _parse_int_optionnel(ligne.get("km_max"))
            if km_min is None:
                raise ValueError("km_min manquant")

            cle = (km_min, km_max)
            tranche = tranches_vues.get(cle)
            if tranche is None:
                tranche = TrancheKm(
                    km_min=km_min,
                    km_max=km_max if km_max is not None else km_min * 10,
                    coefficient_dl=1.0,
                    coefficient_hm=1.0,
                    coefficient_om=1.0,
                )
                tranches_vues[cle] = tranche
                r.tranches_km.append(tranche)

            exercice = (ligne.get("exercice") or "").strip() or str(date.today().year)
            entree = BudgetPlanEntry(
                serie_code=serie_code,
                tranche_km=tranche,
                bp_hm=_parse_float_optionnel(ligne.get("bp_hm")) or 0,
                bp_om=_parse_float_optionnel(ligne.get("bp_om")) or 0,
                exercice=exercice,
            )
            r.budget_plan.append(entree)
            r.nb_lignes_importees += 1
        except (ValueError, TypeError) as exc:
            r.erreurs.append(f"Ligne {i} : {exc}")

    # Tranches de km dédupliquées pour écraser draft.tranches_km : trie par
    # km_min pour que l'ordre d'évaluation dans `tranche_km_pour` soit stable.
    r.tranches_km.sort(key=lambda t: t.km_min)
    return r


def importer_flotte(contenu: str) -> ResultatImport:
    """Colonnes : numero, produit, sous_serie, serie_code, homologations,
    mise_en_service (YYYY-MM-DD), km_cumules, statut.

    `homologations` est une liste séparée par `;` dans la cellule, ex.
    "PL;DE;AT". `statut` = disponible / affectee / en_maintenance /
    hors_service."""
    r = ResultatImport()
    lecteur = _lecteur(contenu)
    for i, ligne in enumerate(lecteur, start=2):
        r.nb_lignes_lues += 1
        try:
            numero = (ligne.get("numero") or "").strip().upper()
            if not numero:
                raise ValueError("numero manquant")

            homo_brut = (ligne.get("homologations") or "").strip()
            homologations = [h.strip().upper() for h in homo_brut.split(";") if h.strip()]

            mise_en_service_brut = (ligne.get("mise_en_service") or "").strip()
            if not mise_en_service_brut:
                raise ValueError("mise_en_service manquante")
            mise_en_service = date.fromisoformat(mise_en_service_brut)

            statut_brut = (ligne.get("statut") or "disponible").strip().lower()
            try:
                statut = StatutLocomotive(statut_brut)
            except ValueError:
                raise ValueError(f"statut inconnu : {statut_brut}")

            loco = Locomotive(
                numero=numero,
                serie_code=(ligne.get("serie_code") or "").strip().upper(),
                mise_en_service=mise_en_service,
                km_cumules=_parse_float_optionnel(ligne.get("km_cumules")) or 0,
                statut=statut,
                produit=(ligne.get("produit") or "").strip().upper(),
                sous_serie=(ligne.get("sous_serie") or "").strip().upper(),
                homologations=homologations,
            )
            r.locomotives.append(loco)
            r.nb_lignes_importees += 1
        except (ValueError, TypeError) as exc:
            r.erreurs.append(f"Ligne {i} : {exc}")
    return r
