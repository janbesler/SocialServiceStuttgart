"""Bestehende Sozialeinrichtungen laden, klassifizieren und georeferenzieren.

Liest `data/osm/sozialeinrichtungen.geojson`, klassifiziert jede Einrichtung
nach Typ und weist sie per Spatial Join dem zugehörigen Stadtbezirk zu.
Nicht-jugendrelevante Einrichtungen (Pflegeheime, ambulante Pflegedienste etc.)
werden herausgefiltert.

Ausgabe: `data/placement/bestand.geojson`
"""

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Klassifikations-Tabellen
# ---------------------------------------------------------------------------

# OSM-social_facility-Tags, die raus fallen (nicht jugendrelevant)
_AUSSCHLUSS_SOCIAL_FACILITY: frozenset[str] = frozenset(
    {
        "nursing_home",
        "assisted_living",
        "ambulatory_care",
        "hospice",
        "healthcare",
        "group_home",  # überwiegend Senioreneinrichtungen in Stuttgart
    }
)

# Schlüsselwörter im Namen, die auf nicht-jugendrelevante Einrichtungen hinweisen
_AUSSCHLUSS_NAME_KEYWORDS: tuple[str, ...] = (
    "pflegedienst",
    "pflege",
    "seniorenresidenz",
    "seniorenheim",
    "senioren",
    "tagespflege",
    "pflegezentrum",
    "hospiz",
    "alten",
    "ambulanter",
    "ambulante",
    "drk bereitschaft",
    "ambulanz",
)

# Schlüsselwörter → interner Typ
_TYP_REGELN: list[tuple[tuple[str, ...], str]] = [
    # Jugendhäuser
    (("jugendhaus", "jugendtreff", "jugendcafe", "jugendzentrum", "jugendklub",
      "kinder- und jugendhaus", "kinder & jugendhaus"), "jugendhaus"),
    # Mobile Jugendarbeit / Streetwork
    (("mobile jugendarbeit", "streetwork", "aufsuchende", "outreach jugend"), "mobile_jugendarbeit"),
    # Familien- und Stadtteilzentren
    (("familienzentrum", "stadtteilzentrum", "stadtteil- und familienzentrum",
      "stadtteil- & familienzentrum", "mehrgenerationenzentrum", "mehrgenerationen",
      "familien", "familienhilfe"), "familienzentrum"),
    # Bürgerzentren / Gemeinschaftshäuser
    (("bürgerforum", "bürgerhaus", "bürgerzentrum", "gemeindehaus", "gemeinschaftshaus",
      "quartierstreff", "begegnungsstätte", "begegnungs- und servicezentrum",
      "begegnungs- & servicezentrum", "nachbarschaftstreff", "nachbarschaft",
      "spielhaus"), "buergerzentrum"),
    # Beratungsstellen
    (("beratungsstelle", "beratung", "bereich armut", "schulden", "schuldner",
      "kontakt und information", "fachberatung"), "beratungsstelle"),
    # Tafeln / Foodbanks
    (("tafel",), "tafel"),
]


def _klassifiziere_typ(row: pd.Series) -> str:
    """Bestimmt den internen Typ einer Sozialeinrichtung.

    Args:
        row: Zeile des GeoDataFrame mit 'name', 'amenity', 'social_facility'.

    Returns:
        Interner Typ-String.
    """
    name_lower = str(row.get("name", "")).lower()
    amenity = str(row.get("amenity", "")).lower()
    social_facility = str(row.get("social_facility", "")).lower()

    # Namenbasierte Klassifikation (Priorität)
    for keywords, typ in _TYP_REGELN:
        if any(kw in name_lower for kw in keywords):
            return typ

    # OSM-Tag-basierte Fallback-Klassifikation
    if social_facility == "outreach":
        return "mobile_jugendarbeit"
    if amenity in ("youth_centre",) or social_facility in ("youth_centre",):
        return "jugendhaus"
    if amenity == "community_centre":
        return "buergerzentrum"
    if amenity in ("social_centre", "social_facility"):
        return "beratungsstelle"

    return "sonstige"


def _ist_jugendrelevant(row: pd.Series) -> bool:
    """Prüft, ob eine Einrichtung jugend- oder familienrelevant ist.

    Args:
        row: Zeile des GeoDataFrame.

    Returns:
        True wenn jugendrelevant, False für Ausschluss.
    """
    social_facility = str(row.get("social_facility", "")).lower()
    name_lower = str(row.get("name", "")).lower()

    # Explizite Ausschluss-Tags
    if social_facility in _AUSSCHLUSS_SOCIAL_FACILITY:
        return False

    # Namenbasierter Ausschluss
    if any(kw in name_lower for kw in _AUSSCHLUSS_NAME_KEYWORDS):
        return False

    return True


