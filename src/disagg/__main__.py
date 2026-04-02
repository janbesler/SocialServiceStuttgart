"""Einstiegspunkt für Phase 3: Dasymetrische Disaggregation.

Aufruf:
    conda run -n socialservices python -m src.disagg
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .dasymetric import compute_segment_weights, disaggregate_timeseries
from .loaders import ALL_LOADERS
from .validation import validate_no_negatives, validate_sum_constraint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
OSM_DIR = BASE / "data" / "osm"
RAW_DIR = BASE / "data" / "raw"
DISAGG_DIR = BASE / "data" / "disaggregated"


def main() -> None:
    """Führt die Disaggregation aller Indikatoren aus."""
    DISAGG_DIR.mkdir(parents=True, exist_ok=True)

    # Straßenabschnitte laden
    seg_path = OSM_DIR / "strassenabschnitte.geojson"
    if not seg_path.exists():
        logger.error("Straßenabschnitte nicht gefunden: %s — bitte erst Phase 2 ausführen", seg_path)
        sys.exit(1)

    logger.info("=== Phase 3: Dasymetrische Disaggregation ===")
    segmente = gpd.read_file(seg_path)
    logger.info("Straßenabschnitte geladen: %d Segmente", len(segmente))

    # Segment-Gewichte berechnen (einmalig, für alle Indikatoren)
    weights = compute_segment_weights(segmente)
    logger.info("Segment-Gewichte berechnet (%d Segmente mit gültigem Bezirk)", len(weights))

    ergebnisse: dict[str, int] = {}

    for indikator, loader_fn in ALL_LOADERS.items():
        logger.info("Verarbeite: %s", indikator)
        try:
            spec = loader_fn(RAW_DIR)
        except Exception as exc:
            logger.warning("  Loader-Fehler für %s: %s — überspringe", indikator, exc)
            continue

        df = spec["df"]
        wert_spalten = spec["wert_spalten"]
        bezirk_spalte = spec["bezirk_spalte"]
        jahr_spalte = spec.get("jahr_spalte")
        modus = spec.get("modus", "count")

        if df.empty:
            logger.warning("  Leerer DataFrame für %s — überspringe", indikator)
            continue

        logger.info(
            "  %d Bezirks-Zeilen, %d Jahre, Modus=%s",
            df[bezirk_spalte].nunique(),
            df[jahr_spalte].nunique() if jahr_spalte and jahr_spalte in df else 1,
            modus,
        )

        # Disaggregieren
        if jahr_spalte and jahr_spalte in df.columns:
            disagg = disaggregate_timeseries(
                bezirk_df=df,
                weights=weights,
                wert_spalten=wert_spalten,
                bezirk_spalte=bezirk_spalte,
                jahr_spalte=jahr_spalte,
                dataset_id=indikator,
                modus=modus,
            )
        else:
            from .dasymetric import disaggregate_bezirk_to_segments
            disagg = disaggregate_bezirk_to_segments(
                bezirk_df=df,
                weights=weights,
                wert_spalten=wert_spalten,
                bezirk_spalte=bezirk_spalte,
                dataset_id=indikator,
                modus=modus,
            )

        if disagg.empty:
            logger.warning("  Keine disaggregierten Daten für %s", indikator)
            continue

        # Validierung (nur für Count-Indikatoren)
        if modus == "count":
            validate_sum_constraint(disagg, df, wert_spalten, bezirk_spalte, indikator)
            validate_no_negatives(disagg, wert_spalten, indikator)

        # Speichern als Parquet
        out_path = DISAGG_DIR / f"{indikator}.parquet"
        disagg.to_parquet(out_path, index=False)
        ergebnisse[indikator] = len(disagg)
        logger.info("  → %d Zeilen → %s", len(disagg), out_path.name)

    logger.info("=== Disaggregation abgeschlossen ===")
    print(f"\n✓ {len(ergebnisse)} Indikatoren disaggregiert:")
    for name, n in sorted(ergebnisse.items()):
        print(f"  {name:<30} {n:>7} Zeilen")


if __name__ == "__main__":
    main()
