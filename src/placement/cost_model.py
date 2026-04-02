"""Kosten-Nutzen-Modell für Sozialarbeiter-Standorte.

Berechnet Jahres- und Einmalkosten pro Standort auf Basis von:
- TVöD SuE S11b/S12 Personalkosten
- Mietkosten (öffentliches vs. privates Gebäude)
- Sachkosten und Einmalkosten

Alle Werte sind konfigurierbar via `kosten_params`-Dict oder Umgebungsvariablen.
"""

import logging
import os

import geopandas as gpd
import numpy as np

logger = logging.getLogger(__name__)

# Standardwerte gemäß CLAUDE.md § 6e
KOSTEN_DEFAULTS: dict[str, float] = {
    "personal_s11b_jahr": 60_000.0,
    "personal_s12_jahr": 65_000.0,
    "miete_oeffentlich_jahr": 3_000.0,
    "miete_privat_jahr": 12_000.0,
    "sachkosten_jahr": 5_000.0,
    "einmalkosten": 10_000.0,
}

# Standort-Typen, die als öffentliche Gebäude gelten (günstigere Miete)
_OEFFENTLICHE_TYPEN: frozenset[str] = frozenset(
    {
        "oeffentlich",
        "school",
        "kindergarten",
        "community_centre",
        "townhall",
        "library",
    }
)


def _lade_kosten_params(override: dict[str, float] | None) -> dict[str, float]:
    """Lädt Kostenparameter aus Defaults, Umgebungsvariablen und Overrides.

    Priorität: override > Umgebungsvariablen (KOSTEN_*) > KOSTEN_DEFAULTS.

    Args:
        override: Optionales Dict mit Überschreibungen.

    Returns:
        Vollständiges Kosten-Dict.
    """
    params = KOSTEN_DEFAULTS.copy()

    # Umgebungsvariablen überschreiben Defaults
    for key in params:
        env_key = f"KOSTEN_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            try:
                params[key] = float(env_val)
                logger.debug("Kostenparameter aus Umgebungsvariable: %s=%.0f", key, params[key])
            except ValueError:
                logger.warning("Ungültiger Wert für %s: %s", env_key, env_val)

    # Explizite Overrides haben höchste Priorität
    if override:
        for key, val in override.items():
            if key in params:
                params[key] = float(val)
            else:
                logger.warning("Unbekannter Kostenparameter: %s", key)

    return params


def berechne_kosten(
    standorte_gdf: gpd.GeoDataFrame,
    kosten_params: dict[str, float] | None = None,
) -> gpd.GeoDataFrame:
    """Berechnet Jahres- und Einmalkosten pro Standort.

    Öffentliche Gebäude (school, community_centre etc.) erhalten die günstigere
    Mietpauschale. Private Standorte die teurere. Der Personalkosten-Ansatz
    nutzt TVöD S11b als Standard.

    Args:
        standorte_gdf: Standorte mit Spalte `standort_typ` ('oeffentlich'/'privat').
            Falls nicht vorhanden, wird 'privat' angenommen.
        kosten_params: Optionale Überschreibungen für KOSTEN_DEFAULTS.

    Returns:
        GeoDataFrame mit zusätzlichen Spalten:
        - personalkosten_jahr
        - mietkosten_jahr
        - sachkosten_jahr
        - gesamtkosten_jahr
        - einmalkosten
        - kosten_pro_erreichtes_kind (falls `erreichte_kinder` vorhanden)
    """
    params = _lade_kosten_params(kosten_params)

    result = standorte_gdf.copy()

    # Standort-Typ normalisieren
    if "standort_typ" not in result.columns:
        result["standort_typ"] = "privat"
        logger.debug("Spalte 'standort_typ' fehlt — nehme 'privat' an")

    # Personalkosten (S11b als Standard)
    result["personalkosten_jahr"] = params["personal_s11b_jahr"]

    # Mietkosten nach Typ
    ist_oeffentlich = result["standort_typ"].isin(_OEFFENTLICHE_TYPEN)
    result["mietkosten_jahr"] = np.where(
        ist_oeffentlich,
        params["miete_oeffentlich_jahr"],
        params["miete_privat_jahr"],
    )

    result["sachkosten_jahr"] = params["sachkosten_jahr"]
    result["einmalkosten"] = params["einmalkosten"]

    result["gesamtkosten_jahr"] = (
        result["personalkosten_jahr"]
        + result["mietkosten_jahr"]
        + result["sachkosten_jahr"]
    )

    # Kosten pro erreichtes Kind (falls impact bereits berechnet)
    if "erreichte_kinder" in result.columns:
        kinder = result["erreichte_kinder"].replace(0, np.nan)
        result["kosten_pro_erreichtes_kind"] = (
            result["gesamtkosten_jahr"] / kinder
        ).round(0)
    else:
        result["kosten_pro_erreichtes_kind"] = np.nan

    logger.info(
        "Kosten berechnet: %d Standorte | ø Gesamtkosten/Jahr: %.0f € | "
        "öffentlich: %d, privat: %d",
        len(result),
        result["gesamtkosten_jahr"].mean() if len(result) > 0 else 0,
        int(ist_oeffentlich.sum()),
        int((~ist_oeffentlich).sum()),
    )

    return result
