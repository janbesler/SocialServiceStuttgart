"""Erreichbarkeit von ÖPNV-Haltestellen und POIs pro Straßenabschnitt berechnen.

Für jeden Straßenabschnitt (Zentroid) werden folgende Distanzen ermittelt:
  - Nächste ÖPNV-Haltestelle (aus GTFS stops.txt)
  - Anzahl Haltestellen innerhalb 500m / 1000m
  - Nächste Schule, Kita, Spielplatz, Sportstätte, Arzt/Klinik (aus OSM POIs)

Alle Distanzen werden in Metern angegeben (EPSG:25832 UTM32N-Projektion).
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

logger = logging.getLogger(__name__)

# Stuttgart Bounding Box (WGS84) für GTFS-Filterung
STUTTGART_LAT_MIN: float = 48.69
STUTTGART_LAT_MAX: float = 48.87
STUTTGART_LON_MIN: float = 9.04
STUTTGART_LON_MAX: float = 9.32

# Projektions-EPSG für metrische Distanzen
CRS_UTM: str = "EPSG:25832"
CRS_WGS84: str = "EPSG:4326"

# Konfidenz-Metadaten
_KONFIDENZ_GEMESSEN: str = "gemessen"
_METHODE_NEAREST: str = "nearest_distance"
_QUELLDATENSATZ_GTFS: str = "gtfs_stops"
_QUELLDATENSATZ_OSM: str = "osm_pois"


def _load_gtfs_stops(gtfs_dir: Path) -> gpd.GeoDataFrame:
    """GTFS stops.txt einlesen und auf Stuttgart filtern.

    Liest die stops.txt-Datei (kommagetrennt), filtert auf tatsächliche
    Haltestellen (location_type == 0 oder leer) und auf die Stuttgarter
    Bounding Box.

    Args:
        gtfs_dir: Verzeichnis mit GTFS-Dateien (muss stops.txt enthalten).

    Returns:
        GeoDataFrame mit Haltestellen-Punkten in EPSG:4326.

    Raises:
        FileNotFoundError: Wenn stops.txt nicht gefunden wird.
    """
    stops_path = gtfs_dir / "stops.txt"
    if not stops_path.exists():
        raise FileNotFoundError(f"stops.txt nicht gefunden: {stops_path}")

    df = pd.read_csv(
        stops_path,
        sep=",",
        dtype={"stop_id": str, "location_type": str},
        encoding="utf-8-sig",  # BOM tolerant
    )
    logger.debug("stops.txt gelesen: %d Zeilen total", len(df))

    # Nur echte Haltestellen (location_type == 0 oder leer / NaN)
    mask_type = df["location_type"].isna() | df["location_type"].isin(["", "0"])
    df = df[mask_type].copy()

    # Koordinaten in Float konvertieren, ungültige Werte verwerfen
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_lat", "stop_lon"])

    # Bounding-Box-Filter Stuttgart
    mask_bbox = (
        (df["stop_lat"] >= STUTTGART_LAT_MIN)
        & (df["stop_lat"] <= STUTTGART_LAT_MAX)
        & (df["stop_lon"] >= STUTTGART_LON_MIN)
        & (df["stop_lon"] <= STUTTGART_LON_MAX)
    )
    df = df[mask_bbox].copy()

    geometry = [Point(lon, lat) for lon, lat in zip(df["stop_lon"], df["stop_lat"])]
    gdf = gpd.GeoDataFrame(df[["stop_id", "stop_name"]], geometry=geometry, crs=CRS_WGS84)

    logger.info("%d Haltestellen geladen (nach Filter auf Stuttgart)", len(gdf))
    return gdf


def _load_pois(pois_path: Path) -> gpd.GeoDataFrame:
    """POI-GeoDataFrame einlesen.

    Args:
        pois_path: Pfad zur pois.geojson-Datei.

    Returns:
        GeoDataFrame mit POIs in EPSG:4326.

    Raises:
        FileNotFoundError: Wenn die POI-Datei nicht gefunden wird.
    """
    if not pois_path.exists():
        raise FileNotFoundError(f"POI-Datei nicht gefunden: {pois_path}")

    gdf = gpd.read_file(pois_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(CRS_WGS84)

    # Leere Strings in den Kategoriespalten zu NaN normalisieren
    for col in ("amenity", "leisure", "public_transport"):
        if col in gdf.columns:
            gdf[col] = gdf[col].replace("", pd.NA)

    logger.info("%d POIs geladen", len(gdf))
    return gdf


def _segment_centroids_utm(segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Segment-Zentroide in UTM32N berechnen.

    Args:
        segments: Straßenabschnitte in beliebigem CRS.

    Returns:
        GeoDataFrame mit Punkt-Geometrien (Zentroide) in EPSG:25832.
    """
    utm = segments.to_crs(CRS_UTM).copy()
    utm["geometry"] = utm["geometry"].centroid
    return utm


