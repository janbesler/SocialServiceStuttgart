"""Straßen an Hauptkreuzungen aufteilen und auf Bezirke mappen.

Algorithmus:
1. Lade Straßen-LineStrings aus OSM
2. Identifiziere "große Kreuzungen" (primary/secondary Schnittpunkte)
3. Splitte jeden LineString an diesen Punkten
4. Weise Stadtbezirk + Stadtteil zu (spatial join)
5. Berechne Länge, Gebäude-Anzahl im Puffer, Bevölkerung (Zensus)
"""

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import split, snap, unary_union

logger = logging.getLogger(__name__)

CRS_WGS84 = "EPSG:4326"
CRS_UTM32 = "EPSG:25832"

# Straßenklassen die "große Kreuzungen" definieren
HAUPTSTRASSEN_KLASSEN = {"primary", "secondary", "primary_link", "secondary_link"}
# Straßenklassen die gesplittet werden
ALLE_STRASSEN_KLASSEN = {"primary", "secondary", "tertiary", "residential",
                          "primary_link", "secondary_link", "tertiary_link"}

GEBAEUDE_PUFFER_M = 50  # Meter Puffer um Straßenabschnitt für Gebäude-Zählung
SPLIT_TOLERANCE_M = 5   # Meter Snap-Toleranz für Kreuzungs-Erkennung


