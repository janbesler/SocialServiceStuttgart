"""Kernaggregationslogik: Bezirk-Level → Straßenabschnitt-Level.

Disaggregation in zwei Modi:
- count: Zählwerte (z.B. Anzahl SGB-II-Empfänger) werden proportional zur
  Straßenabschnittlänge im Bezirk verteilt.
- rate: Prozent-/Quoten-Werte (z.B. Eigentümerquote) werden direkt auf alle
  Segmente des Bezirks übertragen (keine Gewichtung nötig).
"""

import logging
from typing import Literal

import geopandas as gpd
import pandas as pd

from .confidence import KonfidenzStufe, konfidenz_fuer_methode

logger = logging.getLogger(__name__)

DisaggModus = Literal["count", "rate"]

# Normalisierungs-Mapping: kurze Bezirksnamen → offizielle Schreibweise
_BEZIRK_MAP: dict[str, str] = {
    "mitte": "Stuttgart-Mitte",
    "nord": "Stuttgart-Nord",
    "ost": "Stuttgart-Ost",
    "süd": "Stuttgart-Süd",
    "sued": "Stuttgart-Süd",
    "west": "Stuttgart-West",
    "bad cannstatt": "Bad Cannstatt",
    "cannstatt": "Bad Cannstatt",
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
    "stuttgart": "Stuttgart (gesamt)",
    "gesamt": "Stuttgart (gesamt)",
    "stadtgebiet": "Stuttgart (gesamt)",
}


def normalize_bezirk_name(name: str) -> str:
    """Normalisiert einen Bezirksnamen auf offizielle Schreibweise.

    Args:
        name: Roher Bezirksname (z.B. 'Mitte', 'S-Nord').

    Returns:
        Offizieller Bezirksname.
    """
    key = str(name).strip().lower()
    key = key.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    # Re-add umlaut lookup
    raw_key = str(name).strip().lower()
    return _BEZIRK_MAP.get(raw_key, _BEZIRK_MAP.get(key, str(name).strip()))


def compute_segment_weights(segmente: gpd.GeoDataFrame) -> pd.DataFrame:
    """Berechnet Längen-Gewichte pro Straßenabschnitt innerhalb jedes Bezirks.

    Gewicht = Länge_Segment / Gesamtlänge_aller_Segmente_im_Bezirk.
    Summe aller Gewichte pro Bezirk = 1.0.

    Args:
        segmente: Straßenabschnitte-GeoDataFrame mit Spalten 'segment_id',
                  'bezirk', 'laenge_m'.

    Returns:
        DataFrame mit Spalten: segment_id, bezirk, laenge_m, gewicht.
    """
    df = segmente[["segment_id", "bezirk", "laenge_m"]].copy()
    df = df[df["bezirk"] != "unbekannt"]

    gesamt_laenge = df.groupby("bezirk")["laenge_m"].transform("sum")
    df["gewicht"] = df["laenge_m"] / gesamt_laenge

    # Validierung: Summe der Gewichte pro Bezirk ≈ 1.0
    summe_check = df.groupby("bezirk")["gewicht"].sum()
    abweichung = (summe_check - 1.0).abs().max()
    if abweichung > 1e-6:
        logger.warning("Gewichts-Summe weicht ab (max %.2e), prüfe Daten", abweichung)

    return df.reset_index(drop=True)


