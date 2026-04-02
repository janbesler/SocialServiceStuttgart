"""Synthetische Monatswerte aus jährlichen Bezirk-Indikatoren generieren.

Dieses Modul interpoliert jährliche disaggregierte Daten auf Monatsebene mittels
kubischer Spline-Interpolation (innerhalb bekannter Datenpunkte) und linearer
Extrapolation (über das letzte bekannte Jahr hinaus). Zusätzlich werden
saisonale Muster und bezirksspezifisches Rauschen aufgeprägt.

Alle synthetischen Monatswerte erhalten das Konfidenz-Flag "geschaetzt_niedrig"
und die Methode "temporal_synthetic".
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Saisonale Muster (Multiplikatoren, Summe ≈ 12 pro Zeile)
# ---------------------------------------------------------------------------

SEASONAL_PATTERNS: dict[str, list[float]] = {
    "employment": [
        0.98, 0.97, 0.99, 1.01, 1.02, 1.03,
        1.03, 1.02, 1.01, 1.00, 0.99, 0.97,
    ],
    "crime": [
        0.90, 0.88, 0.95, 1.00, 1.05, 1.10,
        1.12, 1.10, 1.05, 0.98, 0.92, 0.88,
    ],
    "transport": [
        1.05, 1.03, 1.02, 1.00, 0.98, 0.95,
        0.85, 0.85, 1.00, 1.05, 1.08, 1.10,
    ],
    "neutral": [1.0] * 12,
}

# Zuordnung Indikator-Präfix → Saison-Typ
INDICATOR_SEASON: dict[str, str] = {
    "sgbii_kinder": "employment",
    "sv_beschaeftigung": "employment",
    "jugend_arbeitslosigkeit": "employment",
    "kriminalitaet": "crime",
    "unfaelle": "crime",
    "ssb_fahrgaeste": "transport",
    "binnenumzuege": "neutral",
    "pkw_bestand": "neutral",
    "einwohner_kinder": "neutral",
    "eigentuemer_quote": "neutral",
    "sozialmietwohnungen": "neutral",
    "einkommen_index": "neutral",
    "wohnungsbestand": "neutral",
    "energie_verbrauch": "neutral",
    "luftqualitaet": "neutral",
    "laermbelastung": "neutral",
    "arztdichte": "neutral",
    "schulen_bezirk": "neutral",
}

# Indikatoren bei denen nur sehr kleine Variation sinnvoll ist (Raten/Indizes)
_RATE_INDICATORS: frozenset[str] = frozenset(
    {"eigentuemer_quote", "einkommen_index", "luftqualitaet", "laermbelastung", "arztdichte"}
)

# Bekannte Meta-Spalten die KEINE Wert-Spalten sind
_META_COLUMNS: frozenset[str] = frozenset(
    {"segment_id", "bezirk", "laenge_m", "jahr", "monat"}
)

# Zufallsgenerator mit festem Seed für Reproduzierbarkeit
_RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _detect_value_columns(df: pd.DataFrame) -> list[str]:
    """Ermittelt Wert-Spalten durch Ausschluss bekannter Meta-Spalten.

    Args:
        df: DataFrame aus einer disaggregierten Parquet-Datei.

    Returns:
        Liste der Spaltennamen die echte Messwerte enthalten (ohne Metadaten).
    """
    result: list[str] = []
    for col in df.columns:
        if col in _META_COLUMNS:
            continue
        if col.endswith("__konfidenz") or col.endswith("__methode") or col.endswith("__quelldatensatz"):
            continue
        result.append(col)
    return result


def _season_key_for_indicator(indicator: str) -> str:
    """Bestimmt den Saison-Typ für einen Indikator.

    Args:
        indicator: Name der Wertspalte.

    Returns:
        Schlüssel in SEASONAL_PATTERNS (z.B. "employment", "crime", "neutral").
    """
    for prefix, season in INDICATOR_SEASON.items():
        if indicator.startswith(prefix):
            return season
    return "neutral"


def _base_noise_for_indicator(indicator: str) -> float:
    """Gibt die Basis-Rauschstärke (Standardabweichung relativ) zurück.

    Raten-Indikatoren bekommen 1 % Rauschen, alle anderen 3 %.

    Args:
        indicator: Name der Wertspalte.

    Returns:
        Relative Standardabweichung als float (0.01 oder 0.03).
    """
    for rate_ind in _RATE_INDICATORS:
        if indicator.startswith(rate_ind):
            return 0.01
    return 0.03


def _linear_extrapolate(years: np.ndarray, values: np.ndarray, target_year: float) -> float:
    """Extrapoliert einen Wert linear aus den letzten 3 verfügbaren Datenpunkten.

    Args:
        years: Bekannte Jahreswerte (aufsteigend sortiert).
        values: Zugehörige Messwerte.
        target_year: Ziel-Jahr für die Extrapolation.

    Returns:
        Extrapolierter Wert (mindestens 0.0).
    """
    n = min(3, len(years))
    recent_years = years[-n:]
    recent_values = values[-n:]
    if len(recent_years) == 1:
        return float(recent_values[0])
    slope, intercept = np.polyfit(recent_years, recent_values, 1)
    return max(0.0, float(slope * target_year + intercept))


def _interpolate_annual_to_monthly(
    years: np.ndarray,
    values: np.ndarray,
    target_year: int,
    target_month: int,
) -> float:
    """Interpoliert oder extrapoliert einen monatlichen Wert aus Jahreswerten.

    Innerhalb des bekannten Zeitraums wird kubische Spline-Interpolation
    verwendet. Für Ziele außerhalb des bekannten Bereichs lineare Extrapolation.

    Args:
        years: Bekannte Jahreswerte (aufsteigend, ohne Duplikate).
        values: Zugehörige Jahreswerte.
        target_year: Ziel-Jahr.
        target_month: Ziel-Monat (1–12).

    Returns:
        Interpolierter / extrapolierter Wert (mindestens 0.0).
    """
    # Jahresbruchteil: Monat 1 → 0.0, Monat 7 → 0.5, Monat 12 → 11/12
    t = target_year + (target_month - 1) / 12.0

    min_year = float(years[0])
    max_year = float(years[-1])

    if t < min_year:
        # Extrapolation in die Vergangenheit (gespiegelt — selten benötigt)
        return _linear_extrapolate(years[::-1] * -1 + 2 * years[0], values[::-1], -t + 2 * min_year)

    if t > max_year:
        return _linear_extrapolate(years, values, t)

    # Kubische Spline-Interpolation (braucht mindestens 2 Punkte)
    if len(years) == 1:
        return max(0.0, float(values[0]))

    cs = CubicSpline(years, values, extrapolate=False)
    result = cs(t)
    # CubicSpline kann None zurückgeben wenn t außerhalb — zur Sicherheit abfangen
    if result is None or np.isnan(result):
        return _linear_extrapolate(years, values, t)
    return max(0.0, float(result))


# ---------------------------------------------------------------------------
# Kern-API
# ---------------------------------------------------------------------------


def generate_monthly_series(
    df: pd.DataFrame,
    value_col: str,
    years_back: int = 5,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Generiert monatliche synthetische Zeitreihe für eine Wert-Spalte.

    Für jede Kombination aus Segment und Bezirk werden monatliche Werte erzeugt
    durch:
    1. Kubische Spline-Interpolation zwischen Jahreswerten.
    2. Lineare Extrapolation über den letzten bekannten Jahreswert hinaus.
    3. Multiplikatives saisonales Muster (indikator-spezifisch).
    4. Bezirksspezifisches normalverteiltes Rauschen (kleiner für große Bezirke).

    Args:
        df: Jährliche disaggregierte Daten. Muss Spalten `segment_id`, `bezirk`,
            `jahr` und `value_col` enthalten.
        value_col: Name der zu verarbeitenden Wert-Spalte.
        years_back: Anzahl Jahre vor dem aktuellen Maximal-Jahr die generiert
            werden sollen (inklusive des Max-Jahres selbst).
        rng: Zufallsgenerator. Wenn None wird der Modul-Level-RNG verwendet.

    Returns:
        DataFrame mit monatlichen Werten. Enthält alle Original-Spalten plus
        `monat` (int 1–12). Konfidenz-Meta-Spalten werden auf
        "geschaetzt_niedrig" / "temporal_synthetic" gesetzt.
    """
    if rng is None:
        rng = _RNG

    if value_col not in df.columns:
        raise KeyError(f"Spalte '{value_col}' nicht im DataFrame gefunden.")

    max_year: int = int(df["jahr"].max())
    start_year: int = max_year - years_back + 1

    # Bezirk-Größe bestimmen (Anzahl Segmente als Proxy für Bevölkerungsgröße)
    segments_per_bezirk: dict[str, int] = (
        df.groupby("bezirk")["segment_id"].nunique().to_dict()
    )
    median_segments: float = float(np.median(list(segments_per_bezirk.values())))

    season_key = _season_key_for_indicator(value_col)
    seasonal = np.array(SEASONAL_PATTERNS[season_key], dtype=float)
    # Normalisiere auf Mittelwert 1.0 (damit Jahressum erhalten bleibt)
    seasonal = seasonal / seasonal.mean()

    base_noise = _base_noise_for_indicator(value_col)

    konfidenz_col = f"{value_col}__konfidenz"
    methode_col = f"{value_col}__methode"
    quelldatensatz_col = f"{value_col}__quelldatensatz"

    # Schneller Ansatz: Interpoliere auf BEZIRK-Ebene (23 statt 10.893 Gruppen),
    # dann verteile die Monatswerte proportional auf alle Segmente des Bezirks.
    # Der Anteil jedes Segments am Bezirkswert bleibt konstant über die Zeit.

    # Segment-Lookup: segment_id → (bezirk, laenge_m, anteil_am_bezirk)
    agg_dict = {"bezirk": ("bezirk", "first")}
    if "laenge_m" in df.columns:
        agg_dict["laenge_m"] = ("laenge_m", "first")
    seg_meta = df.groupby("segment_id").agg(**agg_dict)
    if "laenge_m" not in seg_meta.columns:
        seg_meta["laenge_m"] = 0.0

    # Quelldatensatz-Metadaten
    quelldatensatz = "unbekannt"
    if quelldatensatz_col in df.columns:
        quelldatensatz = str(df[quelldatensatz_col].dropna().iloc[0]) if df[quelldatensatz_col].notna().any() else "unbekannt"

    # Bezirk-Level: Durchschnittswert pro Bezirk pro Jahr
    bezirk_annual = df.groupby(["bezirk", "jahr"])[value_col].mean().reset_index()

    # Monatliche Bezirk-Werte generieren (23 Bezirke × ~60 Monate = ~1380 Zeilen)
    bezirk_monthly_rows: list[dict] = []

    for bezirk, bdf in bezirk_annual.groupby("bezirk"):
        ts = bdf[["jahr", value_col]].dropna(subset=[value_col]).sort_values("jahr")
        years_arr = ts["jahr"].to_numpy(dtype=float)
        values_arr = ts[value_col].to_numpy(dtype=float)
        n_years_available = len(years_arr)

        segs_in_bezirk = segments_per_bezirk.get(str(bezirk), 1)
        variance_factor = base_noise * (median_segments / max(1, segs_in_bezirk))
        variance_factor = min(variance_factor, base_noise * 3.0)

        for year in range(start_year, max_year + 1):
            for month in range(1, 13):
                if n_years_available == 0:
                    continue
                if n_years_available == 1:
                    base_value = max(0.0, float(values_arr[0]))
                else:
                    base_value = _interpolate_annual_to_monthly(
                        years_arr, values_arr, year, month
                    )
                seasonal_value = base_value * seasonal[month - 1]
                noise = rng.normal(loc=0.0, scale=max(1e-10, variance_factor * abs(seasonal_value)))
                final_value = max(0.0, seasonal_value + noise)

                bezirk_monthly_rows.append({
                    "bezirk": bezirk,
                    "jahr": year,
                    "monat": month,
                    value_col: final_value,
                })

    bezirk_monthly = pd.DataFrame(bezirk_monthly_rows)

    # Segment-Anteil am Bezirkswert berechnen (aus letztem verfügbaren Jahr)
    latest_year = df["jahr"].max()
    latest = df[df["jahr"] == latest_year][["segment_id", "bezirk", value_col]].copy()
    bezirk_totals = latest.groupby("bezirk")[value_col].sum()
    latest["_anteil"] = latest.apply(
        lambda r: r[value_col] / bezirk_totals.get(r["bezirk"], 1.0)
        if bezirk_totals.get(r["bezirk"], 0) > 0 else 0.0,
        axis=1,
    )
    anteil_map = dict(zip(latest["segment_id"], latest["_anteil"]))

    # Vectorized: merge bezirk_monthly mit seg_meta über bezirk, dann Anteil multiplizieren
    seg_lookup = seg_meta.reset_index()  # segment_id, bezirk, laenge_m
    seg_lookup["_anteil"] = seg_lookup["segment_id"].map(anteil_map).fillna(0.0)
    # Fallback: gleichmäßig verteilen wenn Anteil 0
    for bezirk, grp in seg_lookup.groupby("bezirk"):
        mask = (seg_lookup["bezirk"] == bezirk) & (seg_lookup["_anteil"] == 0.0)
        if mask.any():
            seg_lookup.loc[mask, "_anteil"] = 1.0 / max(1, mask.sum())

    result = bezirk_monthly.merge(seg_lookup, on="bezirk", how="inner")
    result[value_col] = (result[value_col] * result["_anteil"]).clip(lower=0.0)
    result[konfidenz_col] = "geschaetzt_niedrig"
    result[methode_col] = "temporal_synthetic"
    result[quelldatensatz_col] = quelldatensatz

    return result[["segment_id", "bezirk", "laenge_m", "jahr", "monat",
                    value_col, konfidenz_col, methode_col, quelldatensatz_col]]


