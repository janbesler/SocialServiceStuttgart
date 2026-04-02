"""Definition der Index-Dimensionen, Indikatoren und ihrer Gewichte.

Jeder Indikator ist definiert durch:
- Quelldatensatz (parquet-Dateiname ohne .parquet)
- Wertspalte im Datensatz
- Richtung: 'higher_worse' oder 'higher_better' (für Normalisierung)
- Berechnungsmethode: 'direct' (Rate), 'per_kinder' (÷ einwohner_kinder),
  'per_laenge' (÷ laenge_m × 100)
- Gewicht innerhalb der Dimension
"""

from dataclasses import dataclass, field
from typing import Literal

Richtung = Literal["higher_worse", "higher_better"]
Methode = Literal["direct", "per_kinder", "per_laenge"]


@dataclass
class IndikatorDef:
    """Definition eines einzelnen Indikators."""

    datensatz: str         # Parquet-Dateiname (ohne .parquet)
    spalte: str            # Wertspalte
    richtung: Richtung     # Ob höhere Werte schlechter (True) oder besser sind
    methode: Methode       # Normalisierungs-Methode
    gewicht: float         # Relatives Gewicht innerhalb der Dimension (sum = 1)
    label: str             # Lesbarer Name für Dashboard


@dataclass
class DimensionDef:
    """Definition einer Index-Dimension."""

    key: str               # Interner Schlüssel (z.B. 'oekonomie')
    label: str             # Lesbarer Name
    gewicht: float         # Gewicht im Gesamt-Index (alle Dimensionen sum = 1)
    indikatoren: list[IndikatorDef] = field(default_factory=list)


# ── Indikator-Definitionen ────────────────────────────────────────────────────

DIMENSIONEN: list[DimensionDef] = [
    DimensionDef(
        key="oekonomie",
        label="Ökonomische Prekarität",
        gewicht=0.25,
        indikatoren=[
            IndikatorDef(
                datensatz="sgbii_kinder",
                spalte="sgbii_kinder_unter18",
                richtung="higher_worse",
                methode="per_kinder",
                gewicht=0.40,
                label="SGB-II-Quote Kinder",
            ),
            IndikatorDef(
                datensatz="einkommen_index",
                spalte="einkommen_index",
                richtung="higher_better",
                methode="direct",
                gewicht=0.25,
                label="Einkommens-Index",
            ),
            IndikatorDef(
                datensatz="sv_beschaeftigung",
                spalte="sv_beschaeftigte",
                richtung="higher_better",
                methode="per_kinder",
                gewicht=0.20,
                label="Beschäftigungsquote",
            ),
            IndikatorDef(
                datensatz="energie_verbrauch",
                spalte="energie_verbrauch",
                richtung="higher_better",
                methode="per_laenge",
                gewicht=0.15,
                label="Energieverbrauch (Wirtschaftsindikator)",
            ),
        ],
    ),
    DimensionDef(
        key="bildung",
        label="Bildung",
        gewicht=0.20,
        indikatoren=[
            IndikatorDef(
                datensatz="schulen_bezirk",
                spalte="gymnasium_anteil",
                richtung="higher_better",
                methode="direct",
                gewicht=0.50,
                label="Gymnasialquote",
            ),
            IndikatorDef(
                datensatz="jugend_arbeitslosigkeit",
                spalte="jugend_arbeitslose",
                richtung="higher_worse",
                methode="per_kinder",
                gewicht=0.50,
                label="Jugendarbeitslosigkeit",
            ),
        ],
    ),
    DimensionDef(
        key="gesundheit",
        label="Gesundheit & Versorgung",
        gewicht=0.15,
        indikatoren=[
            IndikatorDef(
                datensatz="arztdichte",
                spalte="arztdichte",
                richtung="higher_better",
                methode="direct",
                gewicht=0.40,
                label="Ärztedichte",
            ),
            IndikatorDef(
                datensatz="luftqualitaet",
                spalte="luftqualitaet",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.35,
                label="Luftqualität (NO₂)",
            ),
            IndikatorDef(
                datensatz="laermbelastung",
                spalte="laermbelastung",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.25,
                label="Lärmbelastung",
            ),
        ],
    ),
    DimensionDef(
        key="sicherheit",
        label="Sicherheit",
        gewicht=0.10,
        indikatoren=[
            IndikatorDef(
                datensatz="kriminalitaet",
                spalte="strassenkriminalitaet_faelle",
                richtung="higher_worse",
                methode="per_laenge",
                gewicht=0.60,
                label="Straßenkriminalität",
            ),
            IndikatorDef(
                datensatz="unfaelle",
                spalte="unfaelle_gesamt",
                richtung="higher_worse",
                methode="per_laenge",
                gewicht=0.40,
                label="Unfälle",
            ),
        ],
    ),
    DimensionDef(
        key="wohnen",
        label="Wohnumfeld",
        gewicht=0.10,
        indikatoren=[
            IndikatorDef(
                datensatz="eigentuemer_quote",
                spalte="eigentuemer_quote_pct",
                richtung="higher_better",
                methode="direct",
                gewicht=0.60,
                label="Eigentümerquote",
            ),
            IndikatorDef(
                datensatz="sozialmietwohnungen",
                spalte="sozialmietwohnungen",
                richtung="higher_worse",
                methode="per_laenge",
                gewicht=0.40,
                label="Sozialmietwohnungsdichte",
            ),
        ],
    ),
    DimensionDef(
        key="mobilitaet",
        label="Mobilität & Teilhabe",
        gewicht=0.10,
        indikatoren=[
            IndikatorDef(
                datensatz="oepnv_erreichbarkeit",
                spalte="nearest_stop_dist_m",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.35,
                label="ÖPNV-Erreichbarkeit",
            ),
            IndikatorDef(
                datensatz="poi_erreichbarkeit",
                spalte="dist_nearest_schule_m",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.20,
                label="Schulerreichbarkeit",
            ),
            IndikatorDef(
                datensatz="poi_erreichbarkeit",
                spalte="dist_nearest_spielplatz_m",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.15,
                label="Spielplatzerreichbarkeit",
            ),
            IndikatorDef(
                datensatz="poi_erreichbarkeit",
                spalte="dist_nearest_sport_m",
                richtung="higher_worse",
                methode="direct",
                gewicht=0.10,
                label="Sporterreichbarkeit",
            ),
            IndikatorDef(
                datensatz="pkw_bestand",
                spalte="pkw_gesamt",
                richtung="higher_worse",
                methode="per_laenge",
                gewicht=0.20,
                label="PKW-Dichte",
            ),
        ],
    ),
    DimensionDef(
        key="soziale_kohäsion",
        label="Soziale Kohäsion",
        gewicht=0.10,
        indikatoren=[
            IndikatorDef(
                datensatz="binnenumzuege",
                spalte="binnenumzuege",
                richtung="higher_worse",
                methode="per_kinder",
                gewicht=1.0,
                label="Binnenumzugsrate",
            ),
        ],
    ),
]

DIMENSION_KEYS = {d.key for d in DIMENSIONEN}
VERFUEGBARE_GEWICHTE_SUMME = sum(d.gewicht for d in DIMENSIONEN)
