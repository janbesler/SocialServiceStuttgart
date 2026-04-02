"""Tests für Phase 4: Index-Berechnung."""

import numpy as np
import pytest
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import LineString

from src.index.dimensions import DIMENSIONEN, DimensionDef, IndikatorDef
from src.index.aufwachsindex import (
    berechne_aufwachsindex,
    berechne_dimension_score,
    _lade_indikator,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def segmente_gdf() -> gpd.GeoDataFrame:
    """10 Straßenabschnitte in 2 Bezirken."""
    n = 10
    return gpd.GeoDataFrame(
        {
            "segment_id": [f"seg_{i:03d}" for i in range(n)],
            "bezirk": (["Stuttgart-Mitte"] * 5 + ["Stuttgart-Nord"] * 5),
            "laenge_m": [100.0, 200.0, 150.0, 300.0, 250.0,
                         120.0, 180.0, 90.0, 220.0, 140.0],
            "highway": ["primary"] * n,
            "name": [f"Straße {i}" for i in range(n)],
            "stadtteil": ["unbekannt"] * n,
            "geometry": [LineString([(i, 0), (i+1, 0)]) for i in range(n)],
        },
        crs="EPSG:4326",
    )


@pytest.fixture()
def tmp_disagg_dir(tmp_path: Path, segmente_gdf: gpd.GeoDataFrame) -> Path:
    """Temporäres Disaggregations-Verzeichnis mit Minimal-Daten."""
    disagg = tmp_path / "disaggregated"
    disagg.mkdir()

    seg_ids = segmente_gdf["segment_id"].tolist()
    laengen = dict(zip(seg_ids, segmente_gdf["laenge_m"]))
    bezirke = dict(zip(seg_ids, segmente_gdf["bezirk"]))

    jahre = [2021, 2022]
    rows = []
    for jahr in jahre:
        for sid in seg_ids:
            rows.append({"segment_id": sid, "bezirk": bezirke[sid],
                         "laenge_m": laengen[sid], "jahr": jahr})
    base = pd.DataFrame(rows)

    # Einwohner-Kinder
    kinder = base.copy()
    kinder["einwohner_kinder_0_17"] = np.random.uniform(10, 100, len(kinder))
    kinder["einwohner_kinder_0_17__konfidenz"] = "geschaetzt_mittel"
    kinder["einwohner_kinder_0_17__methode"] = "laenge_gewichtet"
    kinder["einwohner_kinder_0_17__quelldatensatz"] = "einwohner_kinder"
    kinder.to_parquet(disagg / "einwohner_kinder.parquet", index=False)

    # SGB-II
    sgbii = base.copy()
    sgbii["sgbii_kinder_unter18"] = np.random.uniform(1, 20, len(sgbii))
    sgbii["sgbii_kinder_unter18__konfidenz"] = "geschaetzt_mittel"
    sgbii["sgbii_kinder_unter18__methode"] = "laenge_gewichtet"
    sgbii["sgbii_kinder_unter18__quelldatensatz"] = "sgbii_kinder"
    sgbii.to_parquet(disagg / "sgbii_kinder.parquet", index=False)

    # Einkommen (nur 2017)
    eink = base[base["jahr"] == 2022].copy()
    eink["einkommen_index"] = np.random.uniform(80, 130, len(eink))
    eink["einkommen_index__konfidenz"] = "geschaetzt_hoch"
    eink["einkommen_index__methode"] = "rate_bezirk"
    eink["einkommen_index__quelldatensatz"] = "einkommen_index"
    eink.to_parquet(disagg / "einkommen_index.parquet", index=False)

    # SV-Beschäftigung
    sv = base.copy()
    sv["sv_beschaeftigte"] = np.random.uniform(100, 1000, len(sv))
    sv["sv_beschaeftigte__konfidenz"] = "geschaetzt_mittel"
    sv["sv_beschaeftigte__methode"] = "laenge_gewichtet"
    sv["sv_beschaeftigte__quelldatensatz"] = "sv_beschaeftigung"
    sv.to_parquet(disagg / "sv_beschaeftigung.parquet", index=False)

    # Kriminalität
    krim = base.copy()
    krim["strassenkriminalitaet_faelle"] = np.random.uniform(0, 100, len(krim))
    krim["strassenkriminalitaet_faelle__konfidenz"] = "geschaetzt_mittel"
    krim["strassenkriminalitaet_faelle__methode"] = "laenge_gewichtet"
    krim["strassenkriminalitaet_faelle__quelldatensatz"] = "kriminalitaet"
    krim.to_parquet(disagg / "kriminalitaet.parquet", index=False)

    # Unfälle
    unf = base.copy()
    unf["unfaelle_gesamt"] = np.random.uniform(0, 30, len(unf))
    unf["unfaelle_gesamt__konfidenz"] = "geschaetzt_mittel"
    unf["unfaelle_gesamt__methode"] = "laenge_gewichtet"
    unf["unfaelle_gesamt__quelldatensatz"] = "unfaelle"
    unf.to_parquet(disagg / "unfaelle.parquet", index=False)

    # Eigentümerquote (Rate)
    eig = base.copy()
    eig["eigentuemer_quote_pct"] = np.random.uniform(10, 40, len(eig))
    eig["eigentuemer_quote_pct__konfidenz"] = "geschaetzt_hoch"
    eig["eigentuemer_quote_pct__methode"] = "rate_bezirk"
    eig["eigentuemer_quote_pct__quelldatensatz"] = "eigentuemer_quote"
    eig.to_parquet(disagg / "eigentuemer_quote.parquet", index=False)

    # Sozialmietwohnungen
    soz = base[base["jahr"] == 2022].copy()
    soz["sozialmietwohnungen"] = np.random.uniform(0, 50, len(soz))
    soz["sozialmietwohnungen__konfidenz"] = "geschaetzt_mittel"
    soz["sozialmietwohnungen__methode"] = "laenge_gewichtet"
    soz["sozialmietwohnungen__quelldatensatz"] = "sozialmietwohnungen"
    soz.to_parquet(disagg / "sozialmietwohnungen.parquet", index=False)

    # Binnenumzüge
    binn = base.copy()
    binn["binnenumzuege"] = np.random.uniform(10, 200, len(binn))
    binn["binnenumzuege__konfidenz"] = "geschaetzt_mittel"
    binn["binnenumzuege__methode"] = "laenge_gewichtet"
    binn["binnenumzuege__quelldatensatz"] = "binnenumzuege"
    binn.to_parquet(disagg / "binnenumzuege.parquet", index=False)

    # PKW
    pkw = base.copy()
    pkw["pkw_gesamt"] = np.random.uniform(100, 2000, len(pkw))
    pkw["pkw_gesamt__konfidenz"] = "geschaetzt_mittel"
    pkw["pkw_gesamt__methode"] = "laenge_gewichtet"
    pkw["pkw_gesamt__quelldatensatz"] = "pkw_bestand"
    pkw.to_parquet(disagg / "pkw_bestand.parquet", index=False)

    # Schulen (Gymnasialquote)
    schul = base.copy()
    schul["gymnasium_anteil"] = np.random.uniform(0.3, 0.7, len(schul))
    schul["gymnasium_anteil__konfidenz"] = "geschaetzt_mittel"
    schul["gymnasium_anteil__methode"] = "rate_bezirk"
    schul["gymnasium_anteil__quelldatensatz"] = "schulen_bezirk"
    schul.to_parquet(disagg / "schulen_bezirk.parquet", index=False)

    # Jugendarbeitslosigkeit
    jarb = base.copy()
    jarb["jugend_arbeitslose"] = np.random.uniform(5, 50, len(jarb))
    jarb["jugend_arbeitslose__konfidenz"] = "geschaetzt_mittel"
    jarb["jugend_arbeitslose__methode"] = "laenge_gewichtet"
    jarb["jugend_arbeitslose__quelldatensatz"] = "jugend_arbeitslosigkeit"
    jarb.to_parquet(disagg / "jugend_arbeitslosigkeit.parquet", index=False)

    # Energieverbrauch
    ener = base.copy()
    ener["energie_verbrauch"] = np.random.uniform(50, 200, len(ener))
    ener["energie_verbrauch__konfidenz"] = "geschaetzt_niedrig"
    ener["energie_verbrauch__methode"] = "laenge_gewichtet"
    ener["energie_verbrauch__quelldatensatz"] = "energie_verbrauch"
    ener.to_parquet(disagg / "energie_verbrauch.parquet", index=False)

    # Arztdichte (Rate)
    arzt = base.copy()
    arzt["arztdichte"] = np.random.uniform(30, 60, len(arzt))
    arzt["arztdichte__konfidenz"] = "geschaetzt_niedrig"
    arzt["arztdichte__methode"] = "rate_bezirk"
    arzt["arztdichte__quelldatensatz"] = "arztdichte"
    arzt.to_parquet(disagg / "arztdichte.parquet", index=False)

    # Luftqualität (Rate)
    luft = base.copy()
    luft["luftqualitaet"] = np.random.uniform(30, 90, len(luft))
    luft["luftqualitaet__konfidenz"] = "geschaetzt_niedrig"
    luft["luftqualitaet__methode"] = "rate_bezirk"
    luft["luftqualitaet__quelldatensatz"] = "luftqualitaet"
    luft.to_parquet(disagg / "luftqualitaet.parquet", index=False)

    # Lärmbelastung (Rate)
    laerm = base.copy()
    laerm["laermbelastung"] = np.random.uniform(5, 25, len(laerm))
    laerm["laermbelastung__konfidenz"] = "geschaetzt_niedrig"
    laerm["laermbelastung__methode"] = "rate_bezirk"
    laerm["laermbelastung__quelldatensatz"] = "laermbelastung"
    laerm.to_parquet(disagg / "laermbelastung.parquet", index=False)

    # ÖPNV + POI Erreichbarkeit (in processed/ Unterordner)
    processed = tmp_path / "processed"
    processed.mkdir()

    oepnv = pd.DataFrame({
        "segment_id": seg_ids,
        "nearest_stop_dist_m": np.random.uniform(50, 1200, len(seg_ids)),
        "stops_within_500m": np.random.randint(0, 5, len(seg_ids)),
        "stops_within_1000m": np.random.randint(1, 10, len(seg_ids)),
    })
    oepnv.to_parquet(processed / "oepnv_erreichbarkeit.parquet", index=False)

    poi = pd.DataFrame({
        "segment_id": seg_ids,
        "dist_nearest_schule_m": np.random.uniform(100, 2000, len(seg_ids)),
        "dist_nearest_kita_m": np.random.uniform(50, 1500, len(seg_ids)),
        "dist_nearest_arzt_m": np.random.uniform(100, 2500, len(seg_ids)),
        "dist_nearest_spielplatz_m": np.random.uniform(50, 1000, len(seg_ids)),
        "dist_nearest_sport_m": np.random.uniform(100, 3000, len(seg_ids)),
    })
    poi.to_parquet(processed / "poi_erreichbarkeit.parquet", index=False)

    return disagg


# ── Dimensionen-Definition ────────────────────────────────────────────────────

class TestDimensionenDefinition:
    def test_alle_dimensionen_haben_indikatoren(self) -> None:
        for dim in DIMENSIONEN:
            assert len(dim.indikatoren) > 0, f"Dimension '{dim.key}' hat keine Indikatoren"

    def test_gewichte_in_dimension_positiv(self) -> None:
        for dim in DIMENSIONEN:
            for ind in dim.indikatoren:
                assert ind.gewicht > 0

    def test_richtung_valide(self) -> None:
        for dim in DIMENSIONEN:
            for ind in dim.indikatoren:
                assert ind.richtung in ("higher_worse", "higher_better")

    def test_methode_valide(self) -> None:
        for dim in DIMENSIONEN:
            for ind in dim.indikatoren:
                assert ind.methode in ("direct", "per_kinder", "per_laenge")

    def test_dimension_gewichte_unter_eins(self) -> None:
        # Nur verfügbare Dimensionen; fehlende (Bildung, Gesundheit) nicht dabei
        gesamt = sum(d.gewicht for d in DIMENSIONEN)
        assert gesamt <= 1.0 + 1e-9


# ── berechne_dimension_score ──────────────────────────────────────────────────

class TestBerechneDimensionScore:
    def test_grundlegende_berechnung(self) -> None:
        dim = DimensionDef(
            key="test", label="Test", gewicht=1.0,
            indikatoren=[
                IndikatorDef("ds1", "col1", "higher_worse", "direct", 0.5, "Ind 1"),
                IndikatorDef("ds2", "col2", "higher_worse", "direct", 0.5, "Ind 2"),
            ],
        )
        scores = {
            "ds1__col1": pd.Series([0.2, 0.4, 0.6], index=["a", "b", "c"]),
            "ds2__col2": pd.Series([0.4, 0.6, 0.8], index=["a", "b", "c"]),
        }
        result = berechne_dimension_score(scores, dim)
        assert abs(result["a"] - 0.3) < 1e-9  # (0.2 + 0.4) / 2
        assert abs(result["b"] - 0.5) < 1e-9

    def test_nan_indikator_wird_ignoriert(self) -> None:
        dim = DimensionDef(
            key="test", label="Test", gewicht=1.0,
            indikatoren=[
                IndikatorDef("ds1", "col1", "higher_worse", "direct", 0.5, "Ind 1"),
                IndikatorDef("ds2", "col2", "higher_worse", "direct", 0.5, "Ind 2"),
            ],
        )
        scores = {
            "ds1__col1": pd.Series([0.4, 0.6], index=["a", "b"]),
            "ds2__col2": pd.Series([np.nan, np.nan], index=["a", "b"]),
        }
        result = berechne_dimension_score(scores, dim)
        # Nur ds1 verfügbar → Ergebnis = ds1-Wert
        assert abs(result["a"] - 0.4) < 1e-9

    def test_leere_scores_gibt_leere_serie(self) -> None:
        dim = DimensionDef(
            key="test", label="Test", gewicht=1.0,
            indikatoren=[IndikatorDef("ds1", "col1", "higher_worse", "direct", 1.0, "X")],
        )
        result = berechne_dimension_score({}, dim)
        assert result.empty

    def test_gewichtung_asymmetrisch(self) -> None:
        dim = DimensionDef(
            key="test", label="Test", gewicht=1.0,
            indikatoren=[
                IndikatorDef("ds1", "col1", "higher_worse", "direct", 0.75, "Schwer"),
                IndikatorDef("ds2", "col2", "higher_worse", "direct", 0.25, "Leicht"),
            ],
        )
        scores = {
            "ds1__col1": pd.Series([1.0], index=["x"]),
            "ds2__col2": pd.Series([0.0], index=["x"]),
        }
        result = berechne_dimension_score(scores, dim)
        assert abs(result["x"] - 0.75) < 1e-9


# ── berechne_aufwachsindex (Integration) ─────────────────────────────────────

class TestBerechneAufwachsindex:
    def test_gibt_geodataframe_zurueck(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert isinstance(result, gpd.GeoDataFrame)

    def test_aufwachsindex_spalte_vorhanden(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert "aufwachsindex_gesamt" in result.columns

    def test_wertebereich_0_bis_100(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        idx = result["aufwachsindex_gesamt"].dropna()
        assert (idx >= 0).all() and (idx <= 100).all()

    def test_dimensionsspalten_vorhanden(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        for dim in DIMENSIONEN:
            assert f"dim_{dim.key}" in result.columns

    def test_alle_segmente_im_ergebnis(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert len(result) == len(segmente_gdf)

    def test_konfidenz_spalte_vorhanden(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert "konfidenz_gesamt" in result.columns
        assert (result["konfidenz_gesamt"].dropna().between(0, 1)).all()

    def test_crs_erhalten(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert result.crs.to_epsg() == 4326

    def test_segment_ids_unveraendert(
        self, segmente_gdf: gpd.GeoDataFrame, tmp_disagg_dir: Path
    ) -> None:
        result = berechne_aufwachsindex(tmp_disagg_dir, segmente_gdf)
        assert set(result["segment_id"]) == set(segmente_gdf["segment_id"])
