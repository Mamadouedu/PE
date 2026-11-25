"""Import CSV de la flotte physique Akiem (FleetAsset du Lot 5).

Lit un CSV listant les locomotives réelles à charger dans le catalog :

    asset_number,vehicle_registration_number,technical_variant_code,
    manufacturing_year,commissioning_date,ownership_status,
    operational_status,current_mileage_km,current_engine_hours,
    current_country_iso,current_ecm_provider_code,notes

Conception :
- Dry-run par défaut : lit, valide, rapporte, écrit rien. L'opérateur
  vérifie le rapport avant de relancer avec --apply.
- Résolution des FK par code lisible (technical_variant_code,
  country_iso, ecm_provider_code) — l'opérateur n'a pas à gérer les
  UUIDs.
- Idempotent : un asset_number existant est mis à jour (upsert), pas
  dupliqué. L'opérateur peut réimporter un CSV corrigé.
- Transactionnel : tout ou rien (sauf dry-run). Si une ligne échoue,
  rollback complet. Pas de half-way state.
- Report structuré : liste des lignes ok, rejetées avec motif précis.

Validation :
- Champs obligatoires non vides
- technical_variant_code résolu (sinon ligne rejetée)
- Dates ISO 8601 (YYYY-MM-DD)
- Numériques >= 0
- country_iso optionnel, 2 caractères si fourni
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .fleet import FleetAsset, OperationalStatus, OwnershipStatus


# Colonnes obligatoires dans l'en-tête CSV
REQUIRED_COLUMNS = {
    "asset_number",
    "vehicle_registration_number",
    "technical_variant_code",
    "manufacturing_year",
    "commissioning_date",
}

# Colonnes optionnelles avec valeurs par défaut
OPTIONAL_DEFAULTS = {
    "ownership_status": "owned",
    "operational_status": "available",
    "current_mileage_km": "0",
    "current_engine_hours": "0",
    "current_country_iso": "",
    "current_ecm_provider_code": "",
    "notes": "",
}


@dataclass
class ImportFleetResult:
    """Rapport d'import, pensé pour un print/log humain ou une
    sérialisation JSON si l'opérateur veut l'intégrer à son CI."""

    total_rows: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    inserted: int = 0        # Nouveau asset_number créé
    updated: int = 0         # asset_number existant mis à jour
    errors: list[str] = field(default_factory=list)   # "L3: ..."
    dry_run: bool = True
    applied: bool = False    # True si transaction commitée

    def summary(self) -> str:
        mode = "DRY-RUN" if self.dry_run else ("APPLIQUÉ" if self.applied else "ÉCHEC")
        lines = [
            f"Import flotte — mode {mode}",
            f"  Lignes lues:       {self.total_rows}",
            f"  Lignes valides:    {self.valid_rows}",
            f"  Lignes rejetées:   {self.rejected_rows}",
        ]
        if not self.dry_run and self.applied:
            lines.append(f"  Insertions:        {self.inserted}")
            lines.append(f"  Mises à jour:      {self.updated}")
        if self.errors:
            lines.append("  Erreurs:")
            for e in self.errors[:50]:
                lines.append(f"    - {e}")
            if len(self.errors) > 50:
                lines.append(f"    ... et {len(self.errors) - 50} autres")
        return "\n".join(lines)


def _parse_csv_rows(contents: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse le CSV avec auto-détection du séparateur ,;|tab et
    tolérance au BOM. Retourne (rows, erreurs_header)."""
    errors: list[str] = []
    if contents.startswith("﻿"):
        contents = contents.lstrip("﻿")

    first_line = contents.split("\n", 1)[0] if contents else ""
    counts = {",": first_line.count(","), ";": first_line.count(";"),
              "\t": first_line.count("\t"), "|": first_line.count("|")}
    sep = max(counts, key=lambda k: counts[k]) if max(counts.values()) > 0 else ","

    reader = csv.DictReader(io.StringIO(contents), delimiter=sep)
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        errors.append(f"Colonnes manquantes dans l'en-tête : {sorted(missing)}")
        return [], errors
    return list(reader), errors


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    """Trim + applique les defaults pour les colonnes optionnelles."""
    normalized = {k: (v or "").strip() for k, v in row.items()}
    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in normalized or normalized[col] == "":
            normalized[col] = default
    return normalized


def _validate_row(row: dict[str, str], line_no: int) -> list[str]:
    errors = []
    for col in REQUIRED_COLUMNS:
        if not row.get(col):
            errors.append(f"L{line_no}: colonne obligatoire vide: {col}")

    if row.get("commissioning_date"):
        try:
            date.fromisoformat(row["commissioning_date"])
        except ValueError:
            errors.append(f"L{line_no}: commissioning_date invalide (attendu YYYY-MM-DD): "
                          f"{row['commissioning_date']!r}")

    if row.get("manufacturing_year"):
        try:
            year = int(row["manufacturing_year"])
            if year < 1950 or year > 2100:
                errors.append(f"L{line_no}: manufacturing_year hors bornes [1950-2100]: {year}")
        except ValueError:
            errors.append(f"L{line_no}: manufacturing_year non entier: {row['manufacturing_year']!r}")

    for num_col in ("current_mileage_km", "current_engine_hours"):
        val = row.get(num_col, "0")
        try:
            if float(val) < 0:
                errors.append(f"L{line_no}: {num_col} doit être >= 0 (reçu {val})")
        except ValueError:
            errors.append(f"L{line_no}: {num_col} non numérique: {val!r}")

    iso = row.get("current_country_iso", "")
    if iso and len(iso) != 2:
        errors.append(f"L{line_no}: current_country_iso doit faire 2 caractères (reçu {iso!r})")

    for enum_col, enum_cls in (("ownership_status", OwnershipStatus),
                                ("operational_status", OperationalStatus)):
        val = row.get(enum_col, "")
        if val:
            try:
                enum_cls(val)
            except ValueError:
                vals = [e.value for e in enum_cls]
                errors.append(f"L{line_no}: {enum_col} invalide: {val!r} (valeurs: {vals})")
    return errors


