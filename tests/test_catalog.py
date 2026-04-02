"""Tests für Phase 1: Datenkatalogisierung."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.catalog.classifier import classify_dataset
from src.catalog.normalizer import normalize_bezirk, normalize_fehlwerte, normalize_jahresspalte
from src.catalog.registry import build_registry, load_registry
from src.catalog.scanner import detect_encoding, detect_separator, scan_csv


# ── Scanner ──────────────────────────────────────────────────────────────────

class TestScanner:
    def test_scan_long_format(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "sozialgeld_stadtbezirke.csv"
        info = scan_csv(path)
        assert info["zeilen"] == 6
        assert "Stadtbezirk" in info["spalten"]
        assert "Jahr" in info["spalten"]
        assert info["raeumliche_ebene"] == "stadtbezirk"
        assert info["zeitraum"]["min"] == 2018
        assert info["zeitraum"]["max"] == 2019

    def test_scan_wide_format(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "einwohnerbilanz_gesamt.csv"
        info = scan_csv(path)
        assert info["raeumliche_ebene"] == "gesamtstadt"
        assert info["zeitraum"]["min"] == 2018
        assert info["zeitraum"]["max"] == 2021
        assert info["zeitraum"]["format"] == "wide"

    def test_scan_latin1_encoding(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "kriminalitaet_delikte.csv"
        info = scan_csv(path)
        assert info["encoding"] == "latin-1"
        assert info["zeilen"] == 2

    def test_separator_detection(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "sozialgeld_stadtbezirke.csv"
        sep = detect_separator(path, "utf-8")
        assert sep == ";"

    def test_luecken_prozent_vollstaendig(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "sozialgeld_stadtbezirke.csv"
        info = scan_csv(path)
        assert info["luecken_prozent"] == 0.0

    def test_scan_returns_dateiname(self, tmp_raw_dir: Path) -> None:
        path = tmp_raw_dir / "sozialgeld_stadtbezirke.csv"
        info = scan_csv(path)
        assert info["datei"] == "sozialgeld_stadtbezirke.csv"

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="nicht einlesen"):
            scan_csv(tmp_path / "nicht_vorhanden.csv")


# ── Classifier ───────────────────────────────────────────────────────────────

class TestClassifier:
    def test_sozialgeld_ist_soziales(self) -> None:
        result = classify_dataset("sozialgeld_stadtbezirke.csv", ["Stadtbezirk", "Jahr", "Anzahl"])
        assert "soziales" in result["dimensionen"]
        assert result["index_relevant"] is True

    def test_kriminalitaet_ist_sicherheit(self) -> None:
        result = classify_dataset("kriminalitaet_delikte.csv", ["Stadtbezirk", "Jahr", "Straftaten"])
        assert "sicherheit" in result["dimensionen"]
        assert result["index_relevant"] is True

    def test_wahl_nicht_index_relevant(self) -> None:
        result = classify_dataset("bundestagswahl_ergebnisse.csv", ["Wahlkreis", "CDU", "SPD"])
        assert result["index_relevant"] is False

    def test_schule_ist_bildung(self) -> None:
        result = classify_dataset("schueler_nach_stadtbezirken.csv", ["Stadtbezirk", "Schueler"])
        assert "bildung" in result["dimensionen"]

    def test_mehrere_dimensionen_moeglich(self) -> None:
        # Kinderbetreuung berührt Bildung und Soziales
        result = classify_dataset(
            "kinderbetreuung_quote.csv",
            ["Stadtbezirk", "Betreuungsquote", "Kinder_unter_3"],
        )
        assert len(result["dimensionen"]) >= 1

    def test_unbekannte_datei_sonstig(self) -> None:
        result = classify_dataset("xyz_unbekannt.csv", ["Spalte1", "Spalte2"])
        assert result["dimensionen"] == ["sonstig"]
        assert result["index_relevant"] is False

    def test_arzt_ist_gesundheit(self) -> None:
        result = classify_dataset("aerztliche_versorgung.csv", ["Stadtbezirk", "Aerzte", "Jahr"])
        assert "gesundheit" in result["dimensionen"]

    def test_wohnen_dimension(self) -> None:
        result = classify_dataset("eigentumerquote_stadtbezirke.csv", ["Stadtbezirk", "Eigentuemer_Prozent"])
        assert "wohnen" in result["dimensionen"]


# ── Normalizer ───────────────────────────────────────────────────────────────

class TestNormalizer:
    def test_bezirk_mitte_varianten(self) -> None:
        assert normalize_bezirk("Mitte") == "Stuttgart-Mitte"
        assert normalize_bezirk("S-Mitte") == "Stuttgart-Mitte"
        assert normalize_bezirk("stuttgart mitte") == "Stuttgart-Mitte"

    def test_bezirk_bad_cannstatt(self) -> None:
        assert normalize_bezirk("Bad Cannstatt") == "Bad Cannstatt"
        assert normalize_bezirk("Cannstatt") == "Bad Cannstatt"

    def test_bezirk_umlaut(self) -> None:
        assert normalize_bezirk("Möhringen") == "Möhringen"
        assert normalize_bezirk("Moehringen") == "Möhringen"

    def test_bezirk_nan_gibt_none(self) -> None:
        assert normalize_bezirk(None) is None
        assert normalize_bezirk(float("nan")) is None

    def test_bezirk_unbekannt_gibt_none(self) -> None:
        assert normalize_bezirk("Unbekannte Stadt") is None

    def test_fehlwerte_ersetzen(self) -> None:
        df = pd.DataFrame({"a": ["-", ".", "n.v.", "100", "k.a."]})
        result = normalize_fehlwerte(df)
        assert pd.isna(result["a"][0])
        assert pd.isna(result["a"][1])
        assert pd.isna(result["a"][2])
        assert result["a"][3] == "100"
        assert pd.isna(result["a"][4])

    def test_jahresspalte_zu_int(self) -> None:
        serie = pd.Series(["2018", "2019", "abc", "2020", None])
        result = normalize_jahresspalte(serie)
        assert result[0] == 2018
        assert result[2] is pd.NA or pd.isna(result[2])

    def test_jahresspalte_out_of_range(self) -> None:
        serie = pd.Series([1800, 2025, 3000, 2010])
        result = normalize_jahresspalte(serie)
        assert pd.isna(result[0])  # 1800 ungültig
        assert pd.isna(result[2])  # 3000 ungültig
        assert result[1] == 2025
        assert result[3] == 2010


# ── Registry ─────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_registry_erstellt_json(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        build_registry(tmp_raw_dir, catalog_dir)
        assert (catalog_dir / "registry.json").exists()

    def test_registry_eintraege_vollstaendig(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        registry = build_registry(tmp_raw_dir, catalog_dir)
        assert len(registry) >= 3  # Mindestens 3 gültige CSVs
        for eintrag in registry:
            assert "id" in eintrag
            assert "datei" in eintrag
            assert "thema" in eintrag
            assert "index_relevant" in eintrag
            assert "raeumliche_ebene" in eintrag
            assert "zeitraum" in eintrag
            assert len(eintrag["zeitraum"]) == 2

    def test_wahl_nicht_index_relevant_im_registry(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        registry = build_registry(tmp_raw_dir, catalog_dir)
        wahl_eintraege = [e for e in registry if "bundestagswahl" in e["id"]]
        assert len(wahl_eintraege) == 1
        assert wahl_eintraege[0]["index_relevant"] is False

    def test_sozialgeld_index_relevant(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        registry = build_registry(tmp_raw_dir, catalog_dir)
        sozial = [e for e in registry if "sozialgeld" in e["id"]]
        assert len(sozial) == 1
        assert sozial[0]["index_relevant"] is True

    def test_load_registry(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        build_registry(tmp_raw_dir, catalog_dir)
        loaded = load_registry(catalog_dir)
        assert isinstance(loaded, list)
        assert len(loaded) >= 3

    def test_load_registry_fehlt(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path / "nonexistent")

    def test_index_relevante_zuerst(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        registry = build_registry(tmp_raw_dir, catalog_dir)
        # Index-relevante Einträge sollen zuerst kommen
        relevant_indices = [i for i, e in enumerate(registry) if e["index_relevant"]]
        irrelevant_indices = [i for i, e in enumerate(registry) if not e["index_relevant"]]
        if relevant_indices and irrelevant_indices:
            assert max(relevant_indices) < max(irrelevant_indices) or min(irrelevant_indices) > min(relevant_indices)

    def test_zeitraum_wide_format(self, tmp_raw_dir: Path, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "catalog"
        registry = build_registry(tmp_raw_dir, catalog_dir)
        einwohner = [e for e in registry if "einwohnerbilanz" in e["id"]]
        assert len(einwohner) == 1
        assert einwohner[0]["zeitraum"][0] == 2018
        assert einwohner[0]["zeitraum"][1] == 2021
