"""Einstiegspunkt für die Katalog-Phase.

Aufruf:
    conda run -n socialservices python -m src.catalog
"""

import logging
import sys
from pathlib import Path

from .registry import build_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

BASE = Path(__file__).resolve().parents[2]
RAW_DIR = BASE / "data" / "raw"
CATALOG_DIR = BASE / "data" / "catalog"


def main() -> None:
    """Baut das Datensatz-Register aus allen CSV-Rohdaten."""
    if not RAW_DIR.exists():
        print(f"FEHLER: Rohdaten-Verzeichnis nicht gefunden: {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    registry = build_registry(RAW_DIR, CATALOG_DIR)
    index_relevant = [e for e in registry if e["index_relevant"]]
    print(f"\n✓ {len(registry)} Datensätze katalogisiert, davon {len(index_relevant)} index-relevant.")
    print(f"  Ausgabe: {CATALOG_DIR / 'registry.json'}")


if __name__ == "__main__":
    main()