def _resolve_row_to_asset(
    row: dict[str, str], line_no: int, catalog_store,
) -> tuple[FleetAsset | None, list[str]]:
    """Résout les codes vers les UUIDs catalog et construit le FleetAsset."""
    errors: list[str] = []

    variant = next(
        (v for v in catalog_store.list_technical_variants()
         if v.variant_code == row["technical_variant_code"]),
        None,
    )
    if variant is None:
        errors.append(f"L{line_no}: technical_variant_code inconnu: "
                      f"{row['technical_variant_code']!r}")
        return None, errors

    country_id = None
    iso = row.get("current_country_iso", "")
    if iso:
        country = next(
            (c for c in catalog_store.list_countries() if c.iso_alpha2 == iso.upper()),
            None,
        )
        if country is None:
            errors.append(f"L{line_no}: current_country_iso inconnu: {iso!r}")
            return None, errors
        country_id = country.country_id

    ecm_id = None
    ecm_code = row.get("current_ecm_provider_code", "")
    if ecm_code:
        ecm = next(
            (e for e in catalog_store.list_ecm_providers() if e.provider_code == ecm_code),
            None,
        )
        if ecm is None:
            errors.append(f"L{line_no}: current_ecm_provider_code inconnu: {ecm_code!r}")
            return None, errors
        ecm_id = ecm.ecm_provider_id

    # Si l'asset existe déjà, on garde son UUID pour que upsert le voie
    # comme un update (sinon FleetAsset génère un nouveau fleet_asset_id)
    existing = catalog_store.get_fleet_asset_by_asset_number(row["asset_number"])

    kwargs: dict[str, Any] = {
        "asset_number": row["asset_number"],
        "vehicle_registration_number": row["vehicle_registration_number"],
        "technical_variant_id": variant.technical_variant_id,
        "manufacturing_year": int(row["manufacturing_year"]),
        "commissioning_date": date.fromisoformat(row["commissioning_date"]),
        "ownership_status": OwnershipStatus(row["ownership_status"]),
        "operational_status": OperationalStatus(row["operational_status"]),
        "current_country_id": country_id,
        "current_mileage_km": float(row["current_mileage_km"]),
        "current_engine_hours": float(row["current_engine_hours"]),
        "current_ecm_provider_id": ecm_id,
        "notes": row.get("notes", ""),
    }
    if existing:
        kwargs["fleet_asset_id"] = existing.fleet_asset_id

    return FleetAsset(**kwargs), []


def import_fleet_csv(
    contents: str, catalog_store, *, dry_run: bool = True,
) -> ImportFleetResult:
    """Import principal : parse, valide, (optionnellement) applique.

    Dry-run : valide tout, rapporte, ne touche pas au store.
    Apply : si aucune ligne ne rejette, applique. Si une ligne rejette,
    rien n'est écrit (fail-fast) et on rapporte les erreurs.
    """
    result = ImportFleetResult(dry_run=dry_run)

    rows, header_errors = _parse_csv_rows(contents)
    result.errors.extend(header_errors)
    if header_errors:
        return result

    result.total_rows = len(rows)
    assets_to_upsert: list[tuple[FleetAsset, bool]] = []  # (asset, is_update)

    for idx, raw in enumerate(rows, start=2):  # L2 = 1ère ligne de données après header
        row = _normalize_row(raw)
        line_errors = _validate_row(row, idx)
        if line_errors:
            result.errors.extend(line_errors)
            result.rejected_rows += 1
            continue
        asset, resolve_errors = _resolve_row_to_asset(row, idx, catalog_store)
        if resolve_errors:
            result.errors.extend(resolve_errors)
            result.rejected_rows += 1
            continue
        is_update = catalog_store.get_fleet_asset_by_asset_number(
            row["asset_number"]) is not None
        assets_to_upsert.append((asset, is_update))
        result.valid_rows += 1

    if dry_run or result.rejected_rows > 0:
        return result

    # Apply : fail-fast dès la 1ère exception (le store est transactionnel
    # ligne à ligne, un échec partiel est possible — on le rapporte)
    try:
        for asset, is_update in assets_to_upsert:
            catalog_store.upsert_fleet_asset(asset)
            if is_update:
                result.updated += 1
            else:
                result.inserted += 1
        result.applied = True
    except Exception as e:
        result.errors.append(f"Échec en cours d'apply (après {result.inserted + result.updated} "
                             f"ligne(s) écrite(s)) : {type(e).__name__}: {e}")
        result.applied = False

    return result
