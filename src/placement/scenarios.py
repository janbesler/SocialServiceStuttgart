"""Orchestrierung aller Standortszenarien für Phase 6.

Szenarien:
- baseline          – Nur Bestand, keine neuen Stellen
- n1_optimal        – 1 neue Stelle (MCLP)
- n3_optimal        – 3 neue Stellen (MCLP)
- n5_optimal        – 5 neue Stellen (MCLP)
- n10_optimal       – 10 neue Stellen (MCLP)
- budget_100k       – max. Stellen für 100.000 € Jahresbudget (MCLP)
- budget_300k       – max. Stellen für 300.000 € Jahresbudget (MCLP)
- budget_500k       – max. Stellen für 500.000 € Jahresbudget (MCLP)

Ausgabe:
- `data/placement/szenarien/{szenario}.geojson`  – empfohlene Standorte
- `data/placement/kosten_nutzen.json`             – Zusammenfassung aller Szenarien
"""

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

from .cost_model import KOSTEN_DEFAULTS, berechne_kosten
from .impact import _segment_centroids_utm, _standorte_coords_utm, berechne_wirkung
from .optimizer import solve_mclp

logger = logging.getLogger(__name__)

WGS84 = "EPSG:4326"

# Jahresbudgets in Euro
BUDGET_SZENARIEN: dict[str, float] = {
    "budget_100k": 100_000.0,
    "budget_300k": 300_000.0,
    "budget_500k": 500_000.0,
}

# Anzahl-Szenarien
N_SZENARIEN: dict[str, int] = {
    "n1_optimal": 1,
    "n3_optimal": 3,
    "n5_optimal": 5,
    "n10_optimal": 10,
}