def load_bestand(
    sozial_path: Path,
    bezirke_path: Path,
) -> gpd.GeoDataFrame:
    """Lädt und klassifiziert bestehende Sozialeinrichtungen in Stuttgart.

    Filtert nicht-jugendrelevante Einrichtungen heraus, klassifiziert nach Typ
    und weist über einen Spatial Join den Stadtbezirk zu.

    Args:
        sozial_path: Pfad zu `sozialeinrichtungen.geojson` (OSM-Export).
        bezirke_path: Pfad zu `bezirke.geojson` (23 Stadtbezirke).

    Returns:
        GeoDataFrame mit Spalten:
        - osm_id, osm_type, name (aus OSM)
        - typ (jugendhaus | mobile_jugendarbeit | familienzentrum |
               buergerzentrum | beratungsstelle | tafel | sonstige)
        - bezirk (Stadtbezirksname)
        - quelle ("osm")
        Geometrie: Point, EPSG:4326.

    Raises:
        FileNotFoundError: Wenn eine der Eingabedateien fehlt.
    """
    if not sozial_path.exists():
        raise FileNotFoundError(f"sozialeinrichtungen.geojson nicht gefunden: {sozial_path}")
    if not bezirke_path.exists():
        raise FileNotFoundError(f"bezirke.geojson nicht gefunden: {bezirke_path}")

    logger.info("Lade Sozialeinrichtungen aus %s", sozial_path.name)
    gdf = gpd.read_file(sozial_path)
    logger.info("  %d Einrichtungen geladen (gesamt)", len(gdf))

    # Sicherstellen: EPSG:4326
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    # Duplikate entfernen (gleiche osm_id)
    gdf = gdf.drop_duplicates(subset="osm_id")

    # Jugend-Relevanz-Filter
    maske_relevant = gdf.apply(_ist_jugendrelevant, axis=1)
    n_gesamt = len(gdf)
    gdf = gdf[maske_relevant].copy()
    logger.info(
        "  %d nach Relevanz-Filter (von %d entfernt: %d nicht-jugendrelevant)",
        len(gdf),
        n_gesamt,
        n_gesamt - len(gdf),
    )

    # Typ-Klassifikation
    gdf["typ"] = gdf.apply(_klassifiziere_typ, axis=1)

    typ_counts = gdf["typ"].value_counts()
    for typ, anzahl in typ_counts.items():
        logger.info("    %-25s %d", typ, anzahl)

    # Spatial Join mit Bezirken
    logger.info("Spatial Join mit Bezirken...")
    bezirke = gpd.read_file(bezirke_path)
    if bezirke.crs is None:
        bezirke = bezirke.set_crs("EPSG:4326")
    else:
        bezirke = bezirke.to_crs("EPSG:4326")

    # Bezirks-Namenspalte ermitteln
    bezirk_col = _finde_bezirk_spalte(bezirke)
    bezirke_slim = bezirke[[bezirk_col, "geometry"]].rename(columns={bezirk_col: "bezirk"})

    gdf = gpd.sjoin(gdf, bezirke_slim, how="left", predicate="within")
    gdf["bezirk"] = gdf["bezirk"].fillna("unbekannt")

    # Unnötige Join-Spalten entfernen
    drop_cols = [c for c in gdf.columns if c.startswith("index_")]
    gdf = gdf.drop(columns=drop_cols, errors="ignore")

    # Quelle-Spalte
    gdf["quelle"] = "osm"

    # Ausgabe-Spalten normalisieren
    keep_cols = ["osm_id", "osm_type", "name", "amenity", "social_facility", "typ", "bezirk", "quelle", "geometry"]
    existing_keep = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[existing_keep].copy()

    logger.info(
        "Bestand geladen: %d Einrichtungen in %d Bezirken",
        len(gdf),
        gdf["bezirk"].nunique(),
    )
    return gdf


def _finde_bezirk_spalte(bezirke: gpd.GeoDataFrame) -> str:
    """Ermittelt die Namens-Spalte des Bezirks-GeoDataFrame.

    Args:
        bezirke: Bezirks-GeoDataFrame.

    Returns:
        Name der Spalte mit den Bezirksnamen.

    Raises:
        KeyError: Wenn keine passende Spalte gefunden wird.
    """
    for kandidat in ("name", "bezirk", "Name", "Bezirk", "BEZIRK"):
        if kandidat in bezirke.columns:
            return kandidat
    raise KeyError(
        f"Keine Bezirks-Namensspalte in {list(bezirke.columns)} gefunden. "
        "Erwartet: 'name' oder 'bezirk'."
    )


def merge_manuell(
    bestand_gdf: gpd.GeoDataFrame,
    manuell_path: Path,
) -> gpd.GeoDataFrame:
    """Merged manuelle Einrichtungen in den Bestand.

    Args:
        bestand_gdf: OSM-basierter Bestand (aus load_bestand).
        manuell_path: Pfad zu `bestand_manuell.json` mit manuellen Ergänzungen.

    Returns:
        Kombinierter GeoDataFrame mit OSM + manuellen Einrichtungen.
    """
    if not manuell_path.exists():
        logger.debug("Keine manuelle Ergänzungsliste gefunden: %s", manuell_path)
        return bestand_gdf

    import json

    logger.info("Lade manuelle Ergänzungen aus %s", manuell_path.name)
    with manuell_path.open(encoding="utf-8") as fh:
        eintraege = json.load(fh)

    rows = []
    for eintrag in eintraege:
        rows.append(
            {
                "osm_id": eintrag.get("id", f"manuell_{len(rows)}"),
                "osm_type": "manual",
                "name": eintrag.get("name", ""),
                "amenity": "",
                "social_facility": "",
                "typ": eintrag.get("typ", "sonstige"),
                "bezirk": eintrag.get("bezirk", "unbekannt"),
                "quelle": "manuell",
                "geometry": gpd.points_from_xy(
                    [eintrag["lon"]], [eintrag["lat"]]
                )[0],
            }
        )

    manuell_gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    combined = gpd.GeoDataFrame(
        pd.concat([bestand_gdf, manuell_gdf], ignore_index=True),
        crs="EPSG:4326",
    )
    logger.info(
        "Manuell hinzugefügt: %d Einrichtungen (gesamt: %d)",
        len(manuell_gdf),
        len(combined),
    )
    return combined
