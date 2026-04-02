"""Einstiegspunkt für die Geodaten-Phase.

Aufruf:
    conda run -n socialservices python -m src.geo
    conda run -n socialservices python -m src.geo --skip stadtteile gebaeude
    conda run -n socialservices python -m src.geo --only stadtbezirke strassennetz pois sozialeinrichtungen
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd

from .osm_extract import _ALL_QUERIES, fetch_all
from .spatial_index import (
    overpass_nodes_to_dict,
    overpass_pois_to_points,
    overpass_relations_to_polygons,
    overpass_ways_to_linestrings,
)
from .street_splitter import split_streets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
OSM_DIR = BASE / "data" / "osm"


def main() -> None:
    """Führt die komplette Geodaten-Pipeline aus."""
    parser = argparse.ArgumentParser(description="Phase 2: Geodaten-Pipeline")
    parser.add_argument(
        "--skip",
        nargs="+",
        metavar="DATASET",
        default=[],
        help=f"Datensätze überspringen. Verfügbar: {', '.join(_ALL_QUERIES)}",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="DATASET",
        default=[],
        help="Nur diese Datensätze laden (rest überspringen)",
    )
    args = parser.parse_args()

    skip: set[str] = set(args.skip)
    if args.only:
        skip = set(_ALL_QUERIES) - set(args.only)

    OSM_DIR.mkdir(parents=True, exist_ok=True)

    # 1. OSM-Daten laden
    logger.info("=== Phase 2: Geodaten-Pipeline ===")
    if skip:
        logger.info("Überspringe: %s", ", ".join(sorted(skip)))

    osm_data = fetch_all(OSM_DIR, skip=skip)

    # 2. Stadtbezirke
    bezirke_gdf = gpd.GeoDataFrame()
    if osm_data.get("stadtbezirke", {}).get("elements"):
        logger.info("Verarbeite Stadtbezirke...")
        bezirke_gdf = overpass_relations_to_polygons(osm_data["stadtbezirke"]["elements"])
        if len(bezirke_gdf) > 0:
            out = OSM_DIR / "bezirke.geojson"
            bezirke_gdf.to_file(out, driver="GeoJSON")
            logger.info("  → %d Bezirke → %s", len(bezirke_gdf), out.name)
        else:
            logger.warning("Keine Stadtbezirke gefunden — prüfe Overpass-Query")

    # 3. Stadtteile (optional)
    stadtteile_gdf: gpd.GeoDataFrame | None = None
    if osm_data.get("stadtteile", {}).get("elements"):
        logger.info("Verarbeite Stadtteile...")
        stadtteile_gdf = overpass_relations_to_polygons(osm_data["stadtteile"]["elements"])
        if len(stadtteile_gdf) > 0:
            out = OSM_DIR / "stadtteile.geojson"
            stadtteile_gdf.to_file(out, driver="GeoJSON")
            logger.info("  → %d Stadtteile → %s", len(stadtteile_gdf), out.name)

    # 4. Straßennetz + Splitting
    if osm_data.get("strassennetz", {}).get("elements") and len(bezirke_gdf) > 0:
        logger.info("Verarbeite Straßennetz...")
        elements = osm_data["strassennetz"]["elements"]
        node_lookup = overpass_nodes_to_dict(elements)
        strassen_gdf = overpass_ways_to_linestrings(elements, node_lookup)
        logger.info("  → %d Straßen-Geometrien", len(strassen_gdf))

        logger.info("Starte Street-Splitting...")
        segmente_gdf = split_streets(strassen_gdf, bezirke_gdf, stadtteile_gdf)
        out = OSM_DIR / "strassenabschnitte.geojson"
        segmente_gdf.to_file(out, driver="GeoJSON")
        logger.info("  → %d Straßenabschnitte → %s", len(segmente_gdf), out.name)
    elif "strassennetz" not in skip:
        logger.warning("Straßennetz oder Bezirke fehlen — kein Street-Splitting")

    # 5. POIs
    if osm_data.get("pois", {}).get("elements"):
        logger.info("Verarbeite POIs...")
        pois_gdf = overpass_pois_to_points(osm_data["pois"]["elements"])
        if len(pois_gdf) > 0:
            out = OSM_DIR / "pois.geojson"
            pois_gdf.to_file(out, driver="GeoJSON")
            logger.info("  → %d POIs → %s", len(pois_gdf), out.name)

    # 6. Sozialeinrichtungen
    if osm_data.get("sozialeinrichtungen", {}).get("elements"):
        logger.info("Verarbeite Sozialeinrichtungen...")
        sozial_gdf = overpass_pois_to_points(osm_data["sozialeinrichtungen"]["elements"])
        if len(sozial_gdf) > 0:
            out = OSM_DIR / "sozialeinrichtungen.geojson"
            sozial_gdf.to_file(out, driver="GeoJSON")
            logger.info("  → %d Sozialeinrichtungen → %s", len(sozial_gdf), out.name)

    logger.info("=== Geodaten-Pipeline abgeschlossen ===")

    # Zusammenfassung
    geojsons = list(OSM_DIR.glob("*.geojson"))
    print(f"\n✓ Phase 2 abgeschlossen. {len(geojsons)} GeoJSON-Dateien in {OSM_DIR}:")
    for f in sorted(geojsons):
        size_kb = f.stat().st_size // 1024
        print(f"  {f.name:<35} {size_kb:>6} KB")


if __name__ == "__main__":
    main()
