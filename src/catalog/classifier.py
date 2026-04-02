"""Thematische Klassifikation von Datensätzen.

Ordnet jeden Datensatz einer oder mehreren Dimensionen des Aufwachsindex zu
und markiert ob er index-relevant ist.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Schlüsselwörter pro Dimension (im Dateinamen oder Spaltennamen suchen)
DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "bildung": [
        "schul", "schueler", "schulabgang", "schulabschluss", "gymnasium",
        "grundschule", "uebergang", "bildung", "kita", "kinderbetreuung",
        "betreuungsquote", "lehrerin", "lehrer",
    ],
    "gesundheit": [
        "arzt", "aerztlich", "krankenhaus", "pfleg", "patient", "diagnose",
        "gesundheit", "pflegebeduerft", "pflegegrad", "bett", "klinik",
    ],
    "sicherheit": [
        "kriminal", "straftat", "tatverdaecht", "delikte", "unfall",
        "strassenverkehrsunfall", "gewalt", "opfer",
    ],
    "mobilitaet": [
        "ssb", "opnv", "vvs", "buslinie", "haltestelle", "gtfs", "fahrgast",
        "mobilitaet", "radfahrend", "pkw", "verkehr", "strassenbahn",
    ],
    "wohnen": [
        "wohnung", "wohngebaeude", "wohnflaeche", "eigentuemer", "mietwohnung",
        "sozialmietwohnung", "baufertigstellung", "bauabgang", "baugenehmigung",
        "gefoerdert", "wohngebiet",
    ],
    "wirtschaft": [
        "beschaftigt", "beschaeftigung", "arbeitgeber", "unternehmen",
        "existenzgruendung", "insolvenz", "handwerk", "gewerbe",
        "beschaftigungsquote", "einkommen", "steuer",
    ],
    "umwelt": [
        "luft", "laerm", "emission", "co2", "treibhausgas", "immission",
        "naturschutz", "flaeche", "flachennutzung", "energie", "wasser",
    ],
    "soziales": [
        "sozial", "sozialgeld", "sgb", "armut", "mindestsicherung",
        "auslaender", "migration", "bevoelkerung", "einwohner", "wanderung",
        "alleinerziehend", "kind", "jugend",
    ],
    "kultur_freizeit": [
        "schwimmbad", "theater", "buecherei", "bibliothek", "museum",
        "kino", "sport", "verein", "wilhelma", "fernsehturm",
        "freizeitangebot",
    ],
    "demografie": [
        "einwohner", "altersgruppe", "geburt", "geburtenziffer", "haushalt",
        "bevoelkerung", "binnenumzug", "wohndauer", "stadtbezirk_bevoelkerung",
        "wanderung", "einwohnerbilanz",
    ],
}

# Datensätze die NICHT index-relevant sind
NICHT_INDEX_RELEVANT_KEYWORDS: list[str] = [
    "wahl", "bundestagswahl", "landtagswahl", "ob-wahl", "oberbuergermeister",
    "gemeinderat", "sitzverteilung", "bezirksbeirat",
    "flugzeug", "luftverkehr", "flugziel", "flughafen",
    "hafen", "messe", "ausstellung", "tourismus", "gaeste", "beherbergung",
    "uebernachtung", "fernsehturn", "wilhelma",
    "wetter",
    "studierende", "universitaet", "hochschule",
]


def classify_dataset(datei: str, spalten: list[str]) -> dict[str, Any]:
    """Klassifiziert einen Datensatz thematisch.

    Args:
        datei: Dateiname (ohne Pfad).
        spalten: Liste der Spaltennamen.

    Returns:
        Dictionary mit 'dimensionen', 'thema' und 'index_relevant'.
    """
    suchtext = (datei + " " + " ".join(spalten)).lower()
    # Sonderzeichen normalisieren
    suchtext = re.sub(r"[_\-\.]", " ", suchtext)
    suchtext = suchtext.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")

    gefundene_dimensionen: list[str] = []
    for dimension, keywords in DIMENSION_KEYWORDS.items():
        for kw in keywords:
            kw_norm = kw.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            if kw_norm in suchtext:
                if dimension not in gefundene_dimensionen:
                    gefundene_dimensionen.append(dimension)
                break

    # Index-Relevanz prüfen
    index_relevant = True
    for kw in NICHT_INDEX_RELEVANT_KEYWORDS:
        kw_norm = kw.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        if kw_norm in suchtext:
            index_relevant = False
            break

    # Wenn keine Dimension gefunden: als "sonstig" markieren
    if not gefundene_dimensionen:
        gefundene_dimensionen = ["sonstig"]
        index_relevant = False

    # Primäres Thema = erste Dimension (die spezifischste)
    thema = gefundene_dimensionen[0] if gefundene_dimensionen else "sonstig"

    return {
        "dimensionen": gefundene_dimensionen,
        "thema": thema,
        "index_relevant": index_relevant,
    }