def split_streets(
    strassen_gdf: gpd.GeoDataFrame,
    bezirke_gdf: gpd.GeoDataFrame,
    stadtteile_gdf: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Splittet Straßen-LineStrings an Hauptkreuzungen.

    Args:
        strassen_gdf: Straßen-GeoDataFrame (EPSG:4326) mit Spalte 'highway'.
        bezirke_gdf: Stadtbezirk-Polygone (EPSG:4326) mit Spalte 'name'.
        stadtteile_gdf: Stadtteil-Polygone (EPSG:4326, optional).

    Returns:
        GeoDataFrame mit gesplitteten Straßenabschnitten und Attributen:
        segment_id, osm_id, name, highway, bezirk, stadtteil, laenge_m, geometry.
    """
    logger.info("Starte Street-Splitting: %d Straßen-Geometrien", len(strassen_gdf))

    # Auf UTM32 projizieren für metrische Berechnungen
    strassen = strassen_gdf.to_crs(CRS_UTM32).copy()
    bezirke = bezirke_gdf.to_crs(CRS_UTM32).copy()

    # Hauptstraßen als Splitter identifizieren
    hauptstrassen = strassen[strassen["highway"].isin(HAUPTSTRASSEN_KLASSEN)].copy()
    logger.info("Hauptstraßen (primary/secondary): %d", len(hauptstrassen))

    # Kreuzungspunkte zwischen allen Straßen und Hauptstraßen finden
    kreuzungspunkte = _find_intersection_points(strassen, hauptstrassen)
    logger.info("Kreuzungspunkte gefunden: %d", len(kreuzungspunkte))

    # Straßen an Kreuzungspunkten splitten
    segmente = _split_at_points(strassen, kreuzungspunkte)
    logger.info("Segmente nach Splitting: %d", len(segmente))

    # Segment-IDs vergeben
    segmente = segmente.reset_index(drop=True)
    segmente["segment_id"] = segmente.apply(
        lambda row: f"{_clean_name(row.get('name', 'unbekannt'))}_{row.name:06d}",
        axis=1,
    )

    # Länge berechnen (in Metern, UTM32)
    segmente["laenge_m"] = segmente.geometry.length.round(1)

    # Stadtbezirk zuweisen (spatial join auf Centroid)
    # Centroid-GeoDataFrame explizit mit set_geometry aufbauen
    centroids = gpd.GeoDataFrame(
        {"segment_id": segmente["segment_id"].values},
        geometry=segmente.geometry.centroid.values,
        crs=CRS_UTM32,
    ).to_crs(CRS_WGS84)

    bezirke_wgs = bezirke_gdf.to_crs(CRS_WGS84).copy()

    joined = gpd.sjoin(
        centroids[["segment_id", "geometry"]],
        bezirke_wgs[["name", "geometry"]],
        how="left",
        predicate="within",
    )
    bezirk_map = joined.groupby("segment_id")["name"].first().to_dict()
    segmente["bezirk"] = segmente["segment_id"].map(bezirk_map).fillna("unbekannt")

    # Stadtteil zuweisen (falls verfügbar)
    if stadtteile_gdf is not None:
        stadtteile_wgs = stadtteile_gdf.to_crs(CRS_WGS84).copy()
        joined_st = gpd.sjoin(
            centroids[["segment_id", "geometry"]],
            stadtteile_wgs[["name", "geometry"]],
            how="left",
            predicate="within",
        )
        stadtteil_map = joined_st.groupby("segment_id")["name"].first().to_dict()
        segmente["stadtteil"] = segmente["segment_id"].map(stadtteil_map).fillna("unbekannt")
    else:
        segmente["stadtteil"] = "unbekannt"

    # Zurück auf WGS84
    segmente = segmente.to_crs(CRS_WGS84)

    # Kurze Segmente filtern (< 20m sind meist Artefakte)
    segmente_utm = segmente.to_crs(CRS_UTM32)
    segmente = segmente[segmente_utm.geometry.length >= 20].copy()
    logger.info("Segmente nach Mindestlängen-Filter (≥20m): %d", len(segmente))

    return segmente[["segment_id", "osm_id", "name", "highway", "bezirk", "stadtteil", "laenge_m", "geometry"]]


def _extract_points_from_geometry(geom: Any) -> list[Point]:
    """Extrahiert alle Punkte rekursiv aus einer beliebigen Geometrie.

    Args:
        geom: Shapely-Geometrie.

    Returns:
        Liste von Point-Geometrien.
    """
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type == "LineString":
        return [Point(c) for c in geom.coords]
    if hasattr(geom, "geoms"):
        result: list[Point] = []
        for part in geom.geoms:
            result.extend(_extract_points_from_geometry(part))
        return result
    return []


def _find_intersection_points(
    strassen: gpd.GeoDataFrame,
    hauptstrassen: gpd.GeoDataFrame,
) -> list[Point]:
    """Findet alle Schnittpunkte zwischen Straßen und Hauptstraßen.

    Args:
        strassen: Alle Straßen (UTM32).
        hauptstrassen: Nur Hauptstraßen (UTM32).

    Returns:
        Liste von Schnittpunkt-Geometrien.
    """
    punkte: list[Point] = []

    hauptstrassen_union = unary_union(hauptstrassen.geometry.tolist())

    for geom in strassen.geometry:
        if geom is None or geom.is_empty:
            continue
        try:
            intersection = geom.intersection(hauptstrassen_union)
        except Exception:
            continue
        punkte.extend(_extract_points_from_geometry(intersection))

    return punkte


def _split_at_points(
    strassen: gpd.GeoDataFrame,
    kreuzungspunkte: list[Point],
) -> gpd.GeoDataFrame:
    """Splittet Straßen-LineStrings an Kreuzungspunkten.

    Args:
        strassen: Straßen-GeoDataFrame (UTM32).
        kreuzungspunkte: Kreuzungspunkte für das Splitting.

    Returns:
        GeoDataFrame mit gesplitteten Segmenten.
    """
    segmente_rows: list[dict[str, Any]] = []

    for _, row in strassen.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Nahe Kreuzungspunkte für diese Straße finden
        nahe_punkte = [
            p for p in kreuzungspunkte
            if geom.distance(p) < SPLIT_TOLERANCE_M
        ]

        if not nahe_punkte:
            segmente_rows.append({
                "osm_id": row.get("osm_id", 0),
                "name": row.get("name", ""),
                "highway": row.get("highway", ""),
                "geometry": geom,
            })
            continue

        # Snapping + Splitting
        try:
            current = geom
            for punkt in nahe_punkte:
                snapped = snap(current, punkt, SPLIT_TOLERANCE_M)
                try:
                    result = split(snapped, punkt)
                    if result.geom_type == "GeometryCollection" and len(result.geoms) > 1:
                        # Ersten Teil weiterverarbeiten, Rest in nächster Iteration
                        parts = list(result.geoms)
                        for part in parts:
                            if isinstance(part, (LineString, MultiLineString)):
                                segmente_rows.append({
                                    "osm_id": row.get("osm_id", 0),
                                    "name": row.get("name", ""),
                                    "highway": row.get("highway", ""),
                                    "geometry": part,
                                })
                        current = None
                        break
                except Exception:
                    pass  # Split fehlgeschlagen: Original behalten

            if current is not None:
                segmente_rows.append({
                    "osm_id": row.get("osm_id", 0),
                    "name": row.get("name", ""),
                    "highway": row.get("highway", ""),
                    "geometry": current,
                })
        except Exception as exc:
            logger.debug("Split-Fehler für osm_id %s: %s", row.get("osm_id"), exc)
            segmente_rows.append({
                "osm_id": row.get("osm_id", 0),
                "name": row.get("name", ""),
                "highway": row.get("highway", ""),
                "geometry": geom,
            })

    return gpd.GeoDataFrame(segmente_rows, crs=CRS_UTM32)


def _clean_name(name: str) -> str:
    """Bereitet einen Straßennamen für eine ID auf.

    Args:
        name: Roher Straßenname.

    Returns:
        URL-sicherer Bezeichner.
    """
    import re
    clean = name.lower().strip()
    clean = re.sub(r"[^a-z0-9]", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:40] or "strasse"