def generate_temporal_data(
    disagg_dir: Path,
    output_dir: Path,
    years_back: int = 5,
) -> dict[str, object]:
    """Generiert synthetische Monatsdaten für alle Indikatoren in `disagg_dir`.

    Lädt jede Parquet-Datei aus `disagg_dir`, erkennt Wert-Spalten automatisch
    und schreibt monatliche Versionen nach `output_dir/temporal/`. Erstellt
    zusätzlich eine Metadaten-Zusammenfassung.

    Args:
        disagg_dir: Verzeichnis mit jährlichen disaggregierten Parquet-Dateien.
        output_dir: Zielverzeichnis. Unterordner `temporal/` wird angelegt.
        years_back: Anzahl Jahre vor dem letzten bekannten Jahr.

    Returns:
        Inhalt der erzeugten `temporal_meta.json` als dict.

    Raises:
        FileNotFoundError: Wenn `disagg_dir` nicht existiert.
        ValueError: Wenn keine Parquet-Dateien gefunden werden.
    """
    disagg_dir = Path(disagg_dir)
    output_dir = Path(output_dir)

    if not disagg_dir.exists():
        raise FileNotFoundError(f"Eingabe-Verzeichnis nicht gefunden: {disagg_dir}")

    temporal_dir = output_dir / "temporal"
    temporal_dir.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(disagg_dir.glob("*.parquet"))
    if not parquet_files:
        raise ValueError(f"Keine Parquet-Dateien in {disagg_dir} gefunden.")

    processed_indicators: list[str] = []
    global_min_year: int | None = None
    global_max_year: int | None = None

    for parquet_path in parquet_files:
        indicator_name = parquet_path.stem
        logger.info("Lade Parquet: %s", parquet_path.name)

        df = pd.read_parquet(parquet_path)

        value_cols = _detect_value_columns(df)
        if not value_cols:
            logger.warning("Keine Wert-Spalten in %s — überspringe.", parquet_path.name)
            continue

        max_year = int(df["jahr"].max())
        start_year = max_year - years_back + 1
        n_bezirke = df["bezirk"].nunique()

        # Globalen Zeitraum verfolgen
        if global_min_year is None or start_year < global_min_year:
            global_min_year = start_year
        if global_max_year is None or max_year > global_max_year:
            global_max_year = max_year

        monthly_dfs: list[pd.DataFrame] = []

        for value_col in value_cols:
            n_years = df["jahr"].nunique()
            logger.info(
                "Generating temporal data for %s: %d years × %d Bezirke × 12 months",
                value_col,
                n_years,
                n_bezirke,
            )
            monthly_df = generate_monthly_series(df, value_col, years_back=years_back)
            monthly_dfs.append(monthly_df)

        if not monthly_dfs:
            logger.warning("Keine monatlichen Daten erzeugt für %s.", parquet_path.name)
            continue

        # Mehrere Wert-Spalten zusammenführen (über segment_id + bezirk + laenge_m + jahr + monat)
        key_cols = ["segment_id", "bezirk", "laenge_m", "jahr", "monat"]
        combined = monthly_dfs[0]
        for extra_df in monthly_dfs[1:]:
            merge_cols = [c for c in extra_df.columns if c not in key_cols]
            combined = combined.merge(
                extra_df[key_cols + merge_cols],
                on=key_cols,
                how="outer",
            )

        out_path = temporal_dir / parquet_path.name
        combined.to_parquet(out_path, index=False)
        logger.info("Geschrieben: %s (%d Zeilen)", out_path, len(combined))
        processed_indicators.append(indicator_name)

    # Metadaten-Datei
    meta: dict[str, object] = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "indicators": processed_indicators,
        "date_range": {
            "start": f"{global_min_year}-01" if global_min_year is not None else "unbekannt",
            "end": f"{global_max_year}-12" if global_max_year is not None else "unbekannt",
        },
        "method": "cubic_spline_interpolation_with_seasonal_adjustment",
        "years_back": years_back,
        "konfidenz": "geschaetzt_niedrig",
        "n_indicators": len(processed_indicators),
    }

    meta_path = temporal_dir / "temporal_meta.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    logger.info("Metadaten geschrieben: %s", meta_path)

    return meta


# ---------------------------------------------------------------------------
# Standalone-Aufruf
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Synthetische Monatsdaten aus jährlichen Bezirk-Indikatoren generieren."
    )
    parser.add_argument(
        "--disagg-dir",
        type=Path,
        default=Path("data/disaggregated"),
        help="Verzeichnis mit disaggregierten Jahres-Parquet-Dateien (Standard: data/disaggregated).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/disaggregated"),
        help="Ausgabe-Verzeichnis; Unterordner 'temporal/' wird angelegt (Standard: data/disaggregated).",
    )
    parser.add_argument(
        "--years-back",
        type=int,
        default=5,
        help="Anzahl Jahre rückwirkend ab dem letzten Datenjahr (Standard: 5).",
    )
    args = parser.parse_args()

    result = generate_temporal_data(
        disagg_dir=args.disagg_dir,
        output_dir=args.output_dir,
        years_back=args.years_back,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
