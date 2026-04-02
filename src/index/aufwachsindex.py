"""Berechnung des Aufwachsindex: Normalisierung, Aggregation, Gewichtung.

Pipeline:
1. Lade disaggregierte Parquet-Daten (aktuellstes verfügbares Jahr pro Indikator)
2. Berechne abgeleitete Raten (per_kinder, per_laenge)
3. Min-Max-Normalisierung auf [0, 1] innerhalb Stuttgarts (1 = schlecht)
4. Gewichtete Aggregation zu Dimensions-Scores
5. Gewichteter Gesamt-Index (0–100)
6. Konfidenz-Aggregation
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .dimensions import DIMENSIONEN, DimensionDef, IndikatorDef, Methode

logger = logging.getLogger(__name__)

REFERENZJAHR = 2022  # Bevorzugtes Referenzjahr; Fallback auf aktuellstes verfügbares
MIN_KINDER_THRESHOLD = 1.0  # Segmente mit < 1 Kind → NaN für per_kinder-Indikatoren


def _lade_indikator(
    disagg_dir: Path,
    ind: IndikatorDef,
    einwohner_df: pd.DataFrame,
    segmente_df: pd.DataFrame,
) -> pd.Series:
    """Lädt einen Indikator und berechnet den normalisierten [0,1]-Score.

    Args:
        disagg_dir: Verzeichnis mit disaggregierten Parquet-Dateien.
        ind: Indikator-Definition.
        einwohner_df: Einwohner-Kinder pro Segment (für per_kinder).
        segmente_df: Straßenabschnitte mit 'laenge_m' (für per_laenge).

    Returns:
        Series mit normalisiertem Score [0,1] per segment_id, NaN wo keine Daten.
    """
    path = disagg_dir / f"{ind.datensatz}.parquet"
    if not path.exists():
        # Fallback: data/processed/ für direkte Segment-Daten (GTFS, POI-Erreichbarkeit)
        alt_path = disagg_dir.parent / "processed" / f"{ind.datensatz}.parquet"
        if alt_path.exists():
            path = alt_path
        else:
            logger.warning("Datensatz nicht gefunden: %s — überspringe", path.name)
            return pd.Series(dtype=float)

    df = pd.read_parquet(path)

    # Aktuellstes verfügbares Jahr wählen
    if "jahr" in df.columns:
        verfuegbare_jahre = sorted(df["jahr"].dropna().unique())
        jahr = REFERENZJAHR if REFERENZJAHR in verfuegbare_jahre else max(verfuegbare_jahre)
        if jahr != REFERENZJAHR:
            logger.info(
                "  %s: Referenzjahr %d nicht verfügbar, nutze %d",
                ind.datensatz, REFERENZJAHR, jahr,
            )
        df = df[df["jahr"] == jahr]

    if ind.spalte not in df.columns:
        logger.warning("Spalte '%s' nicht in %s", ind.spalte, ind.datensatz)
        return pd.Series(dtype=float)

    # Einen Wert pro Segment
    serie = df.groupby("segment_id")[ind.spalte].mean()

    # Rate berechnen
    if ind.methode == "per_kinder":
        kinder = einwohner_df.reindex(serie.index)
        mask = kinder >= MIN_KINDER_THRESHOLD
        serie = (serie / kinder).where(mask)
    elif ind.methode == "per_laenge":
        laenge = segmente_df["laenge_m"].reindex(serie.index)
        serie = serie / laenge.replace(0, np.nan) * 100  # Pro 100m

    # Min-Max-Normalisierung [0, 1]
    vmin, vmax = serie.quantile(0.02), serie.quantile(0.98)  # Robuste Grenzen
    if vmax == vmin:
        logger.warning("  %s: Keine Varianz — setze auf 0.5", ind.label)
        return pd.Series(0.5, index=serie.index)

    normalized = (serie - vmin) / (vmax - vmin)
    normalized = normalized.clip(0, 1)

    # Richtung: higher_better → invertieren
    if ind.richtung == "higher_better":
        normalized = 1 - normalized

    logger.info(
        "  %-35s  Median=%.3f  NaN=%d%%",
        ind.label,
        normalized.median(),
        int(normalized.isna().mean() * 100),
    )
    return normalized


def berechne_dimension_score(
    scores: dict[str, pd.Series],
    dim: DimensionDef,
) -> pd.Series:
    """Berechnet den gewichteten Dimensions-Score aus Einzel-Indikatoren.

    Args:
        scores: Indikator-Key → normalisierter Score.
        dim: Dimensions-Definition mit Indikatoren und Gewichten.

    Returns:
        Gewichteter Dimensions-Score [0,1] pro segment_id.
    """
    teil_scores: list[pd.Series] = []
    teil_gewichte: list[float] = []

    for ind in dim.indikatoren:
        key = f"{ind.datensatz}__{ind.spalte}"
        if key not in scores or scores[key].empty:
            logger.warning("  Indikator fehlt: %s — überspringe in Dimension %s", ind.label, dim.key)
            continue
        teil_scores.append(scores[key])
        teil_gewichte.append(ind.gewicht)

    if not teil_scores:
        return pd.Series(dtype=float)

    # Normalisiere Gewichte auf 1.0
    gewichte_sum = sum(teil_gewichte)
    norm_gewichte = [g / gewichte_sum for g in teil_gewichte]

    # Gewichteter Durchschnitt (NaN-robust: ignoriere fehlende Indikatoren)
    df = pd.concat(teil_scores, axis=1, keys=range(len(teil_scores)))
    gewichte_arr = np.array(norm_gewichte)

    # Pro Zeile: gewichteter Durchschnitt nur der nicht-NaN Werte
    def _weighted_mean(row: pd.Series) -> float:
        valid = ~row.isna()
        if not valid.any():
            return np.nan
        w = gewichte_arr[valid.values]
        return float((row[valid].values * w).sum() / w.sum())

    return df.apply(_weighted_mean, axis=1)


def berechne_aufwachsindex(
    disagg_dir: Path,
    segmente: gpd.GeoDataFrame,
    referenzjahr: int = REFERENZJAHR,
) -> gpd.GeoDataFrame:
    """Berechnet den vollständigen Aufwachsindex für alle Straßenabschnitte.

    Args:
        disagg_dir: Verzeichnis mit disaggregierten Parquet-Dateien.
        segmente: Straßenabschnitte-GeoDataFrame.
        referenzjahr: Bevorzugtes Referenzjahr.

    Returns:
        GeoDataFrame mit Spalten:
        - aufwachsindex_gesamt (0–100, höher = schlechter)
        - dim_{key} (0–100) pro Dimension
        - n_dimensionen_verfuegbar
        - konfidenz_gesamt
    """
    global REFERENZJAHR
    REFERENZJAHR = referenzjahr

    # Segment-Lookup für Gewichts-Berechnungen
    seg_df = segmente.set_index("segment_id")[["laenge_m", "bezirk"]]

    # Einwohner-Kinder als Nenner für per_kinder-Indikatoren
    kinder_path = disagg_dir / "einwohner_kinder.parquet"
    if kinder_path.exists():
        kinder_df = pd.read_parquet(kinder_path)
        kinder_jahre = sorted(kinder_df["jahr"].dropna().unique())
        kinder_jahr = REFERENZJAHR if REFERENZJAHR in kinder_jahre else max(kinder_jahre)
        einwohner_serie = (
            kinder_df[kinder_df["jahr"] == kinder_jahr]
            .groupby("segment_id")["einwohner_kinder_0_17"]
            .mean()
        )
    else:
        logger.warning("einwohner_kinder.parquet fehlt — per_kinder-Indikatoren deaktiviert")
        einwohner_serie = pd.Series(dtype=float)

    # Alle Indikatoren laden und normalisieren
    logger.info("Lade und normalisiere Indikatoren...")
    alle_scores: dict[str, pd.Series] = {}
    for dim in DIMENSIONEN:
        for ind in dim.indikatoren:
            key = f"{ind.datensatz}__{ind.spalte}"
            alle_scores[key] = _lade_indikator(
                disagg_dir, ind, einwohner_serie, seg_df
            )

    # Dimensions-Scores berechnen
    logger.info("Berechne Dimensions-Scores...")
    dim_scores: dict[str, pd.Series] = {}
    dim_gewichte: dict[str, float] = {}

    for dim in DIMENSIONEN:
        score = berechne_dimension_score(alle_scores, dim)
        if score.empty or score.isna().all():
            logger.warning("Dimension '%s' hat keine Daten — wird ausgelassen", dim.key)
            continue
        dim_scores[dim.key] = score
        dim_gewichte[dim.key] = dim.gewicht

    if not dim_scores:
        raise RuntimeError("Keine Dimensions-Daten verfügbar — Index kann nicht berechnet werden")

    # Gesamt-Index: gewichteter Durchschnitt der Dimensionen (auf verfügbare skalieren)
    logger.info("Berechne Gesamt-Index...")
    gesamt_gewichte_sum = sum(dim_gewichte.values())
    norm_dim_gewichte = {k: v / gesamt_gewichte_sum for k, v in dim_gewichte.items()}

    dim_df = pd.concat(dim_scores, axis=1)

    def _gesamt_score(row: pd.Series) -> float:
        valid = ~row.isna()
        if not valid.any():
            return np.nan
        w = np.array([norm_dim_gewichte[k] for k in row.index[valid]])
        return float((row[valid].values * w).sum() / w.sum())

    gesamt = dim_df.apply(_gesamt_score, axis=1)

    # Ergebnis-GeoDataFrame aufbauen
    result = segmente.copy()

    for dim_key, score in dim_scores.items():
        col = f"dim_{dim_key}"
        result[col] = (score.reindex(result["segment_id"]).values * 100).round(1)

    result["aufwachsindex_gesamt"] = (
        gesamt.reindex(result["segment_id"]).values * 100
    ).round(1)

    result["n_dimensionen_verfuegbar"] = (
        dim_df.reindex(result["segment_id"]).notna().sum(axis=1).values
    )

    # Konfidenz-Score: Anteil der Segmente mit vollständigen Daten
    result["konfidenz_gesamt"] = (
        dim_df.reindex(result["segment_id"]).notna().mean(axis=1).values.round(2)
    )

    logger.info(
        "Aufwachsindex berechnet: %d Segmente, %d Dimensionen, "
        "%.1f%% mit vollständigen Daten",
        len(result),
        len(dim_scores),
        (result["konfidenz_gesamt"] == 1.0).mean() * 100,
    )
    return result
