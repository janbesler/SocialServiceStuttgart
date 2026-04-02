"""Overpass-API: Stadtbezirke, Straßen, Gebäude, POIs für Stuttgart abrufen.

Alle Antworten werden in data/osm/.cache/ gecacht um API-Rate-Limits zu schonen.
Mehrere Endpunkte werden als Fallback verwendet.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Overpass-Endpunkte in Reihenfolge (Fallback bei Fehler)
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

REQUEST_TIMEOUT = 300   # Sekunden pro Versuch (Overpass braucht bei großen Queries lang)
RETRY_BASE_DELAY = 30   # Sekunden Basis-Wartezeit (exponentiell steigend)
MAX_ATTEMPTS_PER_ENDPOINT = 4  # Versuche pro Endpunkt

# Datensätze die optional sind (Pipeline läuft auch ohne sie weiter)
# Leer: alle Datensätze sind Pflicht und werden so lange retried bis sie funktionieren
OPTIONAL_DATASETS: set[str] = set()


def _cache_path(cache_dir: Path, query: str) -> Path:
    """Berechnet den Cache-Pfad für eine Overpass-Anfrage.

    Args:
        cache_dir: Verzeichnis für Cache-Dateien.
        query: Overpass-QL Query-String.

    Returns:
        Pfad zur Cache-Datei.
    """
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    return cache_dir / f"overpass_{query_hash}.json"


def overpass_query(query: str, cache_dir: Path) -> dict[str, Any]:
    """Führt eine Overpass-API-Anfrage aus (mit Caching, mehrere Endpunkte).

    Args:
        query: Overpass-QL Query-String.
        cache_dir: Verzeichnis für Cache-Dateien.

    Returns:
        Overpass-JSON-Antwort als Dictionary.

    Raises:
        requests.HTTPError: Bei HTTP-Fehlern nach allen Endpunkten.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir, query)

    if cached.exists():
        logger.debug("Cache-Treffer: %s", cached.name)
        with cached.open(encoding="utf-8") as f:
            return json.load(f)

    logger.info("Overpass-Anfrage (kein Cache): %d Zeichen Query", len(query))
    last_exc: Exception | None = None
    total_attempt = 0

    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, MAX_ATTEMPTS_PER_ENDPOINT + 1):
            total_attempt += 1
            try:
                logger.info(
                    "  Versuch %d (Endpunkt %s, Versuch %d/%d)...",
                    total_attempt, endpoint, attempt, MAX_ATTEMPTS_PER_ENDPOINT,
                )
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                with cached.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                logger.info("Overpass-Antwort gecacht: %s (via %s)", cached.name, endpoint)
                return data

            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status in (429, 504, 502, 503):
                    # Exponentieller Backoff: 30s, 60s, 120s, 240s
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "  HTTP %d — warte %ds vor nächstem Versuch...", status, wait,
                    )
                    time.sleep(wait)
                    last_exc = exc
                else:
                    logger.warning("  HTTP %d — wechsle Endpunkt", status)
                    last_exc = exc
                    break  # Permanenter Fehler: direkt zum nächsten Endpunkt

            except requests.Timeout as exc:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("  Timeout — warte %ds vor nächstem Versuch...", wait)
                time.sleep(wait)
                last_exc = exc

            except requests.ConnectionError as exc:
                logger.warning("  Verbindungsfehler bei %s — wechsle Endpunkt", endpoint)
                last_exc = exc
                break  # Endpunkt nicht erreichbar: sofort wechseln

        logger.warning("Endpunkt %s erschöpft, versuche nächsten...", endpoint)

    raise RuntimeError(
        f"Overpass-Anfrage nach allen Endpunkten fehlgeschlagen: {last_exc}"
    )


# ── Vordefinierte Queries ─────────────────────────────────────────────────────

QUERY_STADTBEZIRKE = """
[out:json][timeout:60];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
rel(area.stuttgart)["admin_level"="9"];
out body;
>;
out skel qt;
"""