def _build_kdtree(gdf_utm: gpd.GeoDataFrame) -> tuple[cKDTree, np.ndarray]:
    """cKDTree aus UTM-projizierten Punkten aufbauen.

    Args:
        gdf_utm: GeoDataFrame mit Punkt-Geometrien in EPSG:25832.

    Returns:
        Tupel (cKDTree, coords_array) wobei coords_array shape (N, 2) hat.
    """
    coords = np.column_stack([gdf_utm.geometry.x, gdf_utm.geometry.y])
    tree = cKDTree(coords)
    return tree, coords


def _nearest_distance(
    query_coords: np.ndarray,
    tree: cKDTree,
) -> np.ndarray:
    """Distanz zum nächsten Punkt im KD-Tree abfragen.

    Args:
        query_coords: Array (N, 2) mit Abfrage-Koordinaten in Metern.
        tree: cKDTree der Ziel-Punkte.

    Returns:
        Array (N,) mit Distanzen in Metern. NaN wenn tree leer ist.
    """
    if tree.n == 0:
        return np.full(len(query_coords), np.nan)
    distances, _ = tree.query(query_coords, k=1, workers=-1)
    return distances.astype(float)


def _count_within_radius(
    query_coords: np.ndarray,
    tree: cKDTree,
    radius_m: float,
) -> np.ndarray:
    """Anzahl Punkte innerhalb eines Radius für jede Abfragekoordinate.

    Args:
        query_coords: Array (N, 2) mit Abfrage-Koordinaten in Metern.
        tree: cKDTree der Ziel-Punkte.
        radius_m: Radius in Metern.

    Returns:
        Array (N,) mit ganzzahligen Anzahlen.
    """
    if tree.n == 0:
        return np.zeros(len(query_coords), dtype=int)
    counts = tree.query_ball_point(query_coords, r=radius_m, return_length=True)
    return np.asarray(counts, dtype=int)


