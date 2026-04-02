"""Einstiegspunkt für Phase 4: Index-Berechnung.

Aufruf:
    conda run -n socialservices python -m src.index
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .aufwachsindex import berechne_aufwachsindex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
OSM_DIR = BASE / "data" / "osm"
DISAGG_DIR = BASE / "data" / "disaggregated"
INDEX_DIR = BASE / "data" / "indices"


def main() -> None:
    """Berechnet den Aufwachsindex und schreibt GeoJSON."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    seg_path = OSM_DIR / "strassenabschnitte.geojson"
    if not seg_path.exists():
        logger.error("Straßenabschnitte fehlen — bitte Phase 2 ausführen")
        sys.exit(1)

    logger.info("=== Phase 4: Index-Berechnung ===")
    segmente = gpd.read_file(seg_path)
    logger.info("Segmente geladen: %d", len(segmente))

    result = berechne_aufwachsindex(DISAGG_DIR, segmente)

    # Statistiken
    idx = result["aufwachsindex_gesamt"].dropna()
    logger.info(
        "Aufwachsindex — min=%.1f  median=%.1f  max=%.1f  std=%.1f",
        idx.min(), idx.median(), idx.max(), idx.std(),
    )

    # Top 5 belastete Bezirke
    bezirk_mean = (
        result.dropna(subset=["aufwachsindex_gesamt"])
        .groupby("bezirk")["aufwachsindex_gesamt"]
        .mean()
        .sort_values(ascending=False)
    )
    logger.info("Top 5 belastete Bezirke:\n%s", bezirk_mean.head().to_string())

    # GeoJSON schreiben (vereinfachte Version für Dashboard)
    out_path = INDEX_DIR / "aufwachsindex.geojson"
    result.to_file(out_path, driver="GeoJSON")
    size_mb = out_path.stat().st_size / 1_048_576
    logger.info("GeoJSON geschrieben: %s (%.1f MB)", out_path.name, size_mb)

    if size_mb > 5:
        logger.warning(
            "GeoJSON > 5 MB (%.1f MB) — für Dashboard ggf. Geometrien vereinfachen",
            size_mb,
        )

    # Kompakte Parquet-Version für weitere Verarbeitung
    parquet_path = INDEX_DIR / "aufwachsindex.parquet"
    result.drop(columns=["geometry"]).to_parquet(parquet_path, index=False)
    logger.info("Parquet geschrieben: %s", parquet_path.name)

    print(f"\n✓ Phase 4 abgeschlossen.")
    print(f"  {len(result)} Straßenabschnitte mit Aufwachsindex.")
    print(f"  Ausgabe: {out_path}")
    print(f"\n  Durchschnitt pro Bezirk (Top 5 belastet):")
    for bezirk, wert in bezirk_mean.head().items():
        print(f"    {bezirk:<25} {wert:.1f}")


if __name__ == "__main__":
    main()
