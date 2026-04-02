"""Dataset-spezifische Lade- und Vorverarbeitungsfunktionen.

Jeder Loader gibt ein standardisiertes Dict zurück:
    {
        'df': pd.DataFrame,          # Bereinigte Bezirks-Daten
        'wert_spalten': list[str],   # Spalten zum Disaggregieren
        'bezirk_spalte': str,        # Name der Bezirksspalte
        'jahr_spalte': str | None,   # Name der Jahresspalte (oder None)
        'modus': 'count' | 'rate',   # Disaggregations-Modus
        'indikator': str,            # Kurzer Indikatorname für Output-Dateinamen
        'dimension': str,            # Index-Dimension
    }
"""

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _read_csv(path: Path) -> pd.DataFrame:
    """Liest eine CSV mit automatischer Encoding-Erkennung."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, sep=";", encoding=enc, low_memory=False)
            # Leere Spalten entfernen
            df = df.dropna(axis=1, how="all")
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Kann {path.name} nicht lesen")


def _to_numeric_col(series: pd.Series) -> pd.Series:
    """Konvertiert eine Spalte zu numerischen Werten (Komma als Dezimaltrennzeichen)."""
    if series.dtype == object or str(series.dtype) == "str":
        series = series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(series, errors="coerce")


# ── SGB-II / Sozialgeldempfänger ─────────────────────────────────────────────

def load_sgbii(raw_dir: Path) -> dict[str, Any]:
    """Sozialgeldempfänger SGB II nach Stadtbezirken seit 2005."""
    path = raw_dir / "sozialgeldempfaenger_sgb_ii_nach_stadtbezirken_seit_2005.csv"
    df = _read_csv(path)

    # Relevante Spalten: Gesamtzahl Kinder unter 18
    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"

    # Hauptindikator: Kinder insgesamt (0 bis unter 18)
    wert_col = "insgesamt 0 bis unter 18 Jahre"
    if wert_col not in df.columns:
        # Fallback: erste numerische Spalte nach Bezirk/Jahr
        num_cols = [c for c in df.columns if c not in [bezirk_col, jahr_col, "Nummer des Stadtbezirks"]
                    and pd.to_numeric(df[c], errors="coerce").notna().sum() > 5]
        wert_col = num_cols[0] if num_cols else None

    if wert_col is None:
        raise ValueError("Keine Wert-Spalte in SGB-II-Datensatz gefunden")

    df[wert_col] = _to_numeric_col(df[wert_col])
    df = df[[bezirk_col, jahr_col, wert_col]].dropna(subset=[bezirk_col])
    df = df.rename(columns={wert_col: "sgbii_kinder_unter18"})

    return {
        "df": df,
        "wert_spalten": ["sgbii_kinder_unter18"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "sgbii_kinder",
        "dimension": "oekonomie",
    }


# ── Beschäftigte am Wohnort ───────────────────────────────────────────────────

def load_beschaeftigung(raw_dir: Path) -> dict[str, Any]:
    """Sozialversicherungspflichtig Beschäftigte am Wohnort nach Stadtbezirken."""
    path = raw_dir / "sozialversicherungspflichtig_beschaeftigte_am_wohnort_nach_stadtbezirken_seit_2001.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"
    wert_col = "Sozialversicherungspflichtig Beschäftigte insgesamt"

    df[wert_col] = _to_numeric_col(df[wert_col])
    df = df[[bezirk_col, jahr_col, wert_col]].dropna(subset=[bezirk_col])
    df = df.rename(columns={wert_col: "sv_beschaeftigte"})

    return {
        "df": df,
        "wert_spalten": ["sv_beschaeftigte"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "sv_beschaeftigung",
        "dimension": "oekonomie",
    }


# ── Eigentümerquote ───────────────────────────────────────────────────────────

def load_eigentuemer(raw_dir: Path) -> dict[str, Any]:
    """Eigentümerquote nach Stadtbezirken."""
    path = raw_dir / "tidy_eigentumerquote_stadtbezirke_seit_2016.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"
    wert_col = "Eigentümerquote_in_Prozent"

    df[wert_col] = _to_numeric_col(df[wert_col])
    df = df[[bezirk_col, jahr_col, wert_col]].dropna(subset=[bezirk_col])
    df = df.rename(columns={wert_col: "eigentuemer_quote_pct"})

    return {
        "df": df,
        "wert_spalten": ["eigentuemer_quote_pct"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "rate",
        "indikator": "eigentuemer_quote",
        "dimension": "wohnen",
    }


# ── Einkommen ─────────────────────────────────────────────────────────────────

def load_einkommen(raw_dir: Path) -> dict[str, Any]:
    """Steuerpflichtiges Einkommen nach Stadtbezirken."""
    path = raw_dir / "steuerpflichtiges-einkommen.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"
    wert_col = "Einkommens-Index (Stuttgart = 100)"

    df[wert_col] = _to_numeric_col(df[wert_col])
    df = df[[bezirk_col, jahr_col, wert_col]].dropna(subset=[bezirk_col])
    df = df.rename(columns={wert_col: "einkommen_index"})

    return {
        "df": df,
        "wert_spalten": ["einkommen_index"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "rate",
        "indikator": "einkommen_index",
        "dimension": "oekonomie",
    }


# ── Straßen- und Gewaltkriminalität ──────────────────────────────────────────

def load_kriminalitaet(raw_dir: Path) -> dict[str, Any]:
    """Straßen- und Gewaltkriminalität nach Stadtbezirken."""
    path = raw_dir / "komunis-9903-v1-kriminalitat__strassen-_und_gewaltkriminalitat_seit_2008.csv"
    df = _read_csv(path)

    bezirk_col = next(c for c in df.columns if "stadtbezirk" in c.lower() and "nr" not in c.lower())
    jahr_col = "Jahr"

    # Jährlich aggregieren (Datensatz hat Monatswerte)
    straf_col = next((c for c in df.columns if "straßenkriminalität erfasste" in c.lower()), None)
    gewalt_col = next((c for c in df.columns if "gewaltkriminalität erfasste" in c.lower()), None)

    cols = [c for c in [straf_col, gewalt_col] if c is not None]
    for col in cols:
        df[col] = _to_numeric_col(df[col])

    df_jahr = df.groupby([bezirk_col, jahr_col])[cols].sum().reset_index()

    rename = {}
    if straf_col:
        rename[straf_col] = "strassenkriminalitaet_faelle"
    if gewalt_col:
        rename[gewalt_col] = "gewaltkriminalitaet_faelle"
    df_jahr = df_jahr.rename(columns=rename)
    wert_spalten = list(rename.values())

    return {
        "df": df_jahr,
        "wert_spalten": wert_spalten,
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "kriminalitaet",
        "dimension": "sicherheit",
    }


# ── Unfälle ───────────────────────────────────────────────────────────────────

def load_unfaelle(raw_dir: Path) -> dict[str, Any]:
    """Straßenverkehrsunfälle nach Stadtbezirken."""
    path = raw_dir / "unfalle_nach_sach_personen_stadtbezirk.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"
    wert_col = "Unfälle"

    df[wert_col] = _to_numeric_col(df[wert_col])

    # Jahressumme über alle Unfallgruppen
    df_jahr = df.groupby([bezirk_col, jahr_col])[wert_col].sum().reset_index()
    df_jahr = df_jahr.rename(columns={wert_col: "unfaelle_gesamt"})

    return {
        "df": df_jahr,
        "wert_spalten": ["unfaelle_gesamt"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "unfaelle",
        "dimension": "sicherheit",
    }


# ── Einwohner nach Altersgruppe (Kinder 0–17) ────────────────────────────────

def load_einwohner_kinder(raw_dir: Path) -> dict[str, Any]:
    """Einwohner 0–17 Jahre nach Stadtbezirken (für Bedarfsgewicht)."""
    path = raw_dir / "einwohner-in-stuttgart-nach-altersgruppen-und-stadtbezirken-seit-1986.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    # Stichtag → Jahr extrahieren
    df["Jahr"] = pd.to_datetime(df["Stichtag"], dayfirst=True, errors="coerce").dt.year

    wert_col = "Einwohner"
    df[wert_col] = _to_numeric_col(df[wert_col])

    # Nur Altersgruppen 0–18 Jahre summieren
    kinder_mask = df["Alter in 10 Gruppen"].str.contains(
        r"0 bis|3 bis|6 bis|15 bis unter 18", regex=True, na=False
    )
    df_kinder = (
        df[kinder_mask]
        .groupby([bezirk_col, "Jahr"])[wert_col]
        .sum()
        .reset_index()
        .rename(columns={wert_col: "einwohner_kinder_0_17"})
    )

    return {
        "df": df_kinder,
        "wert_spalten": ["einwohner_kinder_0_17"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": "Jahr",
        "modus": "count",
        "indikator": "einwohner_kinder",
        "dimension": "demografie",
    }


# ── Binnenumzüge (Instabilität) ───────────────────────────────────────────────

def load_binnenumzuege(raw_dir: Path) -> dict[str, Any]:
    """Binnenumzüge nach Stadtbezirken (Indikator für soziale Instabilität).

    Dateiformat: (Jahr, Wegzug-Bezirk, Zuzug-Bezirk, Anzahl) — OD-Matrix.
    Wir aggregieren: Gesamtzuzüge IN jeden Bezirk pro Jahr.
    """
    path = raw_dir / "test_2.5.6-binnenumzuge-in-stuttgart-nach-stadtbezirken_seit1994.csv"
    df = _read_csv(path)

    jahr_col = "Jahr"
    zuzug_col = next(c for c in df.columns if "zuzug" in c.lower() and "bezirk" in c.lower())
    wert_col = next(c for c in df.columns if c not in [jahr_col] and
                    pd.to_numeric(df[c], errors="coerce").notna().sum() > 5 and "bezirk" not in c.lower())

    df[wert_col] = _to_numeric_col(df[wert_col])
    # Aggregiere: Gesamtzuzüge pro Zuzug-Bezirk und Jahr
    df_agg = df.groupby([zuzug_col, jahr_col])[wert_col].sum().reset_index()
    df_agg = df_agg.rename(columns={zuzug_col: "Stadtbezirk", wert_col: "binnenumzuege"})

    return {
        "df": df_agg,
        "wert_spalten": ["binnenumzuege"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "binnenumzuege",
        "dimension": "soziales",
    }


# ── Wohnungen ─────────────────────────────────────────────────────────────────

def load_wohnungen(raw_dir: Path) -> dict[str, Any]:
    """Wohnungsbestand nach Stadtbezirken.

    Dateiformat: (Stichtag, Bezirk, Wohnungsgröße, Anzahl) — aggregiere über alle Größen.
    """
    path = raw_dir / "tidy_bestand_wohnungen_stadtbezirke_seit_1995.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    # Stichtag → Jahr
    df["Jahr"] = pd.to_datetime(df["Stichtag"], dayfirst=True, errors="coerce").dt.year
    wert_col = "Anzahl"

    df[wert_col] = _to_numeric_col(df[wert_col])
    # Aggregiere über Wohnungsgrößen
    df_agg = df.groupby([bezirk_col, "Jahr"])[wert_col].sum().reset_index()
    df_agg = df_agg.rename(columns={wert_col: "wohnungsbestand"})

    return {
        "df": df_agg,
        "wert_spalten": ["wohnungsbestand"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": "Jahr",
        "modus": "count",
        "indikator": "wohnungsbestand",
        "dimension": "wohnen",
    }


# ── Sozialmietwohnungen ───────────────────────────────────────────────────────

def load_sozialmietwohnungen(raw_dir: Path) -> dict[str, Any]:
    """Sozialmietwohnungen 2023 nach Stadtbezirken.

    Dateiformat: Stadtteil-Ebene mit Spalte 'Stadtbezirk' — aggregiere zu Bezirksebene.
    """
    path = raw_dir / "sozialmietwohnungen_2023_sst.csv"
    df = _read_csv(path)

    # CSV ist auf Stadtteil-Ebene; 'Stadtbezirk' ist eine eigene Spalte
    bezirk_col = next(
        (c for c in df.columns if c.lower() == "stadtbezirk"),
        next((c for c in df.columns if "bezirk" in c.lower() and "nr" not in c.lower()), None),
    )
    if bezirk_col is None:
        raise ValueError("Keine Stadtbezirk-Spalte in Sozialmietwohnungen-Datensatz")

    wert_col = next(
        (c for c in df.columns if "anz" in c.lower() and "sozial" in c.lower()),
        next(
            (c for c in df.columns
             if c != bezirk_col and pd.to_numeric(df[c], errors="coerce").notna().sum() > 5),
            None,
        ),
    )
    if wert_col is None:
        raise ValueError("Keine Wert-Spalte in Sozialmietwohnungen-Datensatz")

    df[wert_col] = _to_numeric_col(df[wert_col])
    # Aggregiere Stadtteil-Werte zu Bezirksebene
    df_bezirk = (
        df.groupby(bezirk_col)[wert_col]
        .sum(min_count=1)
        .reset_index()
        .rename(columns={wert_col: "sozialmietwohnungen"})
    )
    df_bezirk["Jahr"] = 2023

    logger.info(
        "Sozialmietwohnungen: %d Stadtteile → %d Bezirke aggregiert",
        len(df),
        df_bezirk["sozialmietwohnungen"].notna().sum(),
    )

    return {
        "df": df_bezirk,
        "wert_spalten": ["sozialmietwohnungen"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": "Jahr",
        "modus": "count",
        "indikator": "sozialmietwohnungen",
        "dimension": "wohnen",
    }


# ── PKW nach Antriebsart ──────────────────────────────────────────────────────

def load_pkw_stadtbezirk(raw_dir: Path) -> dict[str, Any]:
    """PKW-Bestand nach Stadtbezirken (Mobilitätsindikator).

    Dateiformat: (Jahr, Bezirk, Kraftstoffart, Haltertyp, Anzahl) — aggregiere zu Gesamt-PKW.
    """
    path = raw_dir / "pkw_nach_antriebsart_stadtbezirk.csv"
    df = _read_csv(path)

    bezirk_col = "Stadtbezirk"
    jahr_col = "Jahr"
    wert_col = next((c for c in df.columns if "insgesamt" in c.lower() or "gesamt" in c.lower()), None)
    if wert_col is None:
        raise ValueError("Keine Gesamt-Spalte im PKW-Datensatz")

    df[wert_col] = _to_numeric_col(df[wert_col])
    # Aggregiere über Kraftstoffart und Haltertyp
    df_agg = df.groupby([bezirk_col, jahr_col])[wert_col].sum().reset_index()
    df_agg = df_agg.rename(columns={wert_col: "pkw_gesamt"})

    return {
        "df": df_agg,
        "wert_spalten": ["pkw_gesamt"],
        "bezirk_spalte": bezirk_col,
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "pkw_bestand",
        "dimension": "mobilitaet",
    }


# ── Alle 23 Stuttgarter Stadtbezirke ─────────────────────────────────────────

_BEZIRKE: list[str] = [
    "Stuttgart-Mitte",
    "Stuttgart-Nord",
    "Stuttgart-Ost",
    "Stuttgart-Süd",
    "Stuttgart-West",
    "Bad Cannstatt",
    "Birkach",
    "Botnang",
    "Degerloch",
    "Feuerbach",
    "Hedelfingen",
    "Möhringen",
    "Mühlhausen",
    "Münster",
    "Obertürkheim",
    "Plieningen",
    "Sillenbuch",
    "Stammheim",
    "Untertürkheim",
    "Vaihingen",
    "Wangen",
    "Weilimdorf",
    "Zuffenhausen",
]


def _distribute_citywide(
    serie: pd.Series,
    jahr_col: str,
    wert_col: str,
) -> pd.DataFrame:
    """Verteilt gesamtstädtische Jahreswerte gleichmäßig auf alle 23 Bezirke.

    Die Disaggregation gewichtet diese Basiswerte später nach Bevölkerung.

    Args:
        serie: DataFrame mit Spalten [Jahr, wert_col].
        jahr_col: Name der Jahresspalte.
        wert_col: Name der Wertspalte.

    Returns:
        DataFrame mit Spalten [Stadtbezirk, Jahr, wert_col] — 23 Zeilen pro Jahr.
    """
    rows: list[dict[str, Any]] = []
    for _, row in serie.iterrows():
        for bezirk in _BEZIRKE:
            rows.append(
                {
                    "Stadtbezirk": bezirk,
                    jahr_col: row[jahr_col],
                    wert_col: row[wert_col],
                }
            )
    return pd.DataFrame(rows)


# ── Schulen nach Stadtbezirken ────────────────────────────────────────────────


def load_schulen_bezirk(raw_dir: Path) -> dict[str, Any]:
    """Gymnasium-Anteil an Gesamtschülern nach Stadtbezirken (Bildungsindikator).

    Quelle: oeffentliche_allgemeinbilde_schulen_klassen_schueler_nach_stadtbezirken_seit_2013.csv
    Schuljahre im Format '2022/2023' werden auf das Endjahr gemappt.
    """
    path = raw_dir / "oeffentliche_allgemeinbilde_schulen_klassen_schueler_nach_stadtbezirken_seit_2013.csv"
    if not path.exists():
        logger.warning("Schulen-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["gymnasium_anteil"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "gymnasium_anteil",
            "dimension": "bildung",
        }
    df = _read_csv(path)

    bezirk_col = next(
        (c for c in df.columns if "stadtbezirk" in c.lower() and "nr" not in c.lower()),
        "Stadtbezirk",
    )
    schuljahr_col = next(
        (c for c in df.columns if c.lower() in ("jahr", "schuljahr")),
        df.columns[0],
    )

    # Schuljahr '2022/2023' → 2023 (Endjahr)
    df["Jahr"] = (
        df[schuljahr_col]
        .astype(str)
        .str.extract(r"(\d{4})/?(\d{4})?")[1]
        .fillna(df[schuljahr_col].astype(str).str.extract(r"(\d{4})")[0])
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )

    # Column names may contain embedded newlines from CSV quoting — normalise before matching
    col_lower = {c: c.lower().replace("\n", " ") for c in df.columns}

    gym_col = next(
        (
            c
            for c, cl in col_lower.items()
            if ("gymnasium" in cl or "gymnasien" in cl) and ("schüler" in cl or "schueler" in cl)
        ),
        None,
    )

    schueler_cols = [
        c for c, cl in col_lower.items()
        if ("schüler" in cl or "schueler" in cl) and "klassen" not in cl
    ]

    if gym_col is None or not schueler_cols:
        logger.warning("Schulen-Datensatz: Gymnasium- oder Schüler-Spalten nicht gefunden. Spalten: %s", df.columns.tolist())
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["gymnasium_anteil"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "gymnasium_anteil",
            "dimension": "bildung",
        }

    for col in [gym_col, *schueler_cols]:
        df[col] = _to_numeric_col(df[col])

    df["schueler_gesamt"] = df[schueler_cols].sum(axis=1)
    df["gymnasium_anteil"] = df[gym_col] / df["schueler_gesamt"].replace(0, float("nan"))

    df_out = df[[bezirk_col, "Jahr", "gymnasium_anteil"]].dropna(subset=[bezirk_col])
    df_out = df_out.rename(columns={bezirk_col: "Stadtbezirk"})

    logger.info("Schulen: %d Bezirk-Jahr-Kombinationen geladen", len(df_out.dropna()))

    return {
        "df": df_out,
        "wert_spalten": ["gymnasium_anteil"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": "Jahr",
        "modus": "rate",
        "indikator": "gymnasium_anteil",
        "dimension": "bildung",
    }


# ── Jugendarbeitslosigkeit nach Stadtbezirken ─────────────────────────────────


def load_jugend_arbeitslosigkeit(raw_dir: Path) -> dict[str, Any]:
    """Arbeitslos gemeldete unter 25 Jahre nach Stadtbezirken.

    Quelle: arbeitslos_gemeldete_nach_stadtbezirken_seit_2005.csv
    """
    path = raw_dir / "arbeitslos_gemeldete_nach_stadtbezirken_seit_2005.csv"
    if not path.exists():
        logger.warning("Jugendarbeitslosigkeit-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["jugend_arbeitslose"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "count",
            "indikator": "jugend_arbeitslosigkeit",
            "dimension": "bildung",
        }
    df = _read_csv(path)

    bezirk_col = next(
        c
        for c in df.columns
        if "stadtbezirk" in c.lower()
        and "nr" not in c.lower()
        and "nummer" not in c.lower()
    )
    jahr_col = next(c for c in df.columns if c.lower() == "jahr")

    jugend_col = next(
        (
            c
            for c in df.columns
            if re.search(r"unter\s*25|jugend|unter25", c.lower())
            and c not in (bezirk_col, jahr_col)
        ),
        None,
    )
    if jugend_col is None:
        logger.warning(
            "Jugendarbeitslosigkeit: Spalte 'unter 25' nicht gefunden. Spalten: %s",
            df.columns.tolist(),
        )
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["jugend_arbeitslose"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "count",
            "indikator": "jugend_arbeitslosigkeit",
            "dimension": "bildung",
        }

    df[jugend_col] = _to_numeric_col(df[jugend_col])
    df_out = df[[bezirk_col, jahr_col, jugend_col]].dropna(subset=[bezirk_col])
    df_out = df_out.rename(columns={bezirk_col: "Stadtbezirk", jugend_col: "jugend_arbeitslose"})

    logger.info("Jugendarbeitslosigkeit: %d Bezirk-Jahr-Kombinationen geladen", len(df_out.dropna()))

    return {
        "df": df_out,
        "wert_spalten": ["jugend_arbeitslose"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "jugend_arbeitslosigkeit",
        "dimension": "bildung",
    }


# ── SSB Fahrgäste (gesamtstädtisch) ──────────────────────────────────────────


def load_ssb_fahrgaeste(raw_dir: Path) -> dict[str, Any]:
    """Beförderte Personen SSB/ÖPNV pro Jahr, gleichmäßig auf 23 Bezirke verteilt.

    Quelle: ssb_opnv_1980_bis_2024.csv
    Gesamtstädtische Daten; Disaggregation gewichtet später nach Bevölkerung.
    """
    path = raw_dir / "ssb_opnv_1980_bis_2024.csv"
    if not path.exists():
        logger.warning("SSB-ÖPNV-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["ssb_fahrgaeste"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "count",
            "indikator": "ssb_fahrgaeste",
            "dimension": "mobilitaet",
        }
    df = _read_csv(path)

    merkmal_col = next(c for c in df.columns if "merkmal" in c.lower())
    kategorie_col = next(c for c in df.columns if "kategorie" in c.lower())
    jahr_col = next(c for c in df.columns if c.lower() == "jahr")
    wert_col = next(c for c in df.columns if "anzahl" in c.lower() or "wert" in c.lower())

    # Gesamtzahl beförderter Personen (Kategorie "insgesamt")
    mask = (
        df[merkmal_col].str.contains("Beförderte Personen", case=False, na=False)
        & df[kategorie_col].str.strip().str.lower().eq("insgesamt")
    )
    df_total = df.loc[mask, [jahr_col, wert_col]].copy()
    df_total[wert_col] = _to_numeric_col(df_total[wert_col])
    df_total = df_total.dropna(subset=[wert_col])
    df_total = df_total.rename(columns={wert_col: "ssb_fahrgaeste"})

    df_out = _distribute_citywide(df_total, jahr_col, "ssb_fahrgaeste")
    logger.info(
        "SSB Fahrgäste: %d Jahre × 23 Bezirke = %d Zeilen verteilt",
        len(df_total),
        len(df_out),
    )

    return {
        "df": df_out,
        "wert_spalten": ["ssb_fahrgaeste"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "ssb_fahrgaeste",
        "dimension": "mobilitaet",
    }


# ── Energieverbrauch (gesamtstädtisch) ───────────────────────────────────────


def load_energie_verbrauch(raw_dir: Path) -> dict[str, Any]:
    """Stromverbrauch in GWh pro Jahr, gleichmäßig auf 23 Bezirke verteilt.

    Quelle: energie_und_wasserverbrauch_stuttgart.csv
    Gesamtstädtische Daten; Disaggregation gewichtet später nach Bevölkerung.
    """
    path = raw_dir / "energie_und_wasserverbrauch_stuttgart.csv"
    if not path.exists():
        logger.warning("Energieverbrauch-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["energie_verbrauch"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "count",
            "indikator": "energie_verbrauch",
            "dimension": "wirtschaft",
        }
    df = _read_csv(path)

    merkmal_col = next(c for c in df.columns if "merkmal" in c.lower())
    kategorie_col = next(c for c in df.columns if "kategorie" in c.lower())
    auspraegung_col = next(
        (c for c in df.columns if "ausprägung" in c.lower() or "auspraegung" in c.lower()),
        None,
    )
    jahr_col = next(c for c in df.columns if c.lower() == "jahr")
    wert_col = next(c for c in df.columns if "anzahl" in c.lower() or "wert" in c.lower())

    # Stromverbrauch insgesamt in GWh
    strom_mask = df[kategorie_col].str.contains("Strom", case=False, na=False)
    if auspraegung_col:
        strom_mask &= df[auspraegung_col].str.strip().str.lower().eq("insgesamt")

    df_strom = df.loc[strom_mask, [jahr_col, wert_col]].copy()
    df_strom[wert_col] = _to_numeric_col(df_strom[wert_col])
    df_strom = df_strom.dropna(subset=[wert_col])
    df_strom = df_strom.rename(columns={wert_col: "energie_verbrauch"})

    df_out = _distribute_citywide(df_strom, jahr_col, "energie_verbrauch")
    logger.info(
        "Energieverbrauch: %d Jahre × 23 Bezirke = %d Zeilen verteilt",
        len(df_strom),
        len(df_out),
    )

    return {
        "df": df_out,
        "wert_spalten": ["energie_verbrauch"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "count",
        "indikator": "energie_verbrauch",
        "dimension": "wirtschaft",
    }


# ── Luftqualität (gesamtstädtisch) ────────────────────────────────────────────


def load_luftqualitaet(raw_dir: Path) -> dict[str, Any]:
    """NO2-Jahresmittelwert (Mittel beider Messstationen) auf 23 Bezirke verteilt.

    Quelle: luftqualitat.csv
    Gesamtstädtische Daten; Disaggregation gewichtet später nach Bevölkerung.
    """
    path = raw_dir / "luftqualitat.csv"
    if not path.exists():
        logger.warning("Luftqualität-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["luftqualitaet"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "luftqualitaet",
            "dimension": "gesundheit",
        }
    df = _read_csv(path)

    jahr_col = next(c for c in df.columns if c.lower() == "jahr")
    no2_cols = [c for c in df.columns if "no2" in c.lower() or "NO2" in c]

    if not no2_cols:
        logger.warning("Luftqualität: Keine NO2-Spalten gefunden. Spalten: %s", df.columns.tolist())
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["luftqualitaet"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "luftqualitaet",
            "dimension": "gesundheit",
        }

    for col in no2_cols:
        df[col] = _to_numeric_col(df[col])

    df["luftqualitaet"] = df[no2_cols].mean(axis=1)

    df_total = df[[jahr_col, "luftqualitaet"]].dropna(subset=["luftqualitaet"]).copy()
    df_total[jahr_col] = pd.to_numeric(df_total[jahr_col], errors="coerce")
    df_total = df_total.dropna(subset=[jahr_col])

    df_out = _distribute_citywide(df_total, jahr_col, "luftqualitaet")
    logger.info(
        "Luftqualität: %d Jahre × 23 Bezirke = %d Zeilen verteilt",
        len(df_total),
        len(df_out),
    )

    return {
        "df": df_out,
        "wert_spalten": ["luftqualitaet"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "rate",
        "indikator": "luftqualitaet",
        "dimension": "gesundheit",
    }


# ── Lärmbelastung (gesamtstädtisch) ──────────────────────────────────────────


def load_laermbelastung(raw_dir: Path) -> dict[str, Any]:
    """Anteil Bevölkerung mit Straßenlärmbelastung > 65 dB(A) auf 23 Bezirke verteilt.

    Quelle: larmbelastung.csv  (sporadische Messjahre — NaN-Jahre werden verworfen)
    Gesamtstädtische Daten; Disaggregation gewichtet später nach Bevölkerung.
    """
    path = raw_dir / "larmbelastung.csv"
    if not path.exists():
        logger.warning("Lärmbelastung-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["laermbelastung"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "laermbelastung",
            "dimension": "gesundheit",
        }
    df = _read_csv(path)

    jahr_col = next(c for c in df.columns if c.lower() == "jahr")
    laerm_col = next(
        (c for c in df.columns if "65" in c and ("lärm" in c.lower() or "larm" in c.lower())),
        None,
    )
    if laerm_col is None:
        # Fallback: erste nicht-Jahr-Spalte mit numerischen Werten
        laerm_col = next(
            c for c in df.columns
            if c != jahr_col and pd.to_numeric(df[c], errors="coerce").notna().sum() > 0
        )

    df[laerm_col] = _to_numeric_col(df[laerm_col])
    df[jahr_col] = pd.to_numeric(df[jahr_col], errors="coerce")
    df_total = df[[jahr_col, laerm_col]].dropna().rename(columns={laerm_col: "laermbelastung"})

    df_out = _distribute_citywide(df_total, jahr_col, "laermbelastung")
    logger.info(
        "Lärmbelastung: %d Messjahre × 23 Bezirke = %d Zeilen verteilt",
        len(df_total),
        len(df_out),
    )

    return {
        "df": df_out,
        "wert_spalten": ["laermbelastung"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "rate",
        "indikator": "laermbelastung",
        "dimension": "gesundheit",
    }


# ── Ärztliche Versorgung (gesamtstädtisch) ────────────────────────────────────


def load_arztdichte(raw_dir: Path) -> dict[str, Any]:
    """Ärzte pro 100.000 Einwohner pro Jahr auf 23 Bezirke verteilt.

    Quelle: arztliche_versorgung_stuttgart_seit_2010.csv
    Gesamtstädtische Daten; Disaggregation lässt den Wert als Rate konstant.
    """
    path = raw_dir / "arztliche_versorgung_stuttgart_seit_2010.csv"
    if not path.exists():
        logger.warning("Ärztliche-Versorgung-Datei nicht gefunden: %s", path)
        return {
            "df": pd.DataFrame(),
            "wert_spalten": ["arztdichte"],
            "bezirk_spalte": "Stadtbezirk",
            "jahr_spalte": "Jahr",
            "modus": "rate",
            "indikator": "arztdichte",
            "dimension": "gesundheit",
        }
    df = _read_csv(path)

    jahr_col = next(c for c in df.columns if c.lower() == "jahr")
    arzt_col = next(
        (c for c in df.columns if "arzt" in c.lower() or "ärzt" in c.lower() or "arzte" in c.lower()),
        None,
    )
    if arzt_col is None:
        arzt_col = next(c for c in df.columns if c != jahr_col)

    df[arzt_col] = _to_numeric_col(df[arzt_col])
    df[jahr_col] = pd.to_numeric(df[jahr_col], errors="coerce")
    df_total = df[[jahr_col, arzt_col]].dropna().rename(columns={arzt_col: "arztdichte"})

    df_out = _distribute_citywide(df_total, jahr_col, "arztdichte")
    logger.info(
        "Arztdichte: %d Jahre × 23 Bezirke = %d Zeilen verteilt",
        len(df_total),
        len(df_out),
    )

    return {
        "df": df_out,
        "wert_spalten": ["arztdichte"],
        "bezirk_spalte": "Stadtbezirk",
        "jahr_spalte": jahr_col,
        "modus": "rate",
        "indikator": "arztdichte",
        "dimension": "gesundheit",
    }


# ── Registry aller Loader ─────────────────────────────────────────────────────

ALL_LOADERS: dict[str, Any] = {
    "sgbii_kinder": load_sgbii,
    "sv_beschaeftigung": load_beschaeftigung,
    "eigentuemer_quote": load_eigentuemer,
    "einkommen_index": load_einkommen,
    "kriminalitaet": load_kriminalitaet,
    "unfaelle": load_unfaelle,
    "einwohner_kinder": load_einwohner_kinder,
    "binnenumzuege": load_binnenumzuege,
    "wohnungsbestand": load_wohnungen,
    "sozialmietwohnungen": load_sozialmietwohnungen,
    "pkw_bestand": load_pkw_stadtbezirk,
    # New loaders
    "schulen_bezirk": load_schulen_bezirk,
    "jugend_arbeitslosigkeit": load_jugend_arbeitslosigkeit,
    "ssb_fahrgaeste": load_ssb_fahrgaeste,
    "energie_verbrauch": load_energie_verbrauch,
    "luftqualitaet": load_luftqualitaet,
    "laermbelastung": load_laermbelastung,
    "arztdichte": load_arztdichte,
}
