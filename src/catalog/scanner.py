"""CSV-Dateien einlesen und Schemata erkennen.

Liest alle CSV-Dateien aus data/raw/ ein, erkennt Spaltentypen,
Zeiträume und räumliche Auflösung automatisch.
"""

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Bekannte Bezirksnamen (offizielle Schreibweise)
STUTTGARTER_BEZIRKE: set[str] = {
    "Stuttgart-Mitte",
    "Stuttgart-Nord",
    "Stuttgart-Ost",
    "Stuttgart-Süd",
    "Stuttgart-West",
    "Bad Cannstatt",
    "Birkach",
    "Botnang",
    "Degerloch",
    "Feuerbach",
    "Hedelfingen",
    "Möhringen",
    "Mühlhausen",
    "Münster",
    "Obertürkheim",
    "Plieningen",
    "Sillenbuch",
    "Stammheim",
    "Untertürkheim",
    "Vaihingen",
    "Wangen",
    "Weilimdorf",
    "Zuffenhausen",
}

# Varianten-Mapping auf offizielle Schreibweise
BEZIRK_NORMALISIERUNG: dict[str, str] = {
    "s-mitte": "Stuttgart-Mitte",
    "mitte": "Stuttgart-Mitte",
    "s-nord": "Stuttgart-Nord",
    "nord": "Stuttgart-Nord",
    "s-ost": "Stuttgart-Ost",
    "ost": "Stuttgart-Ost",
    "s-süd": "Stuttgart-Süd",
    "süd": "Stuttgart-Süd",
    "s-west": "Stuttgart-West",
    "west": "Stuttgart-West",
    "bad cannstatt": "Bad Cannstatt",
    "cannstatt": "Bad Cannstatt",
    "bad-cannstatt": "Bad Cannirstat",
}

# Spaltennamen die auf Jahresspalten hindeuten
JAHR_PATTERN = re.compile(r"^(19|20)\d{2}$")
# Spaltennamen die auf eine Bezirksspalte hindeuten
BEZIRK_PATTERN = re.compile(r"bezirk|stadtbezirk|district", re.IGNORECASE)
JAHR_SPALTE_PATTERN = re.compile(r"^(jahr|year|periode|zeitraum)$", re.IGNORECASE)


def detect_encoding(path: Path) -> str:
    """Erkennt das Encoding einer CSV-Datei.

    Args:
        path: Pfad zur CSV-Datei.

    Returns:
        Encoding-String (z.B. 'utf-8', 'latin-1').
    """
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with path.open(encoding=encoding) as f:
                f.read(4096)
            return encoding
        except UnicodeDecodeError:
            continue
    logger.warning("Konnte Encoding nicht erkennen für %s, verwende latin-1", path.name)
    return "latin-1"


def detect_separator(path: Path, encoding: str) -> str:
    """Erkennt das Trennzeichen einer CSV-Datei.

    Args:
        path: Pfad zur CSV-Datei.
        encoding: Encoding der Datei.

    Returns:
        Trennzeichen (';' oder ',').
    """
    with path.open(encoding=encoding) as f:
        first_line = f.readline()
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    return ";" if semicolons >= commas else ","


def scan_csv(path: Path) -> dict[str, Any]:
    """Liest eine CSV-Datei ein und extrahiert Schema-Informationen.

    Args:
        path: Pfad zur CSV-Datei.

    Returns:
        Dictionary mit Schema-Informationen: Spalten, Zeitraum,
        räumliche Ebene, Stichprobengröße.

    Raises:
        ValueError: Wenn die Datei nicht gelesen werden kann.
    """
    if not path.exists():
        raise ValueError(f"Kann {path.name} nicht einlesen: Datei nicht gefunden")

    encoding = detect_encoding(path)
    sep = detect_separator(path, encoding)

    try:
        df = pd.read_csv(path, encoding=encoding, sep=sep, low_memory=False)
    except Exception as exc:
        raise ValueError(f"Kann {path.name} nicht einlesen: {exc}") from exc

    # Leere Spalten entfernen
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    info: dict[str, Any] = {
        "datei": path.name,
        "zeilen": len(df),
        "spalten_anzahl": len(df.columns),
        "spalten": list(df.columns),
        "encoding": encoding,
        "separator": sep,
        "zeitraum": _detect_zeitraum(df),
        "raeumliche_ebene": _detect_raeumliche_ebene(df),
        "wert_spalten": _detect_wert_spalten(df),
        "luecken_prozent": round(df.isnull().mean().mean() * 100, 1),
        "sample_werte": _extract_sample_werte(df),
    }

    return info


