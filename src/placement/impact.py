"""Wirkungsbereich und Reichweite pro Sozialarbeiter-Standort.

Für jeden Standort (bestehend + empfohlen) werden berechnet:
- Liste der Straßenabschnitte im Wirkungsradius
- Erreichte Kinderzahl
- Abgedeckter unversorgter Bedarf (mit Distanz-Decay)
- Wirkungskreis-Geometrie (Buffer in UTM32N, reprojiziert nach WGS84)
"""

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely.geometry as sgeom
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)

UTM32N = "EPSG:25832"
WGS84 = "EPSG:4326"


def _segment_centroids_utm(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Berechnet UTM32N-Zentroiden der Segment-Geometrien.

    Args:
        gdf: Straßenabschnitte (LineString, beliebiges CRS).

    Returns:
        (N, 2) float64-Array [x, y] in EPSG:25832.
    """
    gdf_utm = gdf.to_crs(UTM32N)
    centroids = gdf_utm.geometry.centroid
    return np.column_stack([centroids.x.values, centroids.y.values])


def _standorte_coords_utm(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Extrahiert UTM32N-Koordinaten der Standort-Point-Geometrien.

    Args:
        gdf: Standorte-GeoDataFrame (Point, beliebiges CRS).

    Returns:
        (M, 2) float64-Array [x, y] in EPSG:25832.
    """
    gdf_utm = gdf.to_crs(UTM32N)
    return np.column_stack([gdf_utm.geometry.x.values, gdf_utm.geometry.y.values])


def berechne_wirkung(
    standorte_gdf: gpd.GeoDataFrame,
    bedarf_gdf: gpd.GeoDataFrame,
    radius_m: float = 800.0,
    walking_factor: float = 1.4,
) -> gpd.GeoDataFrame:
    """Berechnet Wirkungsbereich und Reichweite pro Standort.

    Args:
        standorte_gdf: Standorte (bestehend + empfohlen), Point-Geometrien.
        bedarf_gdf: Straßenabschnitte mit `kinder` und `bedarf_unversorgt`.
        radius_m: Nominaler Wirkungsradius in Meter (Gehwegäquivalent).
        walking_factor: Faktor Luftlinie → Gehweg.

    Returns:
        GeoDataFrame mit allen Standort-Spalten plus:
        - n_segmente_im_radius (int)
        - erreichte_kinder (float)
        - abgedeckter_bedarf (float, mit Distanz-Decay)
        - wirkungskreis (Polygon, WGS84 – Buffer in UTM32N, rückprojiziert)
        Geometrie: Point, EPSG:4326.
    """
    if len(standorte_gdf) == 0:
        logger.warning("Keine Standorte übergeben — leeres Ergebnis")
        return standorte_gdf.copy()

    effektiver_radius = radius_m / walking_factor

    seg_coords = _segment_centroids_utm(bedarf_gdf)   # (N, 2)
    stand_coords = _standorte_coords_utm(standorte_gdf)  # (M, 2)

    # Distanzmatrix Segmente × Standorte (N × M), Luftlinie in Meter
    dist = cdist(seg_coords, stand_coords, metric="euclidean")  # (N, M)

    kinder_arr = bedarf_gdf["kinder"].fillna(0.0).values
    bedarf_arr = bedarf_gdf["bedarf_unversorgt"].fillna(0.0).values

    # Decay-Matrix: linear 1 → 0 über effektiven Radius
    decay = np.clip(1.0 - dist / effektiver_radius, 0.0, 1.0)  # (N, M)

    n_segmente = []
    erreichte_kinder_list = []
    abgedeckter_bedarf_list = []
    wirkungskreise = []

    standorte_utm = standorte_gdf.to_crs(UTM32N)

    for m_idx in range(len(standorte_gdf)):
        im_radius = dist[:, m_idx] <= effektiver_radius

        n_segmente.append(int(im_radius.sum()))
        erreichte_kinder_list.append(float(kinder_arr[im_radius].sum()))
        abgedeckter_bedarf_list.append(float((bedarf_arr * decay[:, m_idx]).sum()))

        # Wirkungskreis: Buffer in UTM32N (Meter), dann WGS84
        punkt_utm = standorte_utm.geometry.iloc[m_idx]
        kreis_utm = punkt_utm.buffer(effektiver_radius)
        # Rück-Transformation via shapely + pyproj
        from pyproj import Transformer
        transformer = Transformer.from_crs(UTM32N, WGS84, always_xy=True)
        kreis_wgs84 = _transform_polygon(kreis_utm, transformer)
        wirkungskreise.append(kreis_wgs84)

    result = standorte_gdf.copy().to_crs(WGS84)
    result["n_segmente_im_radius"] = n_segmente
    result["erreichte_kinder"] = np.round(erreichte_kinder_list, 1)
    result["abgedeckter_bedarf"] = np.round(abgedeckter_bedarf_list, 2)
    result["wirkungskreis"] = wirkungskreise

    logger.info(
        "Wirkung berechnet: %d Standorte, ø %.0f Segmente/Standort, "
        "ø %.0f Kinder/Standort",
        len(result),
        np.mean(n_segmente) if n_segmente else 0,
        np.mean(erreichte_kinder_list) if erreichte_kinder_list else 0,
    )

    return result


def _transform_polygon(polygon: sgeom.Polygon, transformer) -> sgeom.Polygon:
    """Transformiert ein Shapely-Polygon mit einem pyproj-Transformer.

    Args:
        polygon: Shapely-Polygon in Quell-CRS.
        transformer: pyproj.Transformer (always_xy=True).

    Returns:
        Transformiertes Shapely-Polygon.
    """
    xx, yy = polygon.exterior.coords.xy
    x_out, y_out = transformer.transform(list(xx), list(yy))
    exterior_transformed = list(zip(x_out, y_out))

    interiors = []
    for interior in polygon.interiors:
        xi, yi = interior.coords.xy
        xi_out, yi_out = transformer.transform(list(xi), list(yi))
        interiors.append(list(zip(xi_out, yi_out)))

    return sgeom.Polygon(exterior_transformed, interiors)
