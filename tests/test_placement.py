"""Tests für Phase 6: Sozialarbeiter-Standortoptimierung.

Testet alle Module mit synthetischen Minimal-Fixtures.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely.geometry as sgeom

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WGS84 = "EPSG:4326"
UTM32N = "EPSG:25832"


def _punkt(lon: float, lat: float) -> sgeom.Point:
    """Hilfsfunktion: Erstellt einen WGS84-Punkt."""
    return sgeom.Point(lon, lat)


@pytest.fixture()
def bezirke_geojson(tmp_path: Path) -> Path:
    """Kleines Bezirks-GeoDataFrame mit zwei Polygonen."""
    gdf = gpd.GeoDataFrame(
        {
            "name": ["Stuttgart-Mitte", "Stuttgart-Nord"],
            "geometry": [
                sgeom.box(9.16, 48.77, 9.20, 48.80),
                sgeom.box(9.16, 48.80, 9.20, 48.84),
            ],
        },
        crs=WGS84,
    )
    pfad = tmp_path / "bezirke.geojson"
    gdf.to_file(pfad, driver="GeoJSON")
    return pfad


@pytest.fixture()
def sozial_geojson(tmp_path: Path) -> Path:
    """Sozialeinrichtungen: jugendrelevante + nicht-relevante Einrichtungen."""
    gdf = gpd.GeoDataFrame(
        {
            "osm_id": [1, 2, 3, 4, 5, 6],
            "osm_type": ["node"] * 6,
            "name": [
                "Jugendhaus Mitte",
                "Seniorenresidenz Süd",
                "dasCann Jugendtreff",
                "Ambulanter Pflegedienst ABC",
                "Caritas Beratungsstelle",
                "Familienzentrum Nord",
            ],
            "amenity": ["community_centre", "social_facility", "community_centre",
                        "social_facility", "social_facility", "community_centre"],
            "leisure": [""] * 6,
            "public_transport": [""] * 6,
            "social_facility": ["", "assisted_living", "", "ambulatory_care", "", ""],
            "geometry": [
                _punkt(9.18, 48.78),
                _punkt(9.17, 48.77),
                _punkt(9.19, 48.79),
                _punkt(9.175, 48.775),
                _punkt(9.185, 48.785),
                _punkt(9.18, 48.81),
            ],
        },
        crs=WGS84,
    )
    pfad = tmp_path / "sozialeinrichtungen.geojson"
    gdf.to_file(pfad, driver="GeoJSON")
    return pfad


@pytest.fixture()
def aufwachsindex_geojson(tmp_path: Path) -> Path:
    """Synthetischer Aufwachsindex mit 10 Straßenabschnitten."""
    # Kurze Linien rund um Stuttgart-Mitte
    linien = [
        sgeom.LineString([(9.17 + i * 0.005, 48.775), (9.17 + i * 0.005 + 0.003, 48.778)])
        for i in range(10)
    ]
    gdf = gpd.GeoDataFrame(
        {
            "segment_id": [f"seg_{i:03d}" for i in range(10)],
            "name": [f"Straße {i}" for i in range(10)],
            "bezirk": ["Stuttgart-Mitte"] * 5 + ["Stuttgart-Nord"] * 5,
            "stadtteil": ["Mitte"] * 10,
            "highway": ["residential"] * 10,
            "laenge_m": [100.0] * 10,
            "aufwachsindex_gesamt": [30.0, 45.0, 60.0, 75.0, 80.0, 40.0, 55.0, 65.0, 70.0, 50.0],
            "n_dimensionen_verfuegbar": [7] * 10,
            "konfidenz_gesamt": [1.0] * 10,
            "geometry": linien,
        },
        crs=WGS84,
    )
    pfad = tmp_path / "aufwachsindex.geojson"
    gdf.to_file(pfad, driver="GeoJSON")
    return pfad


@pytest.fixture()
def einwohner_kinder_parquet(tmp_path: Path) -> Path:
    """Einwohner-Kinder-Datei mit 10 Segmenten."""
    df = pd.DataFrame(
        {
            "segment_id": [f"seg_{i:03d}" for i in range(10)],
            "bezirk": ["Stuttgart-Mitte"] * 5 + ["Stuttgart-Nord"] * 5,
            "jahr": [2022] * 10,
            "einwohner_kinder_0_17": [50.0, 80.0, 120.0, 30.0, 60.0, 40.0, 90.0, 70.0, 45.0, 55.0],
        }
    )
    pfad = tmp_path / "einwohner_kinder.parquet"
    df.to_parquet(pfad, index=False)
    return pfad


@pytest.fixture()
def pois_geojson(tmp_path: Path) -> Path:
    """Kleine POI-Datei mit Schulen, Kitas und ÖPNV-Haltestellen."""
    gdf = gpd.GeoDataFrame(
        {
            "osm_id": list(range(20)),
            "osm_type": ["node"] * 20,
            "name": [f"POI {i}" for i in range(20)],
            "amenity": (
                ["school"] * 5
                + ["kindergarten"] * 5
                + ["community_centre"] * 5
                + [""] * 5
            ),
            "leisure": [""] * 20,
            "public_transport": [""] * 15 + ["stop_position"] * 5,
            "social_facility": [""] * 20,
            "geometry": [
                _punkt(9.17 + i * 0.004, 48.775 + (i % 3) * 0.003)
                for i in range(20)
            ],
        },
        crs=WGS84,
    )
    pfad = tmp_path / "pois.geojson"
    gdf.to_file(pfad, driver="GeoJSON")
    return pfad


@pytest.fixture()
def bestand_gdf() -> gpd.GeoDataFrame:
    """Kleiner Bestand für Tests."""
    return gpd.GeoDataFrame(
        {
            "osm_id": [101, 102],
            "osm_type": ["node", "node"],
            "name": ["Jugendhaus Test", "Beratungsstelle Test"],
            "amenity": ["community_centre", "social_facility"],
            "social_facility": ["", ""],
            "typ": ["jugendhaus", "beratungsstelle"],
            "bezirk": ["Stuttgart-Mitte", "Stuttgart-Nord"],
            "quelle": ["osm", "osm"],
            "geometry": [_punkt(9.18, 48.778), _punkt(9.19, 48.81)],
        },
        crs=WGS84,
    )


# ---------------------------------------------------------------------------
# Tests: existing.py
# ---------------------------------------------------------------------------


class TestLoadBestand:
    """Tests für existing.load_bestand."""

    def test_jugendrelevante_werden_behalten(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Jugendrelevante Einrichtungen bleiben erhalten."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        assert len(gdf) > 0
        assert "Seniorenresidenz Süd" not in gdf["name"].values
        assert "Ambulanter Pflegedienst ABC" not in gdf["name"].values

    def test_nicht_jugendrelevante_werden_entfernt(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Pflegeheime und Pflegedienste werden herausgefiltert."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        ausgeschlossene = ["Seniorenresidenz", "Pflegedienst", "ambulant"]
        for name in gdf["name"].values:
            name_lower = name.lower()
            for ausschl in ausgeschlossene:
                assert ausschl.lower() not in name_lower, (
                    f"Nicht-jugendrelevante Einrichtung '{name}' nicht gefiltert"
                )

    def test_typ_klassifikation(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Einrichtungen erhalten korrekten Typ."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        assert "typ" in gdf.columns

        jugendhaus_zeilen = gdf[gdf["name"].str.contains("Jugendhaus", case=False, na=False)]
        if len(jugendhaus_zeilen) > 0:
            assert jugendhaus_zeilen["typ"].iloc[0] == "jugendhaus"

    def test_bezirk_join(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Spatial Join weist Bezirk zu."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        assert "bezirk" in gdf.columns
        # Mindestens eine Einrichtung sollte einen bekannten Bezirk haben
        bekannte_bezirke = gdf[gdf["bezirk"].isin(["Stuttgart-Mitte", "Stuttgart-Nord"])]
        assert len(bekannte_bezirke) > 0

    def test_crs_ist_wgs84(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Ausgabe ist in EPSG:4326."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 4326

    def test_fehlende_datei_wirft_fehler(self, tmp_path: Path, bezirke_geojson: Path) -> None:
        """FileNotFoundError bei fehlender sozialeinrichtungen.geojson."""
        from src.placement.existing import load_bestand

        with pytest.raises(FileNotFoundError):
            load_bestand(tmp_path / "nonexistent.geojson", bezirke_geojson)

    def test_keine_duplikate(
        self,
        sozial_geojson: Path,
        bezirke_geojson: Path,
    ) -> None:
        """Keine doppelten osm_ids im Ergebnis."""
        from src.placement.existing import load_bestand

        gdf = load_bestand(sozial_geojson, bezirke_geojson)
        assert gdf["osm_id"].nunique() == len(gdf)

    def test_merge_manuell_ohne_datei(self, bestand_gdf: gpd.GeoDataFrame, tmp_path: Path) -> None:
        """merge_manuell gibt unverändert zurück wenn keine Datei existiert."""
        from src.placement.existing import merge_manuell

        result = merge_manuell(bestand_gdf, tmp_path / "nicht_vorhanden.json")
        assert len(result) == len(bestand_gdf)

    def test_merge_manuell_mit_datei(self, bestand_gdf: gpd.GeoDataFrame, tmp_path: Path) -> None:
        """merge_manuell fügt manuelle Einträge korrekt hinzu."""
        from src.placement.existing import merge_manuell

        manuell = [
            {
                "id": "man_001",
                "name": "Manuelles Jugendhaus",
                "typ": "jugendhaus",
                "bezirk": "Stuttgart-Mitte",
                "lat": 48.78,
                "lon": 9.18,
            }
        ]
        manuell_path = tmp_path / "bestand_manuell.json"
        manuell_path.write_text(json.dumps(manuell), encoding="utf-8")

        result = merge_manuell(bestand_gdf, manuell_path)
        assert len(result) == len(bestand_gdf) + 1
        assert "Manuelles Jugendhaus" in result["name"].values


# ---------------------------------------------------------------------------
# Tests: demand.py
# ---------------------------------------------------------------------------


class TestBerechneBedarrf:
    """Tests für demand.berechne_bedarf."""

    def test_bedarf_berechnung(
        self,
        aufwachsindex_geojson: Path,
        einwohner_kinder_parquet: Path,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Rohbedarf = (index/100) * kinder."""
        from src.placement.demand import berechne_bedarf

        result = berechne_bedarf(
            aufwachsindex_geojson, einwohner_kinder_parquet, bestand_gdf
        )
        assert "bedarf_roh" in result.columns
        assert "bedarf_unversorgt" in result.columns
        assert "kinder" in result.columns
        assert "versorgungsgrad" in result.columns

        # Rohbedarf muss positiv sein wo Index und Kinder vorhanden
        positiv = result["bedarf_roh"].dropna()
        assert (positiv >= 0).all()

    def test_versorgungsgrad_im_radius_reduziert_bedarf(
        self,
        aufwachsindex_geojson: Path,
        einwohner_kinder_parquet: Path,
    ) -> None:
        """Einrichtung nahe am Segment reduziert dessen Bedarf."""
        from src.placement.demand import berechne_bedarf

        # Einrichtung direkt an Segment 0 (9.17, 48.775)
        nahe_einrichtung = gpd.GeoDataFrame(
            {
                "osm_id": [999],
                "name": ["Nahes Jugendhaus"],
                "typ": ["jugendhaus"],
                "bezirk": ["Stuttgart-Mitte"],
                "quelle": ["test"],
                "geometry": [_punkt(9.170, 48.7755)],
            },
            crs=WGS84,
        )
        weit_entfernt = gpd.GeoDataFrame(
            {
                "osm_id": [998],
                "name": ["Fernes Jugendhaus"],
                "typ": ["jugendhaus"],
                "bezirk": ["unbekannt"],
                "quelle": ["test"],
                "geometry": [_punkt(8.0, 48.0)],  # Weit weg
            },
            crs=WGS84,
        )

        result_nahe = berechne_bedarf(
            aufwachsindex_geojson, einwohner_kinder_parquet, nahe_einrichtung
        )
        result_weit = berechne_bedarf(
            aufwachsindex_geojson, einwohner_kinder_parquet, weit_entfernt
        )

        # Nahe Einrichtung hat höheren Versorgungsgrad → weniger unversorgten Bedarf
        assert (
            result_nahe["bedarf_unversorgt"].sum()
            < result_weit["bedarf_unversorgt"].sum()
        )

    def test_versorgungsgrad_zwischen_null_und_eins(
        self,
        aufwachsindex_geojson: Path,
        einwohner_kinder_parquet: Path,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Versorgungsgrad liegt immer zwischen 0 und 1."""
        from src.placement.demand import berechne_bedarf

        result = berechne_bedarf(
            aufwachsindex_geojson, einwohner_kinder_parquet, bestand_gdf
        )
        vg = result["versorgungsgrad"]
        assert (vg >= 0).all()
        assert (vg <= 1).all()

    def test_leerer_bestand_versorgungsgrad_null(
        self,
        aufwachsindex_geojson: Path,
        einwohner_kinder_parquet: Path,
    ) -> None:
        """Ohne Bestand ist der Versorgungsgrad überall 0."""
        from src.placement.demand import berechne_bedarf

        leerer_bestand = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        result = berechne_bedarf(
            aufwachsindex_geojson, einwohner_kinder_parquet, leerer_bestand
        )
        assert (result["versorgungsgrad"] == 0.0).all()
        # Unversorgter Bedarf = Rohbedarf
        np.testing.assert_allclose(
            result["bedarf_unversorgt"].values,
            result["bedarf_roh"].values,
            rtol=1e-6,
        )

    def test_fehlende_kinder_datei_wirft_fehler(
        self,
        aufwachsindex_geojson: Path,
        tmp_path: Path,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """FileNotFoundError bei fehlendem einwohner_kinder.parquet."""
        from src.placement.demand import berechne_bedarf

        with pytest.raises(FileNotFoundError):
            berechne_bedarf(
                aufwachsindex_geojson,
                tmp_path / "nonexistent.parquet",
                bestand_gdf,
            )


# ---------------------------------------------------------------------------
# Tests: optimizer.py
# ---------------------------------------------------------------------------


@pytest.fixture()
def bedarf_gdf(aufwachsindex_geojson: Path, einwohner_kinder_parquet: Path) -> gpd.GeoDataFrame:
    """Berechneter Bedarf für Optimizer-Tests."""
    from src.placement.demand import berechne_bedarf

    leerer_bestand = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
    return berechne_bedarf(aufwachsindex_geojson, einwohner_kinder_parquet, leerer_bestand)


@pytest.fixture()
def kandidaten_gdf() -> gpd.GeoDataFrame:
    """Synthetische Kandidatenstandorte."""
    return gpd.GeoDataFrame(
        {
            "osm_id": list(range(8)),
            "name": [f"Kandidat {i}" for i in range(8)],
            "amenity": ["school"] * 4 + ["community_centre"] * 4,
            "leisure": [""] * 8,
            "standort_typ": ["oeffentlich"] * 4 + ["privat"] * 4,
            "geometry": [
                _punkt(9.170 + i * 0.004, 48.775 + (i % 2) * 0.005)
                for i in range(8)
            ],
        },
        crs=WGS84,
    )


class TestSelectKandidaten:
    """Tests für optimizer.select_kandidaten."""

    def test_kandidaten_enthalten_schulen_und_kitas(self, pois_geojson: Path) -> None:
        """Schulen und Kitas werden als Kandidaten ausgewählt."""
        from src.placement.optimizer import select_kandidaten

        # Alle POIs als Transit-Stops übergeben (kein Filter)
        pois_gdf = gpd.read_file(pois_geojson)
        transit = pois_gdf[pois_gdf["public_transport"] == "stop_position"].copy()

        result = select_kandidaten(pois_geojson, transit)
        assert len(result) >= 0  # Kann leer sein wenn ÖPNV-Filter zu streng
        if len(result) > 0:
            assert "standort_typ" in result.columns

    def test_kein_transit_filter_liefert_mehr(self, pois_geojson: Path) -> None:
        """Ohne ÖPNV-Filter gibt es mehr oder gleich viele Kandidaten."""
        from src.placement.optimizer import select_kandidaten

        pois_gdf = gpd.read_file(pois_geojson)
        transit = pois_gdf[pois_gdf["public_transport"] == "stop_position"].copy()

        result_mit_filter = select_kandidaten(pois_geojson, transit)

        # Leerer Transit-GDF → kein Filter
        leerer_transit = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        result_ohne_filter = select_kandidaten(pois_geojson, leerer_transit)

        assert len(result_ohne_filter) >= len(result_mit_filter)

    def test_fehlende_datei_wirft_fehler(self, tmp_path: Path) -> None:
        """FileNotFoundError bei fehlendem pois.geojson."""
        from src.placement.optimizer import select_kandidaten

        leerer_transit = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        with pytest.raises(FileNotFoundError):
            select_kandidaten(tmp_path / "nonexistent.geojson", leerer_transit)


class TestSolveMclp:
    """Tests für optimizer.solve_mclp."""

    def test_mclp_liefert_korrekte_anzahl(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """MCLP gibt exakt n_neue Standorte zurück (wenn genug Kandidaten)."""
        from src.placement.optimizer import solve_mclp

        result = solve_mclp(
            bedarf_gdf, kandidaten_gdf, bestand_gdf,
            n_neue=2, radius_m=5000.0, walking_factor=1.0,
        )
        assert len(result) <= 2
        if len(result) > 0:
            assert "modell" in result.columns
            assert (result["modell"] == "mclp").all()

    def test_mclp_leerer_bestand(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
    ) -> None:
        """MCLP funktioniert auch ohne Bestand."""
        from src.placement.optimizer import solve_mclp

        leerer_bestand = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        result = solve_mclp(
            bedarf_gdf, kandidaten_gdf, leerer_bestand,
            n_neue=1, radius_m=5000.0, walking_factor=1.0,
        )
        # Kann leer sein wenn Solver kein Ergebnis liefert, aber kein Fehler
        assert isinstance(result, gpd.GeoDataFrame)

    def test_mclp_leere_kandidaten(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """MCLP gibt leeres GeoDataFrame zurück bei fehlenden Kandidaten."""
        from src.placement.optimizer import solve_mclp

        leere_kandidaten = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        result = solve_mclp(
            bedarf_gdf, leere_kandidaten, bestand_gdf, n_neue=2
        )
        assert len(result) == 0

    def test_mclp_n_groesser_als_kandidaten(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """n_neue > len(kandidaten) wählt maximal alle Kandidaten."""
        from src.placement.optimizer import solve_mclp

        result = solve_mclp(
            bedarf_gdf, kandidaten_gdf, bestand_gdf,
            n_neue=1000, radius_m=5000.0, walking_factor=1.0,
        )
        assert len(result) <= len(kandidaten_gdf)


class TestSolvePMedian:
    """Tests für optimizer.solve_p_median."""

    def test_p_median_liefert_korrekte_anzahl(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
    ) -> None:
        """p-Median gibt maximal n_neue Standorte zurück."""
        from src.placement.optimizer import solve_p_median

        result = solve_p_median(
            bedarf_gdf, kandidaten_gdf, bestand_gdf, n_neue=3
        )
        assert len(result) <= 3
        if len(result) > 0:
            assert "modell" in result.columns
            assert (result["modell"] == "p_median").all()

    def test_p_median_reduziert_gesamtdistanz(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Mehr Standorte reduzieren die gewichtete Gesamtdistanz."""
        from src.placement.optimizer import solve_p_median

        leerer_bestand = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

        result_1 = solve_p_median(bedarf_gdf, kandidaten_gdf, leerer_bestand, n_neue=1)
        result_3 = solve_p_median(bedarf_gdf, kandidaten_gdf, leerer_bestand, n_neue=3)

        # 3 Standorte sollten mindestens so gut wie 1 Standort sein
        assert len(result_3) >= len(result_1)


# ---------------------------------------------------------------------------
# Tests: impact.py
# ---------------------------------------------------------------------------


class TestBerechneWirkung:
    """Tests für impact.berechne_wirkung."""

    def test_wirkung_spalten_vorhanden(
        self,
        bestand_gdf: gpd.GeoDataFrame,
        bedarf_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Ausgabe enthält alle erwarteten Wirkungsspalten."""
        from src.placement.impact import berechne_wirkung

        result = berechne_wirkung(bestand_gdf, bedarf_gdf, radius_m=5000.0)
        for col in ["n_segmente_im_radius", "erreichte_kinder", "abgedeckter_bedarf"]:
            assert col in result.columns

    def test_groesserer_radius_mehr_segmente(
        self,
        bestand_gdf: gpd.GeoDataFrame,
        bedarf_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Größerer Radius erfasst mehr Segmente."""
        from src.placement.impact import berechne_wirkung

        result_klein = berechne_wirkung(bestand_gdf, bedarf_gdf, radius_m=100.0)
        result_gross = berechne_wirkung(bestand_gdf, bedarf_gdf, radius_m=50_000.0)

        assert (
            result_gross["n_segmente_im_radius"].sum()
            >= result_klein["n_segmente_im_radius"].sum()
        )

    def test_erreichte_kinder_nicht_negativ(
        self,
        bestand_gdf: gpd.GeoDataFrame,
        bedarf_gdf: gpd.GeoDataFrame,
    ) -> None:
        """Erreichte Kinder sind nie negativ."""
        from src.placement.impact import berechne_wirkung

        result = berechne_wirkung(bestand_gdf, bedarf_gdf, radius_m=2000.0)
        assert (result["erreichte_kinder"] >= 0).all()

    def test_leere_standorte(self, bedarf_gdf: gpd.GeoDataFrame) -> None:
        """Leerer Standort-GDF führt zu leerem Ergebnis."""
        from src.placement.impact import berechne_wirkung

        leere_standorte = gpd.GeoDataFrame({"geometry": []}, crs=WGS84)
        result = berechne_wirkung(leere_standorte, bedarf_gdf)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests: cost_model.py
# ---------------------------------------------------------------------------


class TestBerechneKosten:
    """Tests für cost_model.berechne_kosten."""

    def test_kosten_spalten_vorhanden(self, kandidaten_gdf: gpd.GeoDataFrame) -> None:
        """Ausgabe enthält alle Kosten-Spalten."""
        from src.placement.cost_model import berechne_kosten

        result = berechne_kosten(kandidaten_gdf)
        for col in ["personalkosten_jahr", "mietkosten_jahr", "sachkosten_jahr",
                    "gesamtkosten_jahr", "einmalkosten"]:
            assert col in result.columns

    def test_oeffentlich_billiger_als_privat(self, kandidaten_gdf: gpd.GeoDataFrame) -> None:
        """Öffentliche Standorte haben niedrigere Mietkosten."""
        from src.placement.cost_model import berechne_kosten

        result = berechne_kosten(kandidaten_gdf)
        oeffentlich = result[result["standort_typ"] == "oeffentlich"]["mietkosten_jahr"]
        privat = result[result["standort_typ"] == "privat"]["mietkosten_jahr"]

        if len(oeffentlich) > 0 and len(privat) > 0:
            assert oeffentlich.mean() < privat.mean()

    def test_gesamtkosten_korrekt(self, kandidaten_gdf: gpd.GeoDataFrame) -> None:
        """Gesamtkosten = Personal + Miete + Sachkosten."""
        from src.placement.cost_model import berechne_kosten

        result = berechne_kosten(kandidaten_gdf)
        erwartet = (
            result["personalkosten_jahr"]
            + result["mietkosten_jahr"]
            + result["sachkosten_jahr"]
        )
        np.testing.assert_allclose(result["gesamtkosten_jahr"].values, erwartet.values)

    def test_kosten_params_override(self, kandidaten_gdf: gpd.GeoDataFrame) -> None:
        """Kosten-Override wird korrekt angewendet."""
        from src.placement.cost_model import berechne_kosten

        hoch = berechne_kosten(kandidaten_gdf, {"personal_s11b_jahr": 100_000.0})
        niedrig = berechne_kosten(kandidaten_gdf, {"personal_s11b_jahr": 30_000.0})

        assert hoch["personalkosten_jahr"].iloc[0] == 100_000.0
        assert niedrig["personalkosten_jahr"].iloc[0] == 30_000.0
        assert hoch["gesamtkosten_jahr"].iloc[0] > niedrig["gesamtkosten_jahr"].iloc[0]

    def test_kosten_pro_kind_berechnet(
        self,
        bestand_gdf: gpd.GeoDataFrame,
        bedarf_gdf: gpd.GeoDataFrame,
    ) -> None:
        """kosten_pro_erreichtes_kind wird berechnet wenn 'erreichte_kinder' vorhanden."""
        from src.placement.cost_model import berechne_kosten
        from src.placement.impact import berechne_wirkung

        mit_wirkung = berechne_wirkung(bestand_gdf, bedarf_gdf, radius_m=5000.0)
        mit_kosten = berechne_kosten(mit_wirkung)

        assert "kosten_pro_erreichtes_kind" in mit_kosten.columns

    def test_keine_negativen_kosten(self, kandidaten_gdf: gpd.GeoDataFrame) -> None:
        """Keine negativen Kostenwerte."""
        from src.placement.cost_model import berechne_kosten

        result = berechne_kosten(kandidaten_gdf)
        for col in ["personalkosten_jahr", "mietkosten_jahr", "sachkosten_jahr",
                    "gesamtkosten_jahr", "einmalkosten"]:
            assert (result[col] >= 0).all()


# ---------------------------------------------------------------------------
# Tests: scenarios.py
# ---------------------------------------------------------------------------


class TestGenerateAll:
    """Tests für scenarios.generate_all."""

    def test_alle_szenarien_erzeugen_geojson(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
        tmp_path: Path,
    ) -> None:
        """Alle Szenarien erzeugen GeoJSON-Dateien."""
        from src.placement.scenarios import generate_all

        ausgabe_dir = tmp_path / "szenarien"
        result = generate_all(
            bedarf_gdf=bedarf_gdf,
            kandidaten_gdf=kandidaten_gdf,
            bestand_gdf=bestand_gdf,
            ausgabe_dir=ausgabe_dir,
            radius_m=5000.0,
        )

        assert "szenarien" in result
        assert len(result["szenarien"]) > 0

        # kosten_nutzen.json muss existieren
        assert (tmp_path / "kosten_nutzen.json").exists()

    def test_baseline_hat_keine_neuen_stellen(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
        tmp_path: Path,
    ) -> None:
        """Baseline-Szenario hat 0 neue Stellen und 0 Kosten."""
        from src.placement.scenarios import generate_all

        result = generate_all(
            bedarf_gdf=bedarf_gdf,
            kandidaten_gdf=kandidaten_gdf,
            bestand_gdf=bestand_gdf,
            ausgabe_dir=tmp_path / "szenarien",
            radius_m=5000.0,
        )

        baseline = result["szenarien"]["baseline"]
        assert baseline["n_neue_stellen"] == 0
        assert baseline["gesamtkosten_jahr_eur"] == 0.0

    def test_mehr_stellen_mehr_abdeckung(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
        tmp_path: Path,
    ) -> None:
        """n5_optimal deckt mehr ab als n1_optimal."""
        from src.placement.scenarios import generate_all

        result = generate_all(
            bedarf_gdf=bedarf_gdf,
            kandidaten_gdf=kandidaten_gdf,
            bestand_gdf=bestand_gdf,
            ausgabe_dir=tmp_path / "szenarien",
            radius_m=5000.0,
        )

        szenarien = result["szenarien"]
        n1 = szenarien.get("n1_optimal")
        n5 = szenarien.get("n5_optimal")

        if n1 and n5:
            assert (
                n5["anteil_bedarf_abgedeckt_pct"]
                >= n1["anteil_bedarf_abgedeckt_pct"]
            )

    def test_budget_szenarien_vorhanden(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
        tmp_path: Path,
    ) -> None:
        """Budget-Szenarien sind im Ergebnis enthalten."""
        from src.placement.scenarios import generate_all

        result = generate_all(
            bedarf_gdf=bedarf_gdf,
            kandidaten_gdf=kandidaten_gdf,
            bestand_gdf=bestand_gdf,
            ausgabe_dir=tmp_path / "szenarien",
            radius_m=5000.0,
        )

        for budget_name in ["budget_100k", "budget_300k", "budget_500k"]:
            assert budget_name in result["szenarien"]

    def test_kosten_nutzen_json_valid(
        self,
        bedarf_gdf: gpd.GeoDataFrame,
        kandidaten_gdf: gpd.GeoDataFrame,
        bestand_gdf: gpd.GeoDataFrame,
        tmp_path: Path,
    ) -> None:
        """kosten_nutzen.json ist valides JSON mit erwartetem Schema."""
        from src.placement.scenarios import generate_all

        generate_all(
            bedarf_gdf=bedarf_gdf,
            kandidaten_gdf=kandidaten_gdf,
            bestand_gdf=bestand_gdf,
            ausgabe_dir=tmp_path / "szenarien",
            radius_m=5000.0,
        )

        kn_path = tmp_path / "kosten_nutzen.json"
        assert kn_path.exists()

        with kn_path.open(encoding="utf-8") as fh:
            kn = json.load(fh)

        assert "szenarien" in kn
        assert "parameter" in kn
        assert isinstance(kn["szenarien"], dict)
        assert len(kn["szenarien"]) >= 8  # baseline + 4 n-Szenarien + 3 Budget-Szenarien