def compute_transit_accessibility(
    segments: gpd.GeoDataFrame,
    gtfs_dir: Path,
) -> pd.DataFrame:
    """ÖPNV-Erreichbarkeit (Distanz zur nächsten Haltestelle) berechnen.

    Für jeden Straßenabschnitt wird der Zentroid berechnet und die Distanz
    zur nächsten GTFS-Haltestelle innerhalb Stuttgarts ermittelt. Zusätzlich
    werden Haltestellenzahlen innerhalb 500m und 1000m ausgewiesen.

    Args:
        segments: Straßenabschnitte-GeoDataFrame mit Spalte ``segment_id``.
        gtfs_dir: Verzeichnis mit GTFS-Dateien (stops.txt).

    Returns:
        DataFrame mit Spalten:
            - ``segment_id``
            - ``nearest_stop_dist_m``
            - ``stops_within_500m``
            - ``stops_within_1000m``
            - ``__konfidenz``
            - ``__methode``
            - ``__quelldatensatz``
    """
    stops = _load_gtfs_stops(gtfs_dir)
    stops_utm = stops.to_crs(CRS_UTM)
    stop_tree, _ = _build_kdtree(stops_utm)

    centroids_utm = _segment_centroids_utm(segments)
    query_coords = np.column_stack(
        [centroids_utm.geometry.x, centroids_utm.geometry.y]
    )

    logger.info(
        "Berechne nächste ÖPNV-Haltestelle für %d Segmente...", len(query_coords)
    )

    nearest_dist = _nearest_distance(query_coords, stop_tree)
    within_500 = _count_within_radius(query_coords, stop_tree, radius_m=500.0)
    within_1000 = _count_within_radius(query_coords, stop_tree, radius_m=1000.0)

    result = pd.DataFrame(
        {
            "segment_id": segments["segment_id"].values,
            "nearest_stop_dist_m": nearest_dist,
            "stops_within_500m": within_500,
            "stops_within_1000m": within_1000,
            "__konfidenz": _KONFIDENZ_GEMESSEN,
            "__methode": _METHODE_NEAREST,
            "__quelldatensatz": _QUELLDATENSATZ_GTFS,
        }
    )
    return result


