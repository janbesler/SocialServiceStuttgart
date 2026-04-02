"""Zentrales Datensatz-Register.

Kombiniert Scanner, Classifier und Normalizer zu einem vollständigen
registry.json das alle verfügbaren Datensätze beschreibt.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from .classifier import classify_dataset
from .scanner import scan_all, scan_csv

logger = logging.getLogger(__name__)

JAHR_PATTERN = re.compile(r"^(19|20)\d{2}$")
BEZIRK_SPALTE_PATTERN = re.compile(r"bezirk|stadtbezirk|district", re.IGNORECASE)
JAHR_SPALTE_PATTERN = re.compile(r"^(jahr|year|periode|zeitraum)$", re.IGNORECASE)


def _derive_dataset_id(dateiname: str) -> str:
    """Leitet eine maschinenlesbare ID aus dem Dateinamen ab.

    Args:
        dateiname: Name der CSV-Datei.

    Returns:
        URL-sichere ID.
    """
    name = dateiname.replace(".csv", "").lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name[:80]  # Max-Länge begrenzen


def _detect_spalten_schema(info: dict[str, Any]) -> dict[str, Any]:
    """Erkennt das Spalten-Schema (bezirk, jahr, werte).

    Args:
        info: Scanner-Output für eine Datei.

    Returns:
        Schema-Dictionary.
    """
    spalten = info.get("spalten", [])
    schema: dict[str, Any] = {"bezirk": None, "jahr": None, "werte": []}

    for col in spalten:
        if BEZIRK_SPALTE_PATTERN.search(str(col)) and schema["bezirk"] is None:
            schema["bezirk"] = col
        elif JAHR_SPALTE_PATTERN.match(str(col)) and schema["jahr"] is None:
            schema["jahr"] = col

    # Wert-Spalten = alle außer bezirk/jahr und Jahres-Headers
    wert_spalten = info.get("wert_spalten", [])
    schema["werte"] = [
        c for c in wert_spalten
        if c != schema["bezirk"] and c != schema["jahr"]
        and not JAHR_PATTERN.match(str(c))
    ]
    # Im Wide-Format: Jahres-Spalten als Werte-Spalten
    jahr_spalten = [c for c in spalten if JAHR_PATTERN.match(str(c))]
    if jahr_spalten:
        schema["werte"] = jahr_spalten

    return schema


def build_registry(raw_dir: Path, catalog_dir: Path) -> list[dict[str, Any]]:
    """Erstellt das vollständige Datensatz-Register.

    Liest alle CSV-Dateien, klassifiziert sie und schreibt registry.json.

    Args:
        raw_dir: Verzeichnis mit Rohdaten-CSVs.
        catalog_dir: Ausgabe-Verzeichnis für registry.json.

    Returns:
        Liste aller Datensatz-Einträge.
    """
    catalog_dir.mkdir(parents=True, exist_ok=True)
    scan_results = scan_all(raw_dir)

    registry: list[dict[str, Any]] = []

    for info in scan_results:
        if "fehler" in info:
            logger.warning("Überspringe %s wegen Fehler: %s", info["datei"], info["fehler"])
            continue

        datei = info["datei"]
        dataset_id = _derive_dataset_id(datei)

        klassifikation = classify_dataset(datei, info.get("spalten", []))
        spalten_schema = _detect_spalten_schema(info)
        zeitraum = info.get("zeitraum", {})

        einheit = _guess_einheit(datei, info.get("spalten", []))

        eintrag: dict[str, Any] = {
            "id": dataset_id,
            "datei": datei,
            "titel": _datei_zu_titel(datei),
            "thema": klassifikation["thema"],
            "dimensionen": klassifikation["dimensionen"],
            "index_relevant": klassifikation["index_relevant"],
            "raeumliche_ebene": info.get("raeumliche_ebene", "unbekannt"),
            "zeitliche_ebene": zeitraum.get("ebene", "unbekannt"),
            "zeitraum": [zeitraum.get("min"), zeitraum.get("max")],
            "spalten": spalten_schema,
            "einheit": einheit,
            "qualitaet": {
                "luecken_prozent": info.get("luecken_prozent", 0.0),
                "zeilen": info.get("zeilen", 0),
                "bemerkungen": "",
            },
        }

        registry.append(eintrag)
        logger.debug("Registriert: %s → %s %s", dataset_id, klassifikation["thema"], klassifikation["dimensionen"])

    # Sortiert: index-relevante zuerst, dann nach Thema
    registry.sort(key=lambda e: (not e["index_relevant"], e["thema"], e["id"]))

    # Schreiben
    output_path = catalog_dir / "registry.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    logger.info(
        "Registry geschrieben: %d Datensätze (%d index-relevant) → %s",
        len(registry),
        sum(1 for e in registry if e["index_relevant"]),
        output_path,
    )
    return registry


def _datei_zu_titel(dateiname: str) -> str:
    """Generiert einen lesbaren Titel aus dem Dateinamen.

    Args:
        dateiname: CSV-Dateiname.

    Returns:
        Lesbarer Titel.
    """
    name = dateiname.replace(".csv", "")
    # Präfixe entfernen
    for prefix in ["tidy_", "komunis-12204-v1-", "komunis-12205-v1-", "komunis-12206-v1-",
                   "komunis-479-v1-", "komunis-5794-", "komunis-9902-v1-", "komunis-9903-v1-",
                   "test-2.2.32-", "test_2.3.4-", "test_2.5.6-"]:
        name = name.replace(prefix, "")
    name = name.replace("_", " ").replace("-", " ")
    return name.strip().capitalize()


def _guess_einheit(datei: str, spalten: list[str]) -> str:
    """Schätzt die Einheit des Datensatzes grob.

    Args:
        datei: Dateiname.
        spalten: Spaltennamen.

    Returns:
        Einheiten-String.
    """
    text = (datei + " " + " ".join(spalten)).lower()
    if "prozent" in text or "quote" in text or "anteil" in text:
        return "Prozent"
    if "je_1000" in text or "je 1000" in text:
        return "Je 1.000 Einwohner"
    if "anzahl" in text or "anzahl" in text:
        return "Anzahl"
    if "euro" in text or "eur" in text:
        return "Euro"
    return "Anzahl"


def load_registry(catalog_dir: Path) -> list[dict[str, Any]]:
    """Lädt das Registry aus einer JSON-Datei.

    Args:
        catalog_dir: Verzeichnis mit registry.json.

    Returns:
        Liste der Datensatz-Einträge.

    Raises:
        FileNotFoundError: Wenn registry.json nicht existiert.
    """
    path = catalog_dir / "registry.json"
    if not path.exists():
        raise FileNotFoundError(f"Registry nicht gefunden: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)