def _max_stellen_fuer_budget(
    budget: float,
    kosten_params: dict[str, float] | None = None,
) -> int:
    """Berechnet die maximale Stellenanzahl bei gegebenem Jahresbudget.

    Nimmt den günstigsten Fall (öffentliches Gebäude) als Basis.

    Args:
        budget: Jahresbudget in Euro.
        kosten_params: Optionale Kostenparameter-Überschreibungen.

    Returns:
        Maximale Anzahl Stellen (mindestens 1).
    """
    params = KOSTEN_DEFAULTS.copy()
    if kosten_params:
        params.update(kosten_params)

    kosten_pro_stelle = (
        params["personal_s11b_jahr"]
        + params["miete_oeffentlich_jahr"]
        + params["sachkosten_jahr"]
    )
    n = max(1, int(budget // kosten_pro_stelle))
    logger.debug(
        "Budget %.0f € → max. %d Stellen (%.0f €/Stelle angenommen)",
        budget,
        n,
        kosten_pro_stelle,
    )
    return n


def _szenario_zusammenfassung(
    szenario_name: str,
    bestand_gdf: gpd.GeoDataFrame,
    neue_standorte_gdf: gpd.GeoDataFrame,
    bedarf_gdf: gpd.GeoDataFrame,
    radius_m: float = 800.0,
    walking_factor: float = 1.4,
) -> dict:
    """Berechnet Kennzahlen für ein einzelnes Szenario.

    Args:
        szenario_name: Bezeichner des Szenarios.
        bestand_gdf: Bestehende Einrichtungen.
        neue_standorte_gdf: Neue empfohlene Standorte.
        bedarf_gdf: Segmente mit `bedarf_roh` und `bedarf_unversorgt`.
        radius_m: Wirkungsradius in Meter.
        walking_factor: Faktor Luftlinie → Gehweg.

    Returns:
        Dict mit Kennzahlen für das Szenario.
    """
    alle_standorte = gpd.GeoDataFrame(
        _concat_gdfs(bestand_gdf, neue_standorte_gdf), crs=WGS84
    )

    # Wirkung und Kosten berechnen (nur für neue Standorte)
    if len(neue_standorte_gdf) > 0:
        neue_mit_kosten = berechne_wirkung(
            neue_standorte_gdf, bedarf_gdf, radius_m, walking_factor
        )
        neue_mit_kosten = berechne_kosten(neue_mit_kosten)
        gesamtkosten_jahr = float(neue_mit_kosten["gesamtkosten_jahr"].sum())
        einmalkosten_gesamt = float(neue_mit_kosten["einmalkosten"].sum())
        erreichte_kinder_neu = float(neue_mit_kosten["erreichte_kinder"].sum())
    else:
        gesamtkosten_jahr = 0.0
        einmalkosten_gesamt = 0.0
        erreichte_kinder_neu = 0.0

    # Gesamtabdeckung (alle Standorte)
    effektiver_radius = radius_m / walking_factor
    seg_coords = _segment_centroids_utm(bedarf_gdf)
    stand_coords = _standorte_coords_utm(alle_standorte) if len(alle_standorte) > 0 else None

    if stand_coords is not None and len(stand_coords) > 0:
        dist = cdist(seg_coords, stand_coords, metric="euclidean")
        im_radius = dist.min(axis=1) <= effektiver_radius
        decay = np.clip(1.0 - dist / effektiver_radius, 0.0, 1.0)
        max_decay = decay.max(axis=1)
    else:
        im_radius = np.zeros(len(bedarf_gdf), dtype=bool)
        max_decay = np.zeros(len(bedarf_gdf))

    bedarf_arr = bedarf_gdf["bedarf_unversorgt"].fillna(0.0).values

    abgedeckter_bedarf = float((bedarf_arr * max_decay).sum())
    bedarf_gesamt = float(bedarf_arr.sum())
    anteil_abgedeckt = abgedeckter_bedarf / max(bedarf_gesamt, 1e-9)

    return {
        "szenario": szenario_name,
        "n_neue_stellen": len(neue_standorte_gdf),
        "n_bestand": len(bestand_gdf),
        "gesamtkosten_jahr_eur": round(gesamtkosten_jahr, 0),
        "einmalkosten_eur": round(einmalkosten_gesamt, 0),
        "erreichte_kinder_neu": round(erreichte_kinder_neu, 0),
        "abgedeckter_bedarf": round(abgedeckter_bedarf, 1),
        "bedarf_gesamt": round(bedarf_gesamt, 1),
        "anteil_bedarf_abgedeckt_pct": round(anteil_abgedeckt * 100, 1),
        "segmente_im_radius": int(im_radius.sum()),
        "segmente_gesamt": len(bedarf_gdf),
    }


def _concat_gdfs(gdf1: gpd.GeoDataFrame, gdf2: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Verbindet zwei GeoDataFrames sicher (behandelt leere DataFrames).

    Args:
        gdf1: Erster GeoDataFrame.
        gdf2: Zweiter GeoDataFrame.

    Returns:
        Kombinierter GeoDataFrame in WGS84.
    """
    teile = []
    if len(gdf1) > 0:
        teile.append(gdf1.to_crs(WGS84))
    if len(gdf2) > 0:
        teile.append(gdf2.to_crs(WGS84))

    if not teile:
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    return gpd.GeoDataFrame(pd.concat(teile, ignore_index=True), crs=WGS84)


def _schreibe_szenario_geojson(
    bestand_gdf: gpd.GeoDataFrame,
    neue_gdf: gpd.GeoDataFrame,
    pfad: Path,
    szenario_name: str,
) -> None:
    """Schreibt ein Szenario-GeoJSON mit Bestand + Empfehlungen + Wirkungskreisen.

    Das GeoJSON enthält:
    - Bestehende Einrichtungen (ist_empfehlung=false)
    - Empfohlene neue Standorte (ist_empfehlung=true)
    - Wirkungskreis-Polygone für empfohlene Standorte (typ=coverage_ring)
    """
    import json as _json
    from shapely.geometry import mapping

    features: list[dict] = []

    # Bestehende Einrichtungen
    for _, row in bestand_gdf.to_crs(WGS84).iterrows():
        props = {
            "standort_id": str(row.get("standort_id", "")),
            "name": str(row.get("name", "Unbenannt")),
            "typ": str(row.get("typ", "sonstige")),
            "ist_empfehlung": False,
        }
        features.append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": props,
        })

    # Empfohlene Standorte + Wirkungskreise
    if len(neue_gdf) > 0:
        neue_wgs = neue_gdf.to_crs(WGS84) if neue_gdf.crs != WGS84 else neue_gdf
        for _, row in neue_wgs.iterrows():
            sid = str(row.get("standort_id", row.get("candidate_id", "")))
            props = {
                "standort_id": sid,
                "name": str(row.get("name", "Unbenannt")),
                "typ": str(row.get("standort_typ", row.get("amenity", ""))),
                "ist_empfehlung": True,
                "kosten_jahr": float(row.get("gesamtkosten_jahr", 0)),
                "erreichte_kinder": int(row.get("erreichte_kinder", 0)),
                "abgedeckter_bedarf": round(float(row.get("abgedeckter_bedarf", 0)), 1),
            }
            features.append({
                "type": "Feature",
                "geometry": mapping(row.geometry),
                "properties": props,
            })

            # Wirkungskreis als separates Polygon-Feature
            if "wirkungskreis" in row.index and row["wirkungskreis"] is not None:
                features.append({
                    "type": "Feature",
                    "geometry": mapping(row["wirkungskreis"]),
                    "properties": {
                        "standort_id": sid,
                        "typ": "coverage_ring",
                        "ist_empfehlung": True,
                    },
                })

    geojson = {"type": "FeatureCollection", "features": features}
    pfad.write_text(_json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
    size_kb = pfad.stat().st_size / 1024
    logger.info("  Szenario '%s' → %s (%.1f KB, %d Features)", szenario_name, pfad.name, size_kb, len(features))


def generate_all(
    bedarf_gdf: gpd.GeoDataFrame,
    kandidaten_gdf: gpd.GeoDataFrame,
    bestand_gdf: gpd.GeoDataFrame,
    ausgabe_dir: Path | None = None,
    radius_m: float = 800.0,
    walking_factor: float = 1.4,
    kosten_params: dict[str, float] | None = None,
) -> dict:
    """Berechnet und schreibt alle Standort-Szenarien.

    Args:
        bedarf_gdf: Straßenabschnitte mit `bedarf_unversorgt`, `kinder`, `bedarf_roh`.
        kandidaten_gdf: Kandidatenstandorte.
        bestand_gdf: Bestehende Einrichtungen.
        ausgabe_dir: Verzeichnis für GeoJSON-Ausgaben. Standard: `data/placement/szenarien/`.
        radius_m: Wirkungsradius in Meter.
        walking_factor: Faktor Luftlinie → Gehweg.
        kosten_params: Optionale Kostenparameter-Überschreibungen.

    Returns:
        Dict mit Zusammenfassungen aller Szenarien
        (wird auch als `kosten_nutzen.json` gespeichert).
    """
    if ausgabe_dir is None:
        base = Path(__file__).resolve().parents[2]
        ausgabe_dir = base / "data" / "placement" / "szenarien"

    ausgabe_dir.mkdir(parents=True, exist_ok=True)
    zusammenfassungen: dict[str, dict] = {}

    # --- Baseline-Szenario (nur Bestand) ---
    logger.info("=== Szenario: baseline ===")
    basis_zf = _szenario_zusammenfassung(
        "baseline", bestand_gdf,
        gpd.GeoDataFrame({"geometry": []}, crs=WGS84),
        bedarf_gdf, radius_m, walking_factor,
    )
    zusammenfassungen["baseline"] = basis_zf

    # Baseline GeoJSON (nur Bestand, keine Empfehlungen)
    _schreibe_szenario_geojson(
        bestand_gdf, gpd.GeoDataFrame({"geometry": []}, crs=WGS84),
        ausgabe_dir / "baseline.geojson", "baseline",
    )

    # --- Anzahl-Szenarien (MCLP) ---
    for szenario_name, n_neue in N_SZENARIEN.items():
        logger.info("=== Szenario: %s (n=%d) ===", szenario_name, n_neue)
        neue_standorte = solve_mclp(
            bedarf_gdf, kandidaten_gdf, bestand_gdf,
            n_neue=n_neue, radius_m=radius_m, walking_factor=walking_factor,
        )

        if len(neue_standorte) > 0:
            neue_standorte = berechne_wirkung(neue_standorte, bedarf_gdf, radius_m, walking_factor)
            neue_standorte = berechne_kosten(neue_standorte, kosten_params)

        _schreibe_szenario_geojson(bestand_gdf, neue_standorte, ausgabe_dir / f"{szenario_name}.geojson", szenario_name)

        zf = _szenario_zusammenfassung(
            szenario_name, bestand_gdf, neue_standorte, bedarf_gdf, radius_m, walking_factor
        )
        zusammenfassungen[szenario_name] = zf

    # --- Budget-Szenarien ---
    for szenario_name, budget in BUDGET_SZENARIEN.items():
        n_max = _max_stellen_fuer_budget(budget, kosten_params)
        logger.info("=== Szenario: %s (budget=%.0f €, max n=%d) ===", szenario_name, budget, n_max)
        neue_standorte = solve_mclp(
            bedarf_gdf, kandidaten_gdf, bestand_gdf,
            n_neue=n_max, radius_m=radius_m, walking_factor=walking_factor,
        )

        if len(neue_standorte) > 0:
            neue_standorte = berechne_wirkung(neue_standorte, bedarf_gdf, radius_m, walking_factor)
            neue_standorte = berechne_kosten(neue_standorte, kosten_params)

            # Budgetkontrolle: Falls Gesamtkosten > Budget, kürzen
            if "gesamtkosten_jahr" in neue_standorte.columns:
                cumkosten = neue_standorte["gesamtkosten_jahr"].cumsum()
                neue_standorte = neue_standorte[cumkosten <= budget].copy()
                if len(neue_standorte) < n_max:
                    logger.info(
                        "  Budget %s: auf %d Standorte reduziert (Budget %.0f €)",
                        szenario_name, len(neue_standorte), budget,
                    )

        _schreibe_szenario_geojson(bestand_gdf, neue_standorte, ausgabe_dir / f"{szenario_name}.geojson", szenario_name)

        zf = _szenario_zusammenfassung(
            szenario_name, bestand_gdf, neue_standorte, bedarf_gdf, radius_m, walking_factor
        )
        zf["budget_eur"] = budget
        zusammenfassungen[szenario_name] = zf

    # --- kosten_nutzen.json schreiben ---
    kosten_nutzen_pfad = ausgabe_dir.parent / "kosten_nutzen.json"
    kosten_nutzen = {
        "szenarien": zusammenfassungen,
        "parameter": {
            "radius_m": radius_m,
            "walking_factor": walking_factor,
            "n_kandidaten": len(kandidaten_gdf),
            "n_bestand": len(bestand_gdf),
            "n_segmente": len(bedarf_gdf),
            "kosten_defaults": {k: v for k, v in (kosten_params or {}).items()}
            if kosten_params
            else KOSTEN_DEFAULTS,
        },
    }

    with kosten_nutzen_pfad.open("w", encoding="utf-8") as fh:
        json.dump(kosten_nutzen, fh, ensure_ascii=False, indent=2)

    logger.info("kosten_nutzen.json geschrieben: %s", kosten_nutzen_pfad.name)

    return kosten_nutzen
