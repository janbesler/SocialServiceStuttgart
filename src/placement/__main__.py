"""Einstiegspunkt für Phase 6: Sozialarbeiter-Standortoptimierung.

Aufruf:
    conda run -n socialservices python -m src.placement

Ablauf:
    1. Bestehende Sozialeinrichtungen laden und klassifizieren
    2. Bedarf pro Straßenabschnitt berechnen
    3. Kandidatenstandorte aus POIs extrahieren
    4. Alle Szenarien berechnen und als GeoJSON schreiben
    5. kosten_nutzen.json zusammenfassen
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd

from .demand import berechne_bedarf
from .existing import load_bestand, merge_manuell
from .optimizer import select_kandidaten
from .scenarios import generate_all

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
PLACEMENT_DIR = BASE / "data" / "placement"


def main() -> None:
    """Führt die vollständige Phase-6-Pipeline aus."""
    PLACEMENT_DIR.mkdir(parents=True, exist_ok=True)
    (PLACEMENT_DIR / "szenarien").mkdir(parents=True, exist_ok=True)

    logger.info("=== Phase 6: Sozialarbeiter-Standortoptimierung ===")

    # --- 1. Bestehende Einrichtungen laden ---
    sozial_path = OSM_DIR / "sozialeinrichtungen.geojson"
    bezirke_path = OSM_DIR / "bezirke.geojson"

    if not sozial_path.exists():
        logger.error("sozialeinrichtungen.geojson fehlt — bitte Phase 2 ausführen")
        sys.exit(1)
    if not bezirke_path.exists():
        logger.error("bezirke.geojson fehlt — bitte Phase 2 ausführen")
        sys.exit(1)

    logger.info("--- Schritt 1: Bestehende Einrichtungen ---")
    bestand_gdf = load_bestand(sozial_path, bezirke_path)

    # Manuelle Ergänzungen (optional)
    manuell_path = PLACEMENT_DIR / "bestand_manuell.json"
    bestand_gdf = merge_manuell(bestand_gdf, manuell_path)

    logger.info("Bestand: %d Einrichtungen", len(bestand_gdf))

    # --- 2. Bedarf berechnen ---
    index_path = INDEX_DIR / "aufwachsindex.geojson"
    kinder_path = DISAGG_DIR / "einwohner_kinder.parquet"

    if not index_path.exists():
        logger.error("aufwachsindex.geojson fehlt — bitte Phase 4 ausführen")
        sys.exit(1)
    if not kinder_path.exists():
        logger.error("einwohner_kinder.parquet fehlt — bitte Phase 3 ausführen")
        sys.exit(1)

    logger.info("--- Schritt 2: Bedarfsberechnung ---")
    bedarf_gdf = berechne_bedarf(index_path, kinder_path, bestand_gdf)
    logger.info(
        "Bedarf: sum_roh=%.0f  sum_unversorgt=%.0f",
        bedarf_gdf["bedarf_roh"].sum(),
        bedarf_gdf["bedarf_unversorgt"].sum(),
    )

    # --- 3. Kandidatenstandorte extrahieren ---
    pois_path = OSM_DIR / "pois.geojson"

    if not pois_path.exists():
        logger.error("pois.geojson fehlt — bitte Phase 2 ausführen")
        sys.exit(1)

    logger.info("--- Schritt 3: Kandidatenstandorte ---")

    # ÖPNV-Haltestellen aus POIs extrahieren
    pois_gdf = gpd.read_file(pois_path)
    if pois_gdf.crs is None:
        pois_gdf = pois_gdf.set_crs("EPSG:4326")
    else:
        pois_gdf = pois_gdf.to_crs("EPSG:4326")

    transit_stops = pois_gdf[pois_gdf["public_transport"] == "stop_position"].copy()
    logger.info("  ÖPNV-Haltestellen: %d", len(transit_stops))

    kandidaten_gdf = select_kandidaten(pois_path, transit_stops)
    logger.info("Kandidaten: %d Standorte", len(kandidaten_gdf))

    if len(kandidaten_gdf) == 0:
        logger.warning(
            "Keine Kandidatenstandorte gefunden — Szenarien werden mit leerem Ergebnis berechnet"
        )

    # --- 4. Alle Szenarien berechnen ---
    logger.info("--- Schritt 4: Szenarien ---")
    ergebnis = generate_all(
        bedarf_gdf=bedarf_gdf,
        kandidaten_gdf=kandidaten_gdf,
        bestand_gdf=bestand_gdf,
        ausgabe_dir=PLACEMENT_DIR / "szenarien",
    )

    # --- Zusammenfassung ---
    szenarien = ergebnis["szenarien"]
    n_szenarien = len(szenarien)

    print(f"\nPhase 6 abgeschlossen.")
    print(f"  {len(bestand_gdf)} bestehende Einrichtungen")
    print(f"  {len(kandidaten_gdf)} Kandidatenstandorte")
    print(f"  {n_szenarien} Szenarien berechnet\n")

    # Tabelle
    header = f"{'Szenario':<20} {'n_neu':>6} {'Kosten/J':>12} {'Abdeckung %':>12} {'Kinder':>8}"
    print(header)
    print("-" * len(header))

    for name, zf in szenarien.items():
        print(
            f"{name:<20} "
            f"{zf['n_neue_stellen']:>6} "
            f"{zf['gesamtkosten_jahr_eur']:>11.0f} € "
            f"{zf['anteil_bedarf_abgedeckt_pct']:>11.1f}% "
            f"{zf['erreichte_kinder_neu']:>8.0f}"
        )

    print(f"\n  Ausgabe: {PLACEMENT_DIR}")
    print(f"  kosten_nutzen.json: {PLACEMENT_DIR / 'kosten_nutzen.json'}")


if __name__ == "__main__":
    main()
