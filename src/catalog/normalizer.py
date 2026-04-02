"""Normalisierung von Spaltennamen, Bezirksnamen und Zeitformaten.

Bringt alle Datensätze auf ein einheitliches Schema:
- Bezirksnamen → offizielle Stuttgarter Schreibweise
- Jahresspalten → Integer
- Fehlwerte → explizit als None/NaN
"""

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Offizielle Bezirksnamen-Normalisierung
BEZIRK_MAP: dict[str, str] = {
    # Stuttgart-Mitte
    "mitte": "Stuttgart-Mitte",
    "stuttgart-mitte": "Stuttgart-Mitte",
    "s-mitte": "Stuttgart-Mitte",
    "stuttgart mitte": "Stuttgart-Mitte",
    # Stuttgart-Nord
    "nord": "Stuttgart-Nord",
    "stuttgart-nord": "Stuttgart-Nord",
    "s-nord": "Stuttgart-Nord",
    # Stuttgart-Ost
    "ost": "Stuttgart-Ost",
    "stuttgart-ost": "Stuttgart-Ost",
    "s-ost": "Stuttgart-Ost",
    # Stuttgart-Süd
    "süd": "Stuttgart-Süd",
    "sued": "Stuttgart-Süd",
    "stuttgart-süd": "Stuttgart-Süd",
    "s-süd": "Stuttgart-Süd",
    "s-sued": "Stuttgart-Süd",
    # Stuttgart-West
    "west": "Stuttgart-West",
    "stuttgart-west": "Stuttgart-West",
    "s-west": "Stuttgart-West",
    # Bad Cannstatt
    "bad cannstatt": "Bad Cannstatt",
    "bad-cannstatt": "Bad Cannstatt",
    "cannstatt": "Bad Cannstatt",
    # Weitere Bezirke
    "birkach": "Birkach",
    "botnang": "Botnang",
    "degerloch": "Degerloch",
    "feuerbach": "Feuerbach",
    "hedelfingen": "Hedelfingen",
    "möhringen": "Möhringen",
    "moehringen": "Möhringen",
    "mühlhausen": "Mühlhausen",
    "muehlhausen": "Mühlhausen",
    "münster": "Münster",
    "muenster": "Münster",
    "obertürkheim": "Obertürkheim",
    "obertuerkheim": "Obertürkheim",
    "plieningen": "Plieningen",
    "sillenbuch": "Sillenbuch",
    "stammheim": "Stammheim",
    "untertürkheim": "Untertürkheim",
    "untertuerkheim": "Untertürkheim",
    "vaihingen": "Vaihingen",
    "wangen": "Wangen",
    "weilimdorf": "Weilimdorf",
    "zuffenhausen": "Zuffenhausen",
    # Gesamtstadt
    "stuttgart": "Stuttgart (gesamt)",
    "landeshauptstadt stuttgart": "Stuttgart (gesamt)",
    "lhs stuttgart": "Stuttgart (gesamt)",
    "stadtgebiet": "Stuttgart (gesamt)",
}

# Typische Fehlwert-Darstellungen
FEHLWERT_TOKENS: set[str] = {
    "-", "–", "—", ".", "..", "...", "n.v.", "n.a.", "k.a.",
    "keine angabe", "nicht verfügbar", "entfällt", "/", "x",
}


def normalize_bezirk(wert: Any) -> str | None:
    """Normalisiert einen Bezirksnamen auf offizielle Schreibweise.

    Args:
        wert: Roher Bezirksname.

    Returns:
        Normalisierter Bezirksname oder None wenn unbekannt.
    """
    if pd.isna(wert):
        return None
    key = str(wert).strip().lower()
    # Umlaute normalisieren für Lookup
    key_norm = key.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return BEZIRK_MAP.get(key, BEZIRK_MAP.get(key_norm))


def normalize_fehlwerte(df: pd.DataFrame) -> pd.DataFrame:
    """Ersetzt typische Fehlwert-Tokens durch echte NaN-Werte.

    Args:
        df: Roher DataFrame.

    Returns:
        DataFrame mit expliziten NaN-Fehlwerten.
    """
    df = df.copy()
    for col in df.columns:
        dtype_name = df[col].dtype.name.lower()
        if dtype_name in ("object", "str") or dtype_name.startswith("string"):
            df[col] = df[col].apply(
                lambda v: None if (v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip().lower() in FEHLWERT_TOKENS) else v
            )
    return df


def normalize_jahresspalte(serie: pd.Series) -> pd.Series:
    """Konvertiert eine Jahresspalte zu Integer.

    Args:
        serie: Rohe Jahresspalte.

    Returns:
        Spalte mit Integer-Jahren (NaN für ungültige Werte).
    """
    numerisch = pd.to_numeric(serie, errors="coerce")
    # Nur sinnvolle Jahreswerte behalten
    valid = numerisch.where((numerisch >= 1900) & (numerisch <= 2030))
    return valid.astype("Int64")


def normalize_dataset(
    df: pd.DataFrame,
    bezirk_spalte: str | None,
    jahr_spalte: str | None,
) -> pd.DataFrame:
    """Normalisiert einen kompletten Datensatz.

    Args:
        df: Roher DataFrame.
        bezirk_spalte: Name der Bezirksspalte (oder None).
        jahr_spalte: Name der Jahresspalte im Long-Format (oder None).

    Returns:
        Normalisierter DataFrame.
    """
    df = normalize_fehlwerte(df)

    if bezirk_spalte and bezirk_spalte in df.columns:
        df[bezirk_spalte] = df[bezirk_spalte].apply(normalize_bezirk)
        logger.debug("Bezirksspalte '%s' normalisiert", bezirk_spalte)

    if jahr_spalte and jahr_spalte in df.columns:
        df[jahr_spalte] = normalize_jahresspalte(df[jahr_spalte])
        logger.debug("Jahresspalte '%s' normalisiert", jahr_spalte)

    # Wide-Format: Jahres-Spaltenheader normalisieren
    JAHR_PATTERN = re.compile(r"^(19|20)\d{2}$")
    rename_map: dict[str, str] = {}
    for col in df.columns:
        if JAHR_PATTERN.match(str(col)):
            rename_map[col] = str(int(str(col).strip()))
    if rename_map:
        df = df.rename(columns=rename_map)

    return df
