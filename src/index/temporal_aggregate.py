"""Aggregiert temporale Segment-Daten zu quartalsweisen Bezirk-Durchschnitten.

Eingabe: data/disaggregated/temporal/*.parquet (monatlich, Segment-Ebene)
Ausgabe: data/indices/temporal_quarterly.json (quartalsweise, Bezirk-Ebene)

Das JSON wird vom Dashboard geladen für Trend-Charts.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .dimensions import DIMENSIONEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
TEMPORAL_DIR = BASE / "data" / "disaggregated" / "temporal"
INDEX_DIR = BASE / "data" / "indices"


def aggregate_quarterly() -> dict:
    """Aggregiert monatliche Segment-Daten zu Quartals-Bezirk-Durchschnitten.

    Returns:
        Dict mit Struktur:
        {
            "quarters": ["2018-Q1", "2018-Q2", ...],
            "bezirke": ["Stuttgart-Mitte", ...],
            "dimensions": {
                "oekonomie": {
                    "Stuttgart-Mitte": [45.2, 44.8, ...],
                    ...
                },
                ...
            },
            "gesamt": {
                "Stuttgart-Mitte": [42.1, 41.5, ...],
                ...
            }
        }
    """
    if not TEMPORAL_DIR.exists():
        logger.error("Temporales Verzeichnis nicht gefunden: %s", TEMPORAL_DIR)
        return {}

    # Lade alle verfügbaren temporalen Indikatoren
    all_bezirk_quarterly: dict[str, pd.DataFrame] = {}

    for dim in DIMENSIONEN:
        for ind in dim.indikatoren:
            path = TEMPORAL_DIR / f"{ind.datensatz}.parquet"
            if not path.exists():
                continue

            df = pd.read_parquet(path)
            if "monat" not in df.columns or "jahr" not in df.columns:
                continue
            if ind.spalte not in df.columns:
                continue

            # Quartal berechnen
            df["quartal"] = ((df["monat"] - 1) // 3 + 1).astype(int)
            df["quarter_label"] = df["jahr"].astype(int).astype(str) + "-Q" + df["quartal"].astype(str)

            # Bezirk-Quartal-Durchschnitt
            bezirk_q = (
                df.groupby(["bezirk", "quarter_label"])[ind.spalte]
                .mean()
                .reset_index()
            )

            key = f"{ind.datensatz}__{ind.spalte}"
            all_bezirk_quarterly[key] = bezirk_q.rename(columns={ind.spalte: "value"})

    if not all_bezirk_quarterly:
        logger.warning("Keine temporalen Daten gefunden")
        return {}

    # Alle Quartale und Bezirke sammeln
    all_quarters = set()
    all_bezirke = set()
    for df in all_bezirk_quarterly.values():
        all_quarters.update(df["quarter_label"].unique())
        all_bezirke.update(df["bezirk"].unique())

    quarters = sorted(all_quarters)
    bezirke = sorted(all_bezirke)

    # Letzte 3 Jahre (12 Quartale) für den Selector
    if len(quarters) > 12:
        quarters = quarters[-12:]

    logger.info("Quartale: %d (%s bis %s)", len(quarters), quarters[0], quarters[-1])
    logger.info("Bezirke: %d", len(bezirke))

    # Pro Dimension: normalisiere und aggregiere Indikatoren zu Dimensions-Score
    result = {
        "quarters": quarters,
        "bezirke": bezirke,
        "dimensions": {},
        "gesamt": {},
    }

    dim_scores_all: dict[str, dict[str, list]] = {}

    for dim in DIMENSIONEN:
        dim_bezirk_scores: dict[str, list[float | None]] = {b: [] for b in bezirke}

        for q_idx, q in enumerate(quarters):
            # Sammle Indikator-Werte für dieses Quartal
            ind_values: dict[str, dict[str, float]] = {}

            for ind in dim.indikatoren:
                key = f"{ind.datensatz}__{ind.spalte}"
                if key not in all_bezirk_quarterly:
                    continue
                df = all_bezirk_quarterly[key]
                q_data = df[df["quarter_label"] == q]
                if q_data.empty:
                    continue
                ind_values[key] = dict(zip(q_data["bezirk"], q_data["value"]))

            # Einfacher Score: Mittelwert der Rohwerte pro Bezirk (nicht normalisiert,
            # für Trenddarstellung reicht die relative Veränderung)
            for b in bezirke:
                vals = []
                weights = []
                for ind in dim.indikatoren:
                    key = f"{ind.datensatz}__{ind.spalte}"
                    if key in ind_values and b in ind_values[key]:
                        v = ind_values[key][b]
                        if not np.isnan(v):
                            vals.append(v)
                            weights.append(ind.gewicht)

                if vals:
                    w = np.array(weights)
                    w = w / w.sum()
                    score = float(np.average(vals, weights=w))
                    dim_bezirk_scores[b].append(round(score, 2))
                else:
                    dim_bezirk_scores[b].append(None)

        dim_scores_all[dim.key] = dim_bezirk_scores
        result["dimensions"][dim.key] = dim_bezirk_scores

    # Gesamt-Score: Durchschnitt über Dimensionen pro Bezirk pro Quartal
    for b in bezirke:
        gesamt = []
        for q_idx in range(len(quarters)):
            dim_vals = []
            dim_weights = []
            for dim in DIMENSIONEN:
                v = dim_scores_all[dim.key][b][q_idx]
                if v is not None:
                    dim_vals.append(v)
                    dim_weights.append(dim.gewicht)
            if dim_vals:
                w = np.array(dim_weights)
                w = w / w.sum()
                gesamt.append(round(float(np.average(dim_vals, weights=w)), 2))
            else:
                gesamt.append(None)
        result["gesamt"][b] = gesamt

    return result


def main() -> None:
    """Aggregiert und schreibt temporal_quarterly.json."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    result = aggregate_quarterly()
    if not result:
        logger.error("Keine Daten zum Aggregieren")
        return

    out_path = INDEX_DIR / "temporal_quarterly.json"
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    logger.info("Temporal-Quartals-JSON geschrieben: %s (%.0f KB)", out_path.name, size_kb)
    logger.info("Quartale: %d, Bezirke: %d, Dimensionen: %d",
                len(result["quarters"]), len(result["bezirke"]),
                len(result["dimensions"]))


if __name__ == "__main__":
    main()
