"""Gemeinsame Test-Fixtures."""

import textwrap
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def tmp_raw_dir(tmp_path: Path) -> Path:
    """Temporäres Rohdaten-Verzeichnis mit Beispiel-CSVs."""
    raw = tmp_path / "raw"
    raw.mkdir()

    # Stadtbezirks-CSV im Long-Format
    (raw / "sozialgeld_stadtbezirke.csv").write_text(
        textwrap.dedent("""\
            Stadtbezirk;Jahr;Anzahl;je_1000_EW
            Stuttgart-Mitte;2018;1200;45.3
            Stuttgart-Nord;2018;980;38.1
            Bad Cannstatt;2018;2100;52.7
            Stuttgart-Mitte;2019;1150;43.8
            Stuttgart-Nord;2019;950;37.0
            Bad Cannstatt;2019;2050;51.2
        """),
        encoding="utf-8",
    )

    # Gesamtstadt-CSV im Wide-Format
    (raw / "einwohnerbilanz_gesamt.csv").write_text(
        textwrap.dedent("""\
            Merkmal;2018;2019;2020;2021
            Einwohner gesamt;634830;635911;626275;628679
            Geburten;6120;6210;5980;6001
            Sterbefälle;5430;5502;5890;5800
        """),
        encoding="utf-8",
    )

    # CSV mit schlechtem Encoding (Umlaute)
    (raw / "kriminalitaet_delikte.csv").write_bytes(
        "Stadtbezirk;Jahr;Straftaten\nStuttgart-Süd;2020;450\nMöhringen;2020;310\n".encode("latin-1")
    )

    # Wahl-CSV (nicht index-relevant)
    (raw / "bundestagswahl_ergebnisse.csv").write_text(
        textwrap.dedent("""\
            Wahlkreis;Jahr;CDU;SPD;Grüne
            Stuttgart I;2021;28.1;21.3;24.5
            Stuttgart II;2021;27.4;22.0;25.1
        """),
        encoding="utf-8",
    )

    return raw