def disaggregate_bezirk_to_segments(
    bezirk_df: pd.DataFrame,
    weights: pd.DataFrame,
    wert_spalten: list[str],
    bezirk_spalte: str,
    dataset_id: str,
    modus: DisaggModus = "count",
    raeumliche_ebene: str = "stadtbezirk",
) -> pd.DataFrame:
    """Disaggregiert Bezirk-Level-Daten auf Straßenabschnitte.

    Args:
        bezirk_df: DataFrame mit Bezirk-Werten. Muss bezirk_spalte enthalten.
        weights: Ausgabe von compute_segment_weights().
        wert_spalten: Spalten die disaggregiert werden sollen.
        bezirk_spalte: Name der Bezirksspalte in bezirk_df.
        dataset_id: Katalog-ID des Quelldatensatzes (für Konfidenz-Metadaten).
        modus: 'count' (Zählwerte) oder 'rate' (Prozent/Quoten).
        raeumliche_ebene: Räumliche Ebene der Quelldaten.

    Returns:
        DataFrame mit Spalten: segment_id, bezirk, {wert_spalten},
        {wert}_konfidenz, {wert}_methode, {wert}_unsicherheit.
    """
    methode = "laenge_gewichtet" if modus == "count" else "rate_bezirk"
    konfidenz: KonfidenzStufe = konfidenz_fuer_methode(methode, raeumliche_ebene)

    # Bezirksnamen normalisieren
    bezirk_df = bezirk_df.copy()
    bezirk_df[bezirk_spalte] = bezirk_df[bezirk_spalte].apply(normalize_bezirk_name)

    # Join: Segmente ← Bezirk-Werte
    merged = weights.merge(
        bezirk_df[[bezirk_spalte] + wert_spalten],
        left_on="bezirk",
        right_on=bezirk_spalte,
        how="left",
    )
    if bezirk_spalte != "bezirk":
        merged = merged.drop(columns=[bezirk_spalte])

    result = merged[["segment_id", "bezirk", "laenge_m", "gewicht"]].copy()

    for col in wert_spalten:
        quell_werte = merged[col]
        if modus == "count":
            result[col] = (quell_werte * merged["gewicht"]).round(4)
        else:
            # Raten direkt übernehmen
            result[col] = quell_werte

        result[f"{col}__konfidenz"] = konfidenz
        result[f"{col}__methode"] = methode
        result[f"{col}__quelldatensatz"] = dataset_id

    # Segmente ohne Bezirks-Match markieren
    fehlend = result[wert_spalten].isna().any(axis=1)
    if fehlend.sum() > 0:
        logger.debug(
            "%s: %d Segmente ohne Bezirks-Match (unbekannte Bezirke)",
            dataset_id, fehlend.sum(),
        )

    return result.drop(columns=["laenge_m", "gewicht"])


def disaggregate_timeseries(
    bezirk_df: pd.DataFrame,
    weights: pd.DataFrame,
    wert_spalten: list[str],
    bezirk_spalte: str,
    jahr_spalte: str,
    dataset_id: str,
    modus: DisaggModus = "count",
) -> pd.DataFrame:
    """Disaggregiert eine Zeitreihe (mehrere Jahre) auf Straßenabschnitte.

    Args:
        bezirk_df: DataFrame mit Bezirk-Zeitreihendaten.
        weights: Ausgabe von compute_segment_weights().
        wert_spalten: Spalten die disaggregiert werden sollen.
        bezirk_spalte: Name der Bezirksspalte.
        jahr_spalte: Name der Jahresspalte.
        dataset_id: Katalog-ID des Quelldatensatzes.
        modus: 'count' oder 'rate'.

    Returns:
        DataFrame mit Spalten: segment_id, bezirk, jahr, {wert_spalten}, Metadaten.
    """
    jahre = sorted(bezirk_df[jahr_spalte].dropna().unique())
    teile: list[pd.DataFrame] = []

    for jahr in jahre:
        jahr_data = bezirk_df[bezirk_df[jahr_spalte] == jahr].copy()
        disagg = disaggregate_bezirk_to_segments(
            bezirk_df=jahr_data,
            weights=weights,
            wert_spalten=wert_spalten,
            bezirk_spalte=bezirk_spalte,
            dataset_id=dataset_id,
            modus=modus,
        )
        disagg["jahr"] = int(jahr)
        teile.append(disagg)

    if not teile:
        return pd.DataFrame()

    return pd.concat(teile, ignore_index=True)
