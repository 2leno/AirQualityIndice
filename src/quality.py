"""
Module de validation et rapport de qualite des donnees.

Audit de qualite :
- Valeurs manquantes (.isnull().sum())
- Doublons (.duplicated())
- Bornes physiques (outliers)
- Types attendus (.dtypes)

Utilisation :
    from src.quality import quality_report_stage, PHYSICAL_RANGES

    quality_report_stage("extract", df, PHYSICAL_RANGES)

    # Traitement...
    quality_report_stage("fact", fact)
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Bornes physiques pour les polluants Open-Meteo Air Quality API
# Valeur min: 0 (pas de concentration negative)
# Valeur max: largeure generique (situation extreme)
PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "european_aqi": (0.0, 500.0),
    "us_aqi": (0.0, 500.0),
    "pm2_5": (0.0, 2000.0),
    "pm10": (0.0, 5000.0),
    "nitrogen_dioxide": (0.0, 2000.0),
    "ozone": (0.0, 1000.0),
    "sulphur_dioxide": (0.0, 2000.0),
    "carbon_monoxide": (0.0, 50000.0),
}


def missing_values_report(df: pd.DataFrame) -> dict[str, int]:
    """Compte les valeurs manquantes par colonne (cf. Tsena T1)."""
    return df.isnull().sum().to_dict()


def duplicates_report(df: pd.DataFrame, subset: list[str] | None = None) -> int:
    """Compte le nombre de lignes dupliquees (cf. Tsena T1)."""
    return int(df.duplicated(subset=subset).sum())


def range_check(
    df: pd.DataFrame,
    ranges: dict[str, tuple[float, float]],
) -> dict[str, int]:
    """Verifie que les colonnes numeriques sont dans des bornes physiques.
    Retourne le nombre de valeurs hors bornes par colonne.
    """
    violations: dict[str, int] = {}
    for col, (low, high) in ranges.items():
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        out_of_range = ((df[col] < low) | (df[col] > high)).sum()
        if out_of_range > 0:
            violations[col] = int(out_of_range)
    return violations


def dtypes_check(
    df: pd.DataFrame,
    expected: dict[str, type],
) -> list[str]:
    """Verifie que les colonnes ont les types pandas attendus.
    Retourne la liste des colonnes dont le type ne correspond pas.
    """
    mismatches: list[str] = []
    for col, dtype in expected.items():
        if col not in df.columns:
            mismatches.append(f"{col}: colonne manquante")
        elif not isinstance(df[col].dtype, dtype) and df[col].dtype != dtype:
            mismatches.append(f"{col}: attendu {dtype}, obtenu {df[col].dtype}")
    return mismatches


def quality_report_stage(
    stage_name: str,
    df: pd.DataFrame,
    ranges: dict[str, tuple[float, float]] | None = None,
    subset_duplicates: list[str] | None = None,
    expected_dtypes: dict[str, type] | None = None,
) -> dict[str, Any]:
    """Produit un rapport de qualite formate pour une etape du pipeline.
    Loggue les resultats et les retourne sous forme de dict.

    Args:
        stage_name: nom de l'etape (ex: 'extract', 'raw', 'fact')
        df: DataFrame a valider
        ranges: bornes physiques optionnelles
        subset_duplicates: colonnes a verifier pour les doublons
        expected_dtypes: types attendus optionnels
    """
    report: dict[str, Any] = {
        "stage": stage_name,
        "rows": len(df),
        "columns": list(df.columns),
    }

    # Valeurs manquantes
    missing = missing_values_report(df)
    total_missing = sum(missing.values())
    report["missing_values"] = total_missing
    if total_missing > 0:
        details = {k: v for k, v in missing.items() if v > 0}
        report["missing_details"] = details
        logger.warning(
            "[Qualite][%s] %d valeur(s) manquante(s) : %s",
            stage_name,
            total_missing,
            details,
        )

    # Doublons
    dupes = duplicates_report(df, subset=subset_duplicates)
    report["duplicates"] = dupes
    if dupes > 0:
        logger.warning(
            "[Qualite][%s] %d ligne(s) dupliquee(s)",
            stage_name,
            dupes,
        )

    # Bornes physiques
    if ranges:
        violations = range_check(df, ranges)
        report["range_violations"] = violations
        total_violations = sum(violations.values())
        if total_violations > 0:
            logger.warning(
                "[Qualite][%s] %d valeur(s) hors bornes : %s",
                stage_name,
                total_violations,
                violations,
            )

    # Types
    if expected_dtypes:
        mismatches = dtypes_check(df, expected_dtypes)
        report["dtype_mismatches"] = mismatches
        if mismatches:
            logger.warning(
                "[Qualite][%s] %d type(s) incorrect(s) : %s",
                stage_name,
                len(mismatches),
                mismatches,
            )

    # Rapport synthetique
    logger.info(
        "[Qualite][%s] %d lignes, %d colonnes, %d manquantes, %d doublons%s",
        stage_name,
        len(df),
        len(df.columns),
        total_missing,
        dupes,
        f", {sum(violations.values())} hors bornes" if ranges else "",
    )

    return report
