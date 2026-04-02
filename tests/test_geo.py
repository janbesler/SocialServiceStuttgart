"""Tests für Phase 2: Geodaten-Pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from src.geo.spatial_index import (
    overpass_nodes_to_dict,
    overpass_pois_to_points,
    overpass_relations_to_polygons,
    overpass_ways_to_linestrings,
)
from src.geo.street_splitter import _clean_name, split_streets


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def simple_elements() -> list[dict]:
    """Minimale Overpass-Elementliste mit 2 Nodes und 1 Way."""
    return [
        {"type": "node", "id": 1, "lat": 48.775, "lon": 9.180},
        {"type": "node", "id": 2, "lat": 48.780, "lon": 9.185},
        {"type": "node", "id": 3, "lat": 48.785, "lon": 9.190},
        {
            "type": "way",
            "id": 100,
            "nodes": [1, 2, 3],
            "tags": {"highway": "primary", "name": "Königstraße"},
        },
    ]


@pytest.fixture()
def bezirke_gdf() -> gpd.GeoDataFrame:
    """Minimales Bezirke-GeoDataFrame mit 2 Bezirken."""
    return gpd.GeoDataFrame(
        {
            "name": ["Stuttgart-Mitte", "Stuttgart-Nord"],
            "geometry": [
                Polygon([(9.17, 48.77), (9.19, 48.77), (9.19, 48.79), (9.17, 48.79)]),
                Polygon([(9.17, 48.79), (9.19, 48.79), (9.19, 48.81), (9.17, 48.81)]),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture()
def strassen_gdf() -> gpd.GeoDataFrame:
    """Minimales Straßen-GeoDataFrame."""
    return gpd.GeoDataFrame(
        {
            "osm_id": [100, 200],
            "name": ["Königstraße", "Hauptstraße"],
            "highway": ["primary", "secondary"],
            "geometry": [
                LineString([(9.175, 48.775), (9.180, 48.780)]),
                LineString([(9.178, 48.772), (9.178, 48.782)]),
            ],
        },
        crs="EPSG:4326",
    )


# ── overpass_nodes_to_dict ────────────────────────────────────────────────────

class TestOverpassNodesToDict:
    def test_basic(self, simple_elements: list[dict]) -> None:
        result = overpass_nodes_to_dict(simple_elements)
        assert 1 in result
        assert result[1] == (9.180, 48.775)

    def test_ignoriert_ways(self, simple_elements: list[dict]) -> None:
        result = overpass_nodes_to_dict(simple_elements)
        assert 100 not in result  # Way, kein Node

    def test_leer(self) -> None:
        assert overpass_nodes_to_dict([]) == {}

    def test_node_ohne_koordinaten(self) -> None:
        elements = [{"type": "node", "id": 5}]  # Kein lat/lon
        result = overpass_nodes_to_dict(elements)
        assert 5 not in result


# ── overpass_ways_to_linestrings ──────────────────────────────────────────────

class TestOverpassWaysToLinestrings:
    def test_basic(self, simple_elements: list[dict]) -> None:
        node_lookup = overpass_nodes_to_dict(simple_elements)
        gdf = overpass_ways_to_linestrings(simple_elements, node_lookup)
        assert len(gdf) == 1
        assert gdf.iloc[0]["osm_id"] == 100
        assert gdf.iloc[0]["highway"] == "primary"
        assert gdf.crs.to_epsg() == 4326

    def test_way_mit_unbekannten_nodes(self) -> None:
        elements = [
            {"type": "way", "id": 1, "nodes": [999, 998], "tags": {"highway": "primary"}},
        ]
        gdf = overpass_ways_to_linestrings(elements, {})
        assert len(gdf) == 0  # Keine validen Koordinaten

    def test_leere_elements(self) -> None:
        gdf = overpass_ways_to_linestrings([], {})
        assert len(gdf) == 0


# ── overpass_pois_to_points ───────────────────────────────────────────────────

class TestOverpassPoisToPoints:
    def test_node_poi(self) -> None:
        elements = [
            {"type": "node", "id": 1, "lat": 48.775, "lon": 9.180,
             "tags": {"amenity": "school", "name": "Grundschule Mitte"}},
        ]
        gdf = overpass_pois_to_points(elements)
        assert len(gdf) == 1
        assert gdf.iloc[0]["amenity"] == "school"
        assert gdf.crs.to_epsg() == 4326

    def test_node_ohne_tags_ignoriert(self) -> None:
        elements = [
            {"type": "node", "id": 1, "lat": 48.775, "lon": 9.180},
        ]
        gdf = overpass_pois_to_points(elements)
        assert len(gdf) == 0

    def test_leere_elements(self) -> None:
        gdf = overpass_pois_to_points([])
        assert len(gdf) == 0


# ── overpass_relations_to_polygons ────────────────────────────────────────────

class TestOverpassRelationsToPolygons:
    def test_einfaches_polygon(self) -> None:
        elements = [
            {"type": "node", "id": 1, "lat": 48.77, "lon": 9.17},
            {"type": "node", "id": 2, "lat": 48.77, "lon": 9.19},
            {"type": "node", "id": 3, "lat": 48.79, "lon": 9.19},
            {"type": "node", "id": 4, "lat": 48.79, "lon": 9.17},
            {"type": "node", "id": 5, "lat": 48.77, "lon": 9.17},  # Schlusspunkt
            {"type": "way", "id": 10, "nodes": [1, 2, 3, 4, 5]},
            {
                "type": "relation",
                "id": 50,
                "tags": {"name": "Stuttgart-Mitte", "admin_level": "9"},
                "members": [{"type": "way", "ref": 10, "role": "outer"}],
            },
        ]
        gdf = overpass_relations_to_polygons(elements)
        assert len(gdf) == 1
        assert gdf.iloc[0]["name"] == "Stuttgart-Mitte"
        assert gdf.crs.to_epsg() == 4326

    def test_relation_ohne_outer_ways_ignoriert(self) -> None:
        elements = [
            {
                "type": "relation",
                "id": 50,
                "tags": {"name": "Test"},
                "members": [],
            }
        ]
        gdf = overpass_relations_to_polygons(elements)
        assert len(gdf) == 0


# ── split_streets ─────────────────────────────────────────────────────────────

class TestSplitStreets:
    def test_gibt_geodataframe_zurueck(
        self, strassen_gdf: gpd.GeoDataFrame, bezirke_gdf: gpd.GeoDataFrame
    ) -> None:
        result = split_streets(strassen_gdf, bezirke_gdf)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) > 0

    def test_pflichtfelder_vorhanden(
        self, strassen_gdf: gpd.GeoDataFrame, bezirke_gdf: gpd.GeoDataFrame
    ) -> None:
        result = split_streets(strassen_gdf, bezirke_gdf)
        for col in ["segment_id", "osm_id", "name", "highway", "bezirk", "laenge_m"]:
            assert col in result.columns, f"Spalte '{col}' fehlt"

    def test_crs_wgs84(
        self, strassen_gdf: gpd.GeoDataFrame, bezirke_gdf: gpd.GeoDataFrame
    ) -> None:
        result = split_streets(strassen_gdf, bezirke_gdf)
        assert result.crs.to_epsg() == 4326

    def test_laenge_positiv(
        self, strassen_gdf: gpd.GeoDataFrame, bezirke_gdf: gpd.GeoDataFrame
    ) -> None:
        result = split_streets(strassen_gdf, bezirke_gdf)
        assert (result["laenge_m"] > 0).all()

    def test_segment_ids_eindeutig(
        self, strassen_gdf: gpd.GeoDataFrame, bezirke_gdf: gpd.GeoDataFrame
    ) -> None:
        result = split_streets(strassen_gdf, bezirke_gdf)
        assert result["segment_id"].is_unique


# ── _clean_name ───────────────────────────────────────────────────────────────

class TestCleanName:
    def test_leerzeichen_zu_unterstrich(self) -> None:
        assert "_" in _clean_name("Königstraße")

    def test_leer_gibt_strasse(self) -> None:
        assert _clean_name("") == "strasse"

    def test_max_laenge(self) -> None:
        langer_name = "a" * 100
        assert len(_clean_name(langer_name)) <= 40