def compute_poi_accessibility(
    segments: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """POI-Erreichbarkeit (Distanz zur nächsten Einrichtung je Kategorie) berechnen.

    Für jeden Straßenabschnitt wird die Distanz zur nächsten Schule, Kita,
    Spielplatz, Sportstätte und Arzt/Klinik berechnet. Fehlende Kategorien
    (keine POIs vorhanden) ergeben NaN.

    Args:
        segments: Straßenabschnitte-GeoDataFrame mit Spalte ``segment_id``.
        pois: POI-GeoDataFrame mit Spalten ``amenity``, ``leisure``.

    Returns:
        DataFrame mit Spalten:
            - ``segment_id``
            - ``dist_nearest_schule_m``
            - ``dist_nearest_kita_m``
            - ``dist_nearest_spielplatz_m``
            - ``dist_nearest_sport_m``
            - ``dist_nearest_arzt_m``
            - ``__konfidenz``
            - ``__methode``
            - ``__quelldatensatz``
    """
    # POI-Kategorien: (Ausgabespalte, Filter-Lambda)
    poi_categories: list[tuple[str, pd.Series]] = []

    amenity_col = pois.get("amenity") if "amenity" in pois.columns else None
    leisure_col = pois.get("leisure") if "leisure" in pois.columns else None

    if amenity_col is not None:
        poi_categories.append(
            ("dist_nearest_schule_m", amenity_col == "school")
        )
        poi_categories.append(
            ("dist_nearest_kita_m", amenity_col == "kindergarten")
        )
        poi_categories.append(
            (
                "dist_nearest_arzt_m",
                amenity_col.isin(["doctors", "clinic"]),
            )
        )

    if leisure_col is not None:
        poi_categories.append(
            ("dist_nearest_spielplatz_m", leisure_col == "playground")
        )
        poi_categories.append(
            ("dist_nearest_sport_m", leisure_col == "sports_centre")
        )

    centroids_utm = _segment_centroids_utm(segments)
    query_coords = np.column_stack(
        [centroids_utm.geometry.x, centroids_utm.geometry.y]
    )
    n_segments = len(query_coords)

    result = pd.DataFrame({"segment_id": segments["segment_id"].values})

    expected_columns = [
        "dist_nearest_schule_m",
        "dist_nearest_kita_m",
        "dist_nearest_spielplatz_m",
        "dist_nearest_sport_m",
        "dist_nearest_arzt_m",
    ]

    computed_columns: set[str] = set()

    for col_name, mask in poi_categories:
        subset = pois[mask]
        if subset.empty:
            logger.warning(
                "Keine POIs für Kategorie '%s' gefunden — setze NaN.", col_name
            )
            result[col_name] = np.nan
            computed_columns.add(col_name)
            continue

        subset_utm = subset.to_crs(CRS_UTM)
        # Nur Punkt-Geometrien verwenden (Flächen-POIs auf Zentroid reduzieren)
        subset_utm = subset_utm.copy()
        subset_utm["geometry"] = subset_utm.geometry.centroid

        tree, _ = _build_kdtree(subset_utm)
        distances = _nearest_distance(query_coords, tree)
        result[col_name] = distances
        computed_columns.add(col_name)

        logger.info(
            "%-30s: %d POIs, mittlere Distanz %.0f m",
            col_name,
            len(subset),
            float(np.nanmean(distances)),
        )

    # Fehlende Spalten mit NaN auffüllen (falls Kategorie-Spalte nicht in GDF)
    for col_name in expected_columns:
        if col_name not in computed_columns:
            logger.warning(
                "Kategorie-Spalte nicht verfügbar, '%s' wird NaN.", col_name
            )
            result[col_name] = np.nan

    result["__konfidenz"] = _KONFIDENZ_GEMESSEN
    result["__methode"] = _METHODE_NEAREST
    result["__quelldatensatz"] = _QUELLDATENSATZ_OSM

    return result


def compute_accessibility(
    segments_path: Path,
    gtfs_dir: Path,
    pois_path: Path,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ÖPNV- und POI-Erreichbarkeit für alle Straßenabschnitte berechnen.

    Orchestriert die Berechnung der Transit- und POI-Erreichbarkeit und
    schreibt die Ergebnisse als Parquet-Dateien in das Ausgabeverzeichnis.

    Args:
        segments_path: Pfad zu strassenabschnitte.geojson.
        gtfs_dir: Verzeichnis mit GTFS-Dateien (stops.txt).
        pois_path: Pfad zu pois.geojson.
        output_dir: Ausgabeverzeichnis für Parquet-Dateien.

    Returns:
        Tupel (transit_df, poi_df) mit den berechneten DataFrames.

    Raises:
        FileNotFoundError: Wenn Eingabedateien nicht gefunden werden.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Lade Straßenabschnitte: %s", segments_path)
    segments = gpd.read_file(segments_path)
    logger.info("%d Straßenabschnitte geladen", len(segments))

    logger.info("Lade POIs: %s", pois_path)
    pois = _load_pois(pois_path)

    # --- ÖPNV-Erreichbarkeit ---
    logger.info("Berechne ÖPNV-Erreichbarkeit...")
    transit_df = compute_transit_accessibility(segments, gtfs_dir)
    transit_out = output_dir / "oepnv_erreichbarkeit.parquet"
    transit_df.to_parquet(transit_out, index=False)
    logger.info(
        "ÖPNV-Erreichbarkeit gespeichert: %s (%d Zeilen)", transit_out, len(transit_df)
    )

    # --- POI-Erreichbarkeit ---
    logger.info("Berechne POI-Erreichbarkeit...")
    poi_df = compute_poi_accessibility(segments, pois)
    poi_out = output_dir / "poi_erreichbarkeit.parquet"
    poi_df.to_parquet(poi_out, index=False)
    logger.info(
        "POI-Erreichbarkeit gespeichert: %s (%d Zeilen)", poi_out, len(poi_df)
    )

    return transit_df, poi_df


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # Standard-Pfade relativ zum Projektverzeichnis
    _project_root = Path(__file__).resolve().parents[2]
    _segments_path = _project_root / "data" / "osm" / "strassenabschnitte.geojson"
    _gtfs_dir = _project_root / "data" / "raw" / "gtfs_realtime"
    _pois_path = _project_root / "data" / "osm" / "pois.geojson"
    _output_dir = _project_root / "data" / "processed"

    compute_accessibility(
        segments_path=_segments_path,
        gtfs_dir=_gtfs_dir,
        pois_path=_pois_path,
        output_dir=_output_dir,
    )