QUERY_STADTTEILE = """
[out:json][timeout:90];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
rel(area.stuttgart)["admin_level"="10"];
out body;
>;
out skel qt;
"""

QUERY_STRASSENNETZ = """
[out:json][timeout:180];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
way(area.stuttgart)["highway"~"^(primary|secondary|tertiary|residential)$"];
out body;
>;
out skel qt;
"""

QUERY_GEBAEUDE = """
[out:json][timeout:300];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
way(area.stuttgart)["building"];
out body;
>;
out skel qt;
"""

QUERY_POIS = """
[out:json][timeout:120];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
(
  nwr(area.stuttgart)["amenity"="school"];
  nwr(area.stuttgart)["amenity"="kindergarten"];
  nwr(area.stuttgart)["amenity"="clinic"];
  nwr(area.stuttgart)["amenity"="doctors"];
  nwr(area.stuttgart)["amenity"="hospital"];
  nwr(area.stuttgart)["leisure"="playground"];
  nwr(area.stuttgart)["leisure"="sports_centre"];
  nwr(area.stuttgart)["public_transport"="stop_position"];
);
out body;
>;
out skel qt;
"""

QUERY_SOZIALEINRICHTUNGEN = """
[out:json][timeout:60];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
(
  nwr(area.stuttgart)["amenity"="social_facility"];
  nwr(area.stuttgart)["social_facility"];
  nwr(area.stuttgart)["amenity"="social_centre"];
  nwr(area.stuttgart)["amenity"="community_centre"];
  nwr(area.stuttgart)["amenity"="youth_centre"];
  nwr(area.stuttgart)["social_facility"="youth_centre"];
  nwr(area.stuttgart)["social_facility"="outreach"];
  nwr(area.stuttgart)["office"="social_services"];
  nwr(area.stuttgart)["office"="counselling"];
  nwr(area.stuttgart)["social_facility"="counselling"];
  nwr(area.stuttgart)["community_centre:for"="juvenile"];
  nwr(area.stuttgart)["community_centre:for"="family"];
);
out body;
>;
out skel qt;
"""

_ALL_QUERIES: dict[str, str] = {
    "stadtbezirke": QUERY_STADTBEZIRKE,
    "stadtteile": QUERY_STADTTEILE,
    "strassennetz": QUERY_STRASSENNETZ,
    "gebaeude": QUERY_GEBAEUDE,
    "pois": QUERY_POIS,
    "sozialeinrichtungen": QUERY_SOZIALEINRICHTUNGEN,
}


def fetch_all(
    osm_dir: Path,
    skip: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Lädt alle benötigten OSM-Datensätze herunter (gecacht).

    Optionale Datensätze (stadtteile, gebaeude) werden bei Fehler übersprungen.

    Args:
        osm_dir: Ausgabe-Verzeichnis für OSM-Daten.
        skip: Datensatz-Namen die übersprungen werden sollen (leere Antwort).

    Returns:
        Dictionary mit Datensatz-Name → Overpass-Antwort.

    Raises:
        RuntimeError: Wenn ein Pflicht-Datensatz nicht geladen werden konnte.
    """
    cache_dir = osm_dir / ".cache"
    results: dict[str, dict[str, Any]] = {}
    skip = skip or set()

    for name, query in _ALL_QUERIES.items():
        if name in skip:
            logger.info("Überspringe Datensatz: %s (--skip)", name)
            results[name] = {"elements": []}
            continue

        logger.info("Lade OSM-Datensatz: %s", name)
        try:
            results[name] = overpass_query(query, cache_dir)
            element_count = len(results[name].get("elements", []))
            logger.info("  → %d Elemente", element_count)
        except Exception as exc:
            if name in OPTIONAL_DATASETS:
                logger.warning(
                    "Optionaler Datensatz '%s' nicht verfügbar (wird übersprungen): %s",
                    name, exc,
                )
                results[name] = {"elements": []}
            else:
                raise RuntimeError(
                    f"Pflicht-Datensatz '{name}' konnte nicht geladen werden: {exc}"
                ) from exc

    return results
