"""Tests für Phase 3: Dasymetrische Disaggregation."""

import pytest
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
from shapely.geometry import LineString

from src.disagg.confidence import (
    DisaggValue,
    konfidenz_fuer_methode,
    UNSICHERHEIT_STUFEN,
)
from src.disagg.dasymetric import (
    normalize_bezirk_name,
    compute_segment_weights,
    disaggregate_bezirk_to_segments,
    disaggregate_timeseries,
)
from src.disagg.validation import validate_sum_constraint, validate_no_negatives


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def segmente_gdf() -> gpd.GeoDataFrame:
    """Minimale Straßenabschnitte in 2 Bezirken."""
    return gpd.GeoDataFrame(
        {
            "segment_id": ["mitte_001", "mitte_002", "nord_001", "nord_002", "nord_003"],
            "bezirk": ["Stuttgart-Mitte", "Stuttgart-Mitte", "Stuttgart-Nord", "Stuttgart-Nord", "Stuttgart-Nord"],
            "laenge_m": [100.0, 200.0, 150.0, 150.0, 300.0],
            "highway": ["primary", "secondary", "primary", "residential", "residential"],
            "geometry": [LineString([(0, 0), (1, 0)])] * 5,
        },
        crs="EPSG:4326",
    )


@pytest.fixture()
def weights(segmente_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    return compute_segment_weights(segmente_gdf)


@pytest.fixture()
def bezirk_df() -> pd.DataFrame:
    """Einfache Bezirks-Zeitreihendaten."""
    return pd.DataFrame({
        "Stadtbezirk": ["Mitte", "Mitte", "Nord", "Nord"],
        "Jahr": [2020, 2021, 2020, 2021],
        "sgbii_kinder": [300.0, 320.0, 450.0, 430.0],
    })


# ── DisaggValue & Konfidenz ───────────────────────────────────────────────────

class TestDisaggValue:
    def test_valid_creation(self) -> None:
        v = DisaggValue(
            wert=42.0,
            konfidenz="geschaetzt_mittel",
            quelldatensatz="test",
            quellwert_bezirk=300.0,
            methode="laenge_gewichtet",
            unsicherheit_relativ=0.35,
        )
        assert v.wert == 42.0

    def test_unsicherheit_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            DisaggValue(
                wert=1.0,
                konfidenz="gemessen",
                quelldatensatz="x",
                quellwert_bezirk=1.0,
                methode="direkt",
                unsicherheit_relativ=1.5,  # > 1
            )

    def test_konfidenz_stufen_vollstaendig(self) -> None:
        for stufe in ("gemessen", "geschaetzt_hoch", "geschaetzt_mittel", "geschaetzt_niedrig"):
            assert stufe in UNSICHERHEIT_STUFEN


class TestKonfidenzFuerMethode:
    def test_gemessen_fuer_strassenabschnitt(self) -> None:
        assert konfidenz_fuer_methode("direkt", "strassenabschnitt") == "gemessen"

    def test_hoch_fuer_rate(self) -> None:
        assert konfidenz_fuer_methode("rate_bezirk", "stadtbezirk") == "geschaetzt_hoch"

    def test_mittel_fuer_laenge_stadtbezirk(self) -> None:
        assert konfidenz_fuer_methode("laenge_gewichtet", "stadtbezirk") == "geschaetzt_mittel"

    def test_niedrig_fuer_gesamtstadt(self) -> None:
        assert konfidenz_fuer_methode("laenge_gewichtet", "gesamtstadt") == "geschaetzt_niedrig"


# ── normalize_bezirk_name ─────────────────────────────────────────────────────

class TestNormalizeBezirkName:
    def test_mitte(self) -> None:
        assert normalize_bezirk_name("Mitte") == "Stuttgart-Mitte"

    def test_nord(self) -> None:
        assert normalize_bezirk_name("Nord") == "Stuttgart-Nord"

    def test_bad_cannstatt(self) -> None:
        assert normalize_bezirk_name("Bad Cannstatt") == "Bad Cannstatt"

    def test_moehringen_umlaut(self) -> None:
        assert normalize_bezirk_name("Möhringen") == "Möhringen"

    def test_unbekannt_bleibt_erhalten(self) -> None:
        assert normalize_bezirk_name("XYZ Unbekannt") == "XYZ Unbekannt"


# ── compute_segment_weights ───────────────────────────────────────────────────

class TestComputeSegmentWeights:
    def test_gewichte_summieren_zu_eins(self, weights: pd.DataFrame) -> None:
        summen = weights.groupby("bezirk")["gewicht"].sum()
        assert (summen - 1.0).abs().max() < 1e-9

    def test_alle_segmente_enthalten(self, weights: pd.DataFrame, segmente_gdf: gpd.GeoDataFrame) -> None:
        # Nur Segmente mit bekanntem Bezirk
        bekannte = segmente_gdf[segmente_gdf["bezirk"] != "unbekannt"]
        assert len(weights) == len(bekannte)

    def test_gewichte_positiv(self, weights: pd.DataFrame) -> None:
        assert (weights["gewicht"] > 0).all()

    def test_unbekannte_bezirke_ausgeschlossen(self) -> None:
        gdf = gpd.GeoDataFrame(
            {"segment_id": ["x", "y"], "bezirk": ["unbekannt", "Stuttgart-Mitte"],
             "laenge_m": [100.0, 200.0],
             "geometry": [LineString([(0,0),(1,0)])] * 2},
            crs="EPSG:4326",
        )
        w = compute_segment_weights(gdf)
        assert "unbekannt" not in w["bezirk"].values
        assert len(w) == 1

    def test_gewicht_proportional_zu_laenge(self, weights: pd.DataFrame) -> None:
        mitte = weights[weights["bezirk"] == "Stuttgart-Mitte"].set_index("segment_id")
        # mitte_002 (200m) soll doppelt so schwer sein wie mitte_001 (100m)
        assert abs(mitte.loc["mitte_002", "gewicht"] / mitte.loc["mitte_001", "gewicht"] - 2.0) < 1e-9


# ── disaggregate_bezirk_to_segments ──────────────────────────────────────────

class TestDisaggregateBezirkToSegments:
    def test_count_modus_summe_erhalten(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({
            "Bezirk": ["Mitte", "Nord"],
            "wert": [300.0, 600.0],
        })
        result = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="count",
        )
        # Summe pro Bezirk muss Originalwert treffen (bis Rundung)
        assert abs(result[result["bezirk"] == "Stuttgart-Mitte"]["wert"].sum() - 300.0) < 0.01
        assert abs(result[result["bezirk"] == "Stuttgart-Nord"]["wert"].sum() - 600.0) < 0.01

    def test_rate_modus_gleiche_werte_im_bezirk(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({
            "Bezirk": ["Mitte", "Nord"],
            "quote": [12.5, 18.3],
        })
        result = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["quote"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="rate",
        )
        mitte_werte = result[result["bezirk"] == "Stuttgart-Mitte"]["quote"].unique()
        assert len(mitte_werte) == 1
        assert abs(mitte_werte[0] - 12.5) < 1e-9

    def test_konfidenz_spalten_vorhanden(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({"Bezirk": ["Mitte"], "wert": [100.0]})
        result = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test_ds", modus="count",
        )
        assert "wert__konfidenz" in result.columns
        assert "wert__methode" in result.columns
        assert "wert__quelldatensatz" in result.columns
        assert (result["wert__quelldatensatz"] == "test_ds").all()

    def test_unbekannter_bezirk_gibt_nan(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({"Bezirk": ["Mitte"], "wert": [100.0]})
        result = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="count",
        )
        # Nord-Segmente haben keinen Bezirks-Match → NaN
        assert result[result["bezirk"] == "Stuttgart-Nord"]["wert"].isna().all()

    def test_alle_segmente_im_ergebnis(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({"Bezirk": ["Mitte", "Nord"], "wert": [100.0, 200.0]})
        result = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="count",
        )
        assert len(result) == len(weights)


# ── disaggregate_timeseries ───────────────────────────────────────────────────

class TestDisaggregateTimeseries:
    def test_alle_jahre_vorhanden(
        self, bezirk_df: pd.DataFrame, weights: pd.DataFrame
    ) -> None:
        result = disaggregate_timeseries(
            bezirk_df=bezirk_df, weights=weights,
            wert_spalten=["sgbii_kinder"], bezirk_spalte="Stadtbezirk",
            jahr_spalte="Jahr", dataset_id="test",
        )
        assert set(result["jahr"].unique()) == {2020, 2021}

    def test_summen_pro_jahr_erhalten(
        self, bezirk_df: pd.DataFrame, weights: pd.DataFrame
    ) -> None:
        result = disaggregate_timeseries(
            bezirk_df=bezirk_df, weights=weights,
            wert_spalten=["sgbii_kinder"], bezirk_spalte="Stadtbezirk",
            jahr_spalte="Jahr", dataset_id="test",
        )
        for jahr in [2020, 2021]:
            for bezirk, erwarteter_wert in [("Stuttgart-Mitte", bezirk_df[bezirk_df["Jahr"] == jahr].query("Stadtbezirk == 'Mitte'")["sgbii_kinder"].iloc[0])]:
                ist = result[(result["jahr"] == jahr) & (result["bezirk"] == bezirk)]["sgbii_kinder"].sum()
                assert abs(ist - erwarteter_wert) < 0.01

    def test_leerer_df_gibt_leeres_ergebnis(self, weights: pd.DataFrame) -> None:
        df = pd.DataFrame(columns=["Stadtbezirk", "Jahr", "wert"])
        result = disaggregate_timeseries(
            bezirk_df=df, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Stadtbezirk",
            jahr_spalte="Jahr", dataset_id="test",
        )
        assert result.empty


# ── Validierung ───────────────────────────────────────────────────────────────

class TestValidation:
    def test_sum_constraint_ok(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({"Bezirk": ["Mitte", "Nord"], "wert": [300.0, 600.0]})
        disagg = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="count",
        )
        ok = validate_sum_constraint(disagg, bezirk, ["wert"], "Bezirk", "test")
        assert ok is True

    def test_no_negatives_ok(self, weights: pd.DataFrame) -> None:
        bezirk = pd.DataFrame({"Bezirk": ["Mitte", "Nord"], "wert": [300.0, 600.0]})
        disagg = disaggregate_bezirk_to_segments(
            bezirk_df=bezirk, weights=weights,
            wert_spalten=["wert"], bezirk_spalte="Bezirk",
            dataset_id="test", modus="count",
        )
        ok = validate_no_negatives(disagg, ["wert"], "test")
        assert ok is True

    def test_negative_werte_erkannt(self) -> None:
        df = pd.DataFrame({"bezirk": ["Mitte"], "wert": [-5.0]})
        ok = validate_no_negatives(df, ["wert"], "test")
        assert ok is False
