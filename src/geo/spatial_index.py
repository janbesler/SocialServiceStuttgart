"""Konvertierung von Overpass-JSON zu GeoDataFrames und räumliche Indizes.

Hilfsfunktionen die Overpass-Rohdaten in saubere GeoDataFrames umwandeln.
"""

import logging
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

logger = logging.getLogger(__name__)

CRS_WGS84 = "EPSG:4326"
CRS_UTM32 = "EPSG:25832"  # Für Flächen-/Distanzberechnungen

_EMPTY_LINESTRING_GDF_COLS = ["osm_id", "name", "highway", "geometry"]
_EMPTY_POINT_GDF_COLS = ["osm_id", "osm_type", "name", "amenity", "leisure",
                          "public_transport", "social_facility", "geometry"]
_EMPTY_POLYGON_GDF_COLS = ["osm_id", "name", "admin_level", "geometry"]


def _empty_gdf(columns: list[str], crs: str) -> gpd.GeoDataFrame:
    """Erstellt ein leeres GeoDataFrame mit bekannten Spalten.

    Args:
        columns: Spaltennamen (muss 'geometry' enthalten).
        crs: Koordinatenreferenzsystem.

    Returns:
        Leeres GeoDataFrame.
    """
    return gpd.GeoDataFrame(
        {col: pd.Series(dtype="object") for col in columns},
        geometry="geometry",
        crs=crs,
    )


def overpass_nodes_to_dict(elements: list[dict[str, Any]]) -> dict[int, tuple[float, float]]:
    """Extrahiert Node-ID → (lon, lat) Mapping aus Overpass-Elementen.

    Args:
        elements: Overpass-Elementliste.

    Returns:
        Dictionary von Node-ID zu (lon, lat) Koordinaten.
    """
    return {
        el["id"]: (el["lon"], el["lat"])
        for el in elements
        if el["type"] == "node" and "lon" in el and "lat" in el
    }


def overpass_ways_to_linestrings(
    elements: list[dict[str, Any]],
    node_lookup: dict[int, tuple[float, float]],
) -> gpd.GeoDataFrame:
    """Konvertiert Overpass-Ways zu einem LineString-GeoDataFrame.

    Args:
        elements: Overpass-Elementliste.
        node_lookup: Node-ID → (lon, lat) Mapping.

    Returns:
        GeoDataFrame mit Spalten: osm_id, name, highway, geometry.
    """
    rows = []
    for el in elements:
        if el["type"] != "way":
            continue
        node_ids = el.get("nodes", [])
        coords = [node_lookup[nid] for nid in node_ids if nid in node_lookup]
        if len(coords) < 2:
            continue
        tags = el.get("tags", {})
        rows.append({
            "osm_id": el["id"],
            "name": tags.get("name", ""),
            "highway": tags.get("highway", ""),
            "geometry": LineString(coords),
        })

    if not rows:
        return _empty_gdf(_EMPTY_LINESTRING_GDF_COLS, CRS_WGS84)

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_WGS84)
    logger.debug("Ways → %d LineStrings", len(gdf))
    return gdf


def overpass_pois_to_points(elements: list[dict[str, Any]]) -> gpd.GeoDataFrame:
    """Konvertiert Overpass-Nodes/Ways zu POI-Punkten.

    Für Ways wird der Centroid verwendet.

    Args:
        elements: Overpass-Elementliste.

    Returns:
        GeoDataFrame mit Spalten: osm_id, osm_type, name, amenity, leisure,
        public_transport, geometry.
    """
    node_lookup = overpass_nodes_to_dict(elements)
    rows = []

    for el in elements:
        tags = el.get("tags", {})
        if not tags:
            continue

        if el["type"] == "node" and "lon" in el:
            geom: Point = Point(el["lon"], el["lat"])
        elif el["type"] == "way":
            coords = [node_lookup[nid] for nid in el.get("nodes", []) if nid in node_lookup]
            if len(coords) < 3:
                continue
            geom = Polygon(coords).centroid
        else:
            continue

        rows.append({
            "osm_id": el["id"],
            "osm_type": el["type"],
            "name": tags.get("name", ""),
            "amenity": tags.get("amenity", ""),
            "leisure": tags.get("leisure", ""),
            "public_transport": tags.get("public_transport", ""),
            "social_facility": tags.get("social_facility", ""),
            "geometry": geom,
        })

    if not rows:
        return _empty_gdf(_EMPTY_POINT_GDF_COLS, CRS_WGS84)

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_WGS84)
    logger.debug("POIs → %d Punkte", len(gdf))
    return gdf


def overpass_relations_to_polygons(
    elements: list[dict[str, Any]],
    name_tag: str = "name",
) -> gpd.GeoDataFrame:
    """Konvertiert Overpass-Relations (Grenzen) zu Polygon-GeoDataFrame.

    Einfache Approximation: äußere Ways werden zu Polygonen zusammengesetzt.

    Args:
        elements: Overpass-Elementliste.
        name_tag: Tag-Name für den Bezirks-/Stadtteil-Namen.

    Returns:
        GeoDataFrame mit Spalten: osm_id, name, admin_level, geometry.
    """
    node_lookup = overpass_nodes_to_dict(elements)

    # Ways als LineStrings aufbauen
    way_lines: dict[int, list[tuple[float, float]]] = {}
    for el in elements:
        if el["type"] != "way":
            continue
        coords = [node_lookup[nid] for nid in el.get("nodes", []) if nid in node_lookup]
        if len(coords) >= 2:
            way_lines[el["id"]] = coords

    rows = []
    for el in elements:
        if el["type"] != "relation":
            continue
        tags = el.get("tags", {})
        members = el.get("members", [])

        # Outer-Ways zusammensammeln
        outer_coords: list[tuple[float, float]] = []
        for member in members:
            if member.get("role") == "outer" and member.get("type") == "way":
                way_id = member["ref"]
                if way_id in way_lines:
                    outer_coords.extend(way_lines[way_id])

        if len(outer_coords) < 4:
            continue

        try:
            poly = Polygon(outer_coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception as exc:
            logger.warning("Polygon-Fehler für Relation %d: %s", el["id"], exc)
            continue

        rows.append({
            "osm_id": el["id"],
            "name": tags.get(name_tag, tags.get("name", "")),
            "admin_level": tags.get("admin_level", ""),
            "geometry": poly,
        })

    if not rows:
        return _empty_gdf(_EMPTY_POLYGON_GDF_COLS, CRS_WGS84)

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_WGS84)
    logger.debug("Relations → %d Polygone", len(gdf))
    return gdf
