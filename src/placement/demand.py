"""Bedarfsberechnung pro Straßenabschnitt.

Der unversorgte Bedarf ergibt sich aus:
    bedarf = (aufwachsindex_gesamt / 100) * einwohner_kinder_0_17

Bestehende Einrichtungen reduzieren den Bedarf ihrer Umgebung über einen
linearen Distanz-Decay innerhalb des Wirkungsradius (Standard: 800 m
Gehwegäquivalent, approximiert als Luftlinie × WALKING_FACTOR=1.4).
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)

WALKING_FACTOR = 1.4  # Luftlinie → Gehwegdistanz-Approximation (Stuttgart hilly)
UTM32N = "EPSG:25832"
WGS84 = "EPSG:4326"


def _segmente_centroids_utm(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Berechnet UTM32N-Zentroiden der Straßenabschnitt-Geometrien.

    Args:
        gdf: Straßenabschnitte in beliebigem CRS.

    Returns:
        (N, 2) float64-Array mit [x, y] in EPSG:25832 (Meter).
    """
    gdf_utm = gdf.to_crs(UTM32N)
    centroids = gdf_utm.geometry.centroid
    return np.column_stack([centroids.x.values, centroids.y.values])


def _einrichtungen_coords_utm(bestand_gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Extrahiert UTM32N-Koordinaten der Einrichtungen.

    Args:
        bestand_gdf: Bestehende Sozialeinrichtungen (Point-Geometrien).

    Returns:
        (M, 2) float64-Array mit [x, y] in EPSG:25832.
    """
    gdf_utm = bestand_gdf.to_crs(UTM32N)
    return np.column_stack([gdf_utm.geometry.x.values, gdf_utm.geometry.y.values])


def berechne_bedarf(
    index_path: Path,
    kinder_path: Path,
    bestand_gdf: gpd.GeoDataFrame,
    radius_m: float = 800.0,
    walking_factor: float = WALKING_FACTOR,
) -> gpd.GeoDataFrame:
    """Berechnet den unversorgten Bedarf pro Straßenabschnitt.

    Der Rohbedarf ist proportional zu Aufwachsindex × Kinderzahl.
    Segmente im Wirkungsradius bestehender Einrichtungen haben reduzierten
    Bedarf (linearer Decay von 1.0 an der Einrichtung bis 0.0 am Radius).

    Args:
        index_path: Pfad zu `aufwachsindex.geojson` mit `aufwachsindex_gesamt`.
        kinder_path: Pfad zu `einwohner_kinder.parquet` mit
            `segment_id`, `jahr`, `einwohner_kinder_0_17`.
        bestand_gdf: Bestehende Sozialeinrichtungen (Point, beliebiges CRS).
        radius_m: Wirkungsradius in Meter (Luftlinie × walking_factor).
        walking_factor: Multiplikator Luftlinie → Gehwegäquivalent.

    Returns:
        GeoDataFrame der Straßenabschnitte mit zusätzlichen Spalten:
        - kinder (einwohner_kinder_0_17)
        - bedarf_roh (index/100 * kinder)
        - versorgungsgrad (0.0–1.0, Anteil abgedeckt durch Bestand)
        - bedarf_unversorgt (bedarf_roh * (1 - versorgungsgrad))
        Geometrie: LineString, EPSG:4326.

    Raises:
        FileNotFoundError: Wenn eine Eingabedatei fehlt.
    """
    if not index_path.exists():
        raise FileNotFoundError(f"aufwachsindex.geojson nicht gefunden: {index_path}")
    if not kinder_path.exists():
        raise FileNotFoundError(f"einwohner_kinder.parquet nicht gefunden: {kinder_path}")

    logger.info("Lade Aufwachsindex aus %s", index_path.name)
    idx_gdf = gpd.read_file(index_path)
    if idx_gdf.crs is None:
        idx_gdf = idx_gdf.set_crs(WGS84)
    else:
        idx_gdf = idx_gdf.to_crs(WGS84)

    logger.info("  %d Segmente geladen", len(idx_gdf))

    # Einwohner-Kinder laden (aktuellstes Jahr)
    logger.info("Lade Kinder-Einwohner aus %s", kinder_path.name)
    kinder_df = pd.read_parquet(kinder_path)
    if "jahr" in kinder_df.columns:
        letztes_jahr = kinder_df["jahr"].dropna().max()
        kinder_df = kinder_df[kinder_df["jahr"] == letztes_jahr]
        logger.info("  Nutze Jahr %d", letztes_jahr)

    kinder_serie = (
        kinder_df.groupby("segment_id")["einwohner_kinder_0_17"]
        .mean()
    )

    # Kinder auf Index-Segmente joinen
    idx_gdf["kinder"] = kinder_serie.reindex(idx_gdf["segment_id"]).fillna(0.0).values

    # Rohbedarf
    index_wert = idx_gdf["aufwachsindex_gesamt"].fillna(0.0)
    idx_gdf["bedarf_roh"] = (index_wert / 100.0) * idx_gdf["kinder"]

    logger.info(
        "Rohbedarf: sum=%.0f  max=%.1f  median=%.1f",
        idx_gdf["bedarf_roh"].sum(),
        idx_gdf["bedarf_roh"].max(),
        idx_gdf["bedarf_roh"].median(),
    )

    # Versorgungsgrad durch bestehende Einrichtungen
    if len(bestand_gdf) == 0:
        logger.warning("Kein Bestand — Versorgungsgrad = 0 überall")
        idx_gdf["versorgungsgrad"] = 0.0
    else:
        idx_gdf["versorgungsgrad"] = _berechne_versorgungsgrad(
            idx_gdf, bestand_gdf, radius_m, walking_factor
        )

    idx_gdf["bedarf_unversorgt"] = (
        idx_gdf["bedarf_roh"] * (1.0 - idx_gdf["versorgungsgrad"])
    ).clip(lower=0.0)

    logger.info(
        "Unversorgter Bedarf: sum=%.0f  (%.1f%% des Rohbedarfs)",
        idx_gdf["bedarf_unversorgt"].sum(),
        100.0 * idx_gdf["bedarf_unversorgt"].sum() / max(idx_gdf["bedarf_roh"].sum(), 1e-9),
    )

    return idx_gdf


def _berechne_versorgungsgrad(
    idx_gdf: gpd.GeoDataFrame,
    bestand_gdf: gpd.GeoDataFrame,
    radius_m: float,
    walking_factor: float,
) -> pd.Series:
    """Berechnet den Versorgungsgrad pro Segment (0.0–1.0).

    Verwendet scipy.spatial.distance.cdist auf UTM32N-Koordinaten.
    Distanz-Decay: linear von 1.0 bei d=0 bis 0.0 bei d=effektiver_radius.

    Args:
        idx_gdf: Aufwachsindex-Segmente.
        bestand_gdf: Bestehende Einrichtungen.
        radius_m: Nominaler Radius in Meter (Luftlinie × walking_factor = Gehweg).
        walking_factor: Faktor Luftlinie → Gehweg.

    Returns:
        Series mit Versorgungsgrad pro Segment (Index = positional, wie idx_gdf).
    """
    # Effektiver Luftlinien-Radius
    effektiver_radius = radius_m / walking_factor

    seg_coords = _segmente_centroids_utm(idx_gdf)    # (N, 2)
    einr_coords = _einrichtungen_coords_utm(bestand_gdf)  # (M, 2)

    logger.debug(
        "Distanzmatrix %d Segmente × %d Einrichtungen (radius_luftlinie=%.0f m)",
        len(seg_coords),
        len(einr_coords),
        effektiver_radius,
    )

    # Distanzmatrix (N × M), Meter
    dist_matrix = cdist(seg_coords, einr_coords, metric="euclidean")

    # Linearer Decay pro Einrichtung: 1 - d/r, geclipt auf [0, 1]
    decay = np.clip(1.0 - dist_matrix / effektiver_radius, 0.0, 1.0)

    # Maximaler Versorgungsgrad über alle Einrichtungen (nicht addieren — eine Einrichtung reicht)
    versorgungsgrad = decay.max(axis=1)

    return pd.Series(versorgungsgrad, name="versorgungsgrad")