def _detect_zeitraum(df: pd.DataFrame) -> dict[str, Any]:
    """Erkennt den Zeitraum eines Datensatzes.

    Args:
        df: Der eingelesene DataFrame.

    Returns:
        Dictionary mit Zeitraum-Informationen.
    """
    jahre: list[int] = []

    # Spaltennamen die direkt Jahre sind (Wide-Format: 2005, 2006, ...)
    for col in df.columns:
        if JAHR_PATTERN.match(str(col)):
            jahre.append(int(col))

    # Jahresspalte im Long-Format
    for col in df.columns:
        if JAHR_SPALTE_PATTERN.match(str(col)):
            try:
                werte = pd.to_numeric(df[col], errors="coerce").dropna()
                jahr_werte = [int(v) for v in werte if 1900 <= v <= 2030]
                if jahr_werte:
                    jahre.extend(jahr_werte)
            except Exception:
                pass

    if jahre:
        return {
            "min": min(jahre),
            "max": max(jahre),
            "ebene": "jaehrlich",
            "format": "wide" if any(JAHR_PATTERN.match(str(c)) for c in df.columns) else "long",
        }

    return {"min": None, "max": None, "ebene": "unbekannt", "format": "unbekannt"}


def _detect_raeumliche_ebene(df: pd.DataFrame) -> str:
    """Erkennt die räumliche Auflösung eines Datensatzes.

    Args:
        df: Der eingelesene DataFrame.

    Returns:
        Räumliche Ebene: 'stadtbezirk', 'stadtteil', 'gesamtstadt', 'unbekannt'.
    """
    for col in df.columns:
        if BEZIRK_PATTERN.search(col):
            # Prüfe ob echte Bezirksnamen enthalten sind
            unique_vals = {str(v).strip().lower() for v in df[col].dropna().unique()}
            bezirke_lower = {b.lower() for b in STUTTGARTER_BEZIRKE}
            treffer = unique_vals & bezirke_lower
            normiert_treffer = {BEZIRK_NORMALISIERUNG.get(v, v) for v in unique_vals}
            if len(treffer) >= 3 or len(normiert_treffer & STUTTGARTER_BEZIRKE) >= 3:
                return "stadtbezirk"

    # Prüfe auf Stadtteil-Hinweise
    for col in df.columns:
        if re.search(r"stadtteil|ortsteil", col, re.IGNORECASE):
            return "stadtteil"

    # Wenn keine räumliche Spalte: Gesamtstadt oder unbekannt
    if any(BEZIRK_PATTERN.search(col) for col in df.columns):
        return "stadtbezirk"  # Spalte vorhanden aber unklare Werte

    return "gesamtstadt"


def _detect_wert_spalten(df: pd.DataFrame) -> list[str]:
    """Identifiziert numerische Wertspalten.

    Args:
        df: Der eingelesene DataFrame.

    Returns:
        Liste der Spalten mit numerischen Werten.
    """
    wert_spalten = []
    seen: set[str] = set()
    for col in df.columns:
        if col in seen:
            continue
        seen.add(col)
        if BEZIRK_PATTERN.search(col) or JAHR_SPALTE_PATTERN.match(col):
            continue
        if JAHR_PATTERN.match(str(col)):
            continue
        series = df[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() > len(df) * 0.3:
            wert_spalten.append(col)
    return wert_spalten


def _extract_sample_werte(df: pd.DataFrame) -> dict[str, list[Any]]:
    """Extrahiert Beispielwerte pro Spalte (max. 3).

    Args:
        df: Der eingelesene DataFrame.

    Returns:
        Dictionary Spaltenname → Liste von Beispielwerten.
    """
    sample: dict[str, list[Any]] = {}
    seen: set[str] = set()
    for col in list(df.columns)[:10]:  # Nur erste 10 Spalten
        if col in seen:
            continue
        seen.add(col)
        series = df[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        werte = series.dropna().head(3).tolist()
        sample[col] = [str(v)[:50] for v in werte]
    return sample


def scan_all(raw_dir: Path) -> list[dict[str, Any]]:
    """Scannt alle CSV-Dateien in einem Verzeichnis.

    Args:
        raw_dir: Verzeichnis mit CSV-Dateien.

    Returns:
        Liste von Schema-Dictionaries pro Datei.
    """
    results = []
    csv_files = sorted(raw_dir.glob("*.csv"))
    logger.info("Scanne %d CSV-Dateien in %s", len(csv_files), raw_dir)

    for path in csv_files:
        try:
            info = scan_csv(path)
            results.append(info)
            logger.debug("Gescannt: %s (%d Zeilen, %d Spalten)", path.name, info["zeilen"], info["spalten_anzahl"])
        except ValueError as exc:
            logger.warning("Fehler beim Scannen von %s: %s", path.name, exc)
            results.append({"datei": path.name, "fehler": str(exc)})

    logger.info("Scan abgeschlossen: %d Dateien verarbeitet", len(results))
    return results
