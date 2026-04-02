"""Standortoptimierung: MCLP und p-Median (greedy).

Zwei Modelle:

1. MCLP (Maximal Covering Location Problem) – exakte MILP-Lösung via PuLP.
   Maximiert die Summe des abgedeckten unversorgten Bedarfs.

2. p-Median greedy – iterative Heuristik, deutlich schneller für n≥10.

Kandidatenstandorte werden aus `data/osm/pois.geojson` extrahiert
(Schulen, Kitas, Bürgerzentren) und auf ÖPNV-Nähe (≤300 m) gefiltert.
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pulp
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)

UTM32N = "EPSG:25832"
WGS84 = "EPSG:4326"

# Kandidaten-ÖPNV-Radius (Luftlinie, Meter)
TRANSIT_RADIUS_M = 300.0
# Deduplizierungs-Radius für Kandidaten (Meter)
DEDUP_RADIUS_M = 50.0

# OSM-Amenity/Leisure-Werte, die als Kandidatenstandorte gelten
_KANDIDATEN_AMENITY: frozenset[str] = frozenset(
    {
        "school",
        "kindergarten",
        "community_centre",
        "social_centre",
        "social_facility",
        "library",
        "civic",
        "townhall",
        "youth_centre",
    }
)
_KANDIDATEN_LEISURE: frozenset[str] = frozenset(
    {
        "sports_centre",
        "community_centre",
    }
)


def _get_solver() -> pulp.LpSolver:
    """Gibt den besten verfügbaren MILP-Solver zurück.

    Probiert HiGHS zuerst (schneller), fällt auf CBC zurück.

    Returns:
        Initialisiertes LpSolver-Objekt.

    Raises:
        RuntimeError: Wenn kein Solver verfügbar ist.
    """
    for cls in [pulp.HiGHS_CMD, pulp.PULP_CBC_CMD]:
        try:
            solver = cls(msg=0, timeLimit=120)
            if solver.available():
                logger.debug("Verwende Solver: %s", cls.__name__)
                return solver
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(
        "Kein MILP-Solver verfügbar — PuLP mit HiGHS oder CBC installieren."
    )


def _coords_utm(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Gibt UTM32N-Koordinaten der Point-Geometrien zurück.

    Args:
        gdf: GeoDataFrame mit Point-Geometrien.

    Returns:
        (N, 2) float64-Array [x, y] in EPSG:25832.
    """
    gdf_utm = gdf.to_crs(UTM32N)
    return np.column_stack([gdf_utm.geometry.x.values, gdf_utm.geometry.y.values])


def _segment_centroids_utm(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Gibt UTM32N-Zentroiden der Segment-Geometrien zurück.

    Args:
        gdf: GeoDataFrame mit LineString-Geometrien.

    Returns:
        (N, 2) float64-Array [x, y] in EPSG:25832.
    """
    gdf_utm = gdf.to_crs(UTM32N)
    centroids = gdf_utm.geometry.centroid
    return np.column_stack([centroids.x.values, centroids.y.values])


def select_kandidaten(
    pois_path: Path,
    transit_stops_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Filtert und dedupliziert Kandidatenstandorte aus POI-Daten.

    Kriterien:
    - Amenity: school, kindergarten, community_centre, social_centre, etc.
    - ÖPNV-Nähe: maximale Luftlinie von TRANSIT_RADIUS_M zu einer Haltestelle
    - Deduplizierung: Kandidaten innerhalb DEDUP_RADIUS_M werden zusammengeführt

    Args:
        pois_path: Pfad zu `pois.geojson`.
        transit_stops_gdf: GeoDataFrame mit ÖPNV-Haltestellen (Point).

    Returns:
        GeoDataFrame mit Spalten:
        - osm_id, name, amenity, leisure, standort_typ
        Geometrie: Point, EPSG:4326.

    Raises:
        FileNotFoundError: Wenn pois.geojson nicht existiert.
    """
    if not pois_path.exists():
        raise FileNotFoundError(f"pois.geojson nicht gefunden: {pois_path}")

    logger.info("Lade POIs aus %s", pois_path.name)
    pois = gpd.read_file(pois_path)
    if pois.crs is None:
        pois = pois.set_crs(WGS84)
    else:
        pois = pois.to_crs(WGS84)

    # ÖPNV-Haltestellen aus POIs extrahieren, falls nicht extern übergeben
    if len(transit_stops_gdf) == 0:
        logger.warning("Leerer Transit-GDF übergeben — ÖPNV-Filter deaktiviert")
    else:
        transit_stops_gdf = transit_stops_gdf.to_crs(WGS84)

    # Kandidaten filtern
    amenity_mask = pois["amenity"].isin(_KANDIDATEN_AMENITY)
    leisure_mask = pois["leisure"].isin(_KANDIDATEN_LEISURE)
    kandidaten = pois[amenity_mask | leisure_mask].copy()
    logger.info("  %d Kandidaten nach Amenity-Filter", len(kandidaten))

    if len(kandidaten) == 0:
        logger.warning("Keine Kandidatenstandorte gefunden!")
        return gpd.GeoDataFrame(columns=["osm_id", "name", "amenity", "standort_typ", "geometry"],
                                crs=WGS84)

    # ÖPNV-Nähe-Filter
    if len(transit_stops_gdf) > 0:
        kandidaten = _filter_transit_naehe(kandidaten, transit_stops_gdf, TRANSIT_RADIUS_M)
        logger.info("  %d Kandidaten nach ÖPNV-Filter (≤%.0f m)", len(kandidaten), TRANSIT_RADIUS_M)

    if len(kandidaten) == 0:
        logger.warning("Keine Kandidaten nach ÖPNV-Filter — lockere den Radius")
        return gpd.GeoDataFrame(columns=["osm_id", "name", "amenity", "standort_typ", "geometry"],
                                crs=WGS84)

    # Deduplizierung
    kandidaten = _dedupliziere(kandidaten, DEDUP_RADIUS_M)
    logger.info("  %d Kandidaten nach Deduplizierung (≤%.0f m)", len(kandidaten), DEDUP_RADIUS_M)

    # Standort-Typ zuweisen
    kandidaten["standort_typ"] = kandidaten.apply(_standort_typ, axis=1)

    return kandidaten[["osm_id", "name", "amenity", "leisure", "standort_typ", "geometry"]].copy()


def _filter_transit_naehe(
    kandidaten: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    radius_m: float,
) -> gpd.GeoDataFrame:
    """Filtert Kandidaten auf maximale Luftlinien-Distanz zu ÖPNV-Haltestelle.

    Args:
        kandidaten: Kandidaten-GeoDataFrame (Point, WGS84).
        stops: Haltestellen-GeoDataFrame (Point, WGS84).
        radius_m: Maximale Luftlinie in Metern.

    Returns:
        Gefilterter Kandidaten-GeoDataFrame.
    """
    kand_coords = _coords_utm(kandidaten)
    stop_coords = _coords_utm(stops)

    dist = cdist(kand_coords, stop_coords, metric="euclidean")
    min_dist = dist.min(axis=1)

    maske = min_dist <= radius_m
    return kandidaten[maske].copy()


def _dedupliziere(
    kandidaten: gpd.GeoDataFrame,
    radius_m: float,
) -> gpd.GeoDataFrame:
    """Entfernt Kandidaten, die zu nahe beieinander liegen (greedy).

    Iteriert durch Kandidaten (nach osm_id sortiert) und verwirft alle
    folgenden Kandidaten innerhalb des Radius.

    Args:
        kandidaten: Kandidaten-GeoDataFrame.
        radius_m: Mindestabstand in Metern.

    Returns:
        Deduplizierter GeoDataFrame.
    """
    if len(kandidaten) <= 1:
        return kandidaten

    coords = _coords_utm(kandidaten)
    behalten = np.ones(len(kandidaten), dtype=bool)

    for i in range(len(kandidaten)):
        if not behalten[i]:
            continue
        for j in range(i + 1, len(kandidaten)):
            if not behalten[j]:
                continue
            dist = np.linalg.norm(coords[i] - coords[j])
            if dist <= radius_m:
                behalten[j] = False

    return kandidaten[behalten].copy()


def _standort_typ(row: pd.Series) -> str:
    """Bestimmt den Standort-Typ für das Kostenmodell.

    Args:
        row: POI-Zeile.

    Returns:
        'oeffentlich' oder 'privat'.
    """
    amenity = str(row.get("amenity", "")).lower()
    if amenity in ("school", "kindergarten", "community_centre", "townhall", "library"):
        return "oeffentlich"
    return "privat"


def solve_mclp(
    bedarf_gdf: gpd.GeoDataFrame,
    kandidaten_gdf: gpd.GeoDataFrame,
    bestand_gdf: gpd.GeoDataFrame,
    n_neue: int,
    radius_m: float = 800.0,
    walking_factor: float = 1.4,
) -> gpd.GeoDataFrame:
    """Löst das Maximal Covering Location Problem (MCLP) mit PuLP.

    Maximiert den abgedeckten unversorgten Bedarf bei n_neue neuen Standorten.
    Bestehende Einrichtungen werden als fixe Abdeckung berücksichtigt.

    Mathematisches Modell:
        max  Σ_j d_j * z_j
        s.t. Σ_i x_i <= n_neue
             z_j <= Σ_{i in N_j} x_i + abgedeckt_durch_bestand_j  ∀j
             x_i, z_j ∈ {0, 1}

    Args:
        bedarf_gdf: Straßenabschnitte mit `bedarf_unversorgt` (aus demand.py).
        kandidaten_gdf: Kandidatenstandorte (Point).
        bestand_gdf: Bestehende Einrichtungen (Point).
        n_neue: Anzahl neue Standorte.
        radius_m: Nominaler Wirkungsradius in Meter (Gehweg).
        walking_factor: Faktor Luftlinie → Gehweg.

    Returns:
        GeoDataFrame der empfohlenen Standorte (n_neue Zeilen) mit Spalten:
        - alle Kandidaten-Spalten
        - modell: "mclp"
        Geometrie: Point, EPSG:4326.
    """
    if len(kandidaten_gdf) == 0:
        logger.warning("Keine Kandidaten — MCLP gibt leeres Ergebnis zurück")
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    # Nur Segmente mit positivem Bedarf
    aktive = bedarf_gdf[bedarf_gdf["bedarf_unversorgt"] > 0].copy()
    if len(aktive) == 0:
        logger.warning("Kein unversorgter Bedarf — alle Gebiete bereits abgedeckt")
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    effektiver_radius = radius_m / walking_factor

    seg_coords = _segment_centroids_utm(aktive)   # (N, 2)
    kand_coords = _coords_utm(kandidaten_gdf)     # (M, 2)

    # Distanzmatrix Segmente × Kandidaten
    dist_sk = cdist(seg_coords, kand_coords, metric="euclidean")  # (N, M)

    # Abdeckungs-Matrix: N_j[j] = {i | dist(j,i) <= effektiver_radius}
    abdeckt = dist_sk <= effektiver_radius  # (N, M) bool

    # Segmente, die bereits durch Bestand abgedeckt sind
    if len(bestand_gdf) > 0:
        bestand_coords = _coords_utm(bestand_gdf)
        dist_sb = cdist(seg_coords, bestand_coords, metric="euclidean")  # (N, K)
        bereits_abgedeckt = (dist_sb <= effektiver_radius).any(axis=1)  # (N,)
    else:
        bereits_abgedeckt = np.zeros(len(aktive), dtype=bool)

    N = len(aktive)
    M = len(kandidaten_gdf)
    bedarf_arr = aktive["bedarf_unversorgt"].values

    # Segmente mit 0 Kandidaten in Reichweite können ohnehin nicht abgedeckt werden
    erreichbar = abdeckt.any(axis=1) | bereits_abgedeckt
    logger.info(
        "MCLP: N=%d Segmente (mit Bedarf), M=%d Kandidaten, n_neue=%d, "
        "erreichbar=%.1f%%",
        N, M, n_neue, 100.0 * erreichbar.mean(),
    )

    # PuLP-Modell
    prob = pulp.LpProblem("MCLP", pulp.LpMaximize)

    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(M)]
    z = [pulp.LpVariable(f"z_{j}", cat="Binary") for j in range(N)]

    # Zielfunktion: maximiere abgedeckten Bedarf
    prob += pulp.lpSum(bedarf_arr[j] * z[j] for j in range(N))

    # Budget-Constraint
    prob += pulp.lpSum(x) <= n_neue

    # Abdeckungs-Constraints
    for j in range(N):
        if bereits_abgedeckt[j]:
            # Bereits durch Bestand abgedeckt — z_j kann immer 1 sein
            prob += z[j] <= 1
        else:
            nachbarn = [i for i in range(M) if abdeckt[j, i]]
            if nachbarn:
                prob += z[j] <= pulp.lpSum(x[i] for i in nachbarn)
            else:
                prob += z[j] == 0  # Nicht erreichbar

    solver = _get_solver()
    status = prob.solve(solver)

    if pulp.LpStatus[prob.status] not in ("Optimal", "Not Solved"):
        logger.warning("MCLP Status: %s", pulp.LpStatus[prob.status])

    # Ausgewählte Kandidaten extrahieren
    ausgewaehlt = [i for i in range(M) if pulp.value(x[i]) and pulp.value(x[i]) > 0.5]
    logger.info(
        "MCLP gelöst: Status=%s, ausgewählt=%d/%d, abgedeckter Bedarf=%.0f",
        pulp.LpStatus[prob.status],
        len(ausgewaehlt),
        n_neue,
        pulp.value(prob.objective) or 0,
    )

    if not ausgewaehlt:
        logger.warning("MCLP wählte keine Standorte aus")
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    result = kandidaten_gdf.iloc[ausgewaehlt].copy()
    result["modell"] = "mclp"
    result = result.to_crs(WGS84)
    return result


def solve_p_median(
    bedarf_gdf: gpd.GeoDataFrame,
    kandidaten_gdf: gpd.GeoDataFrame,
    bestand_gdf: gpd.GeoDataFrame,
    n_neue: int,
    walking_factor: float = 1.4,
) -> gpd.GeoDataFrame:
    """Löst das p-Median-Problem mit einer Greedy-Heuristik.

    Iterativ wird derjenige Kandidat gewählt, der die bedarfsgewichtete
    Gesamtdistanz aller Segmente zu ihrem nächsten Standort am stärksten
    reduziert. Bestehende Einrichtungen gelten als fixe Standorte.

    Args:
        bedarf_gdf: Straßenabschnitte mit `bedarf_unversorgt`.
        kandidaten_gdf: Kandidatenstandorte (Point).
        bestand_gdf: Bestehende Einrichtungen (Point).
        n_neue: Anzahl neue Standorte.
        walking_factor: Faktor Luftlinie → Gehweg (für Distanzumrechnung).

    Returns:
        GeoDataFrame der empfohlenen Standorte mit Spalte `modell="p_median"`.
    """
    if len(kandidaten_gdf) == 0:
        logger.warning("Keine Kandidaten — p-Median gibt leeres Ergebnis zurück")
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    aktive = bedarf_gdf[bedarf_gdf["bedarf_unversorgt"] > 0].copy()
    if len(aktive) == 0:
        logger.warning("Kein unversorgter Bedarf für p-Median")
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    seg_coords = _segment_centroids_utm(aktive)
    kand_coords = _coords_utm(kandidaten_gdf)
    bedarf_arr = aktive["bedarf_unversorgt"].values

    # Distanzmatrix Segmente × Kandidaten (Gehwegäquivalent)
    dist_sk = cdist(seg_coords, kand_coords, metric="euclidean") * walking_factor  # (N, M)

    # Mindestdistanz zum Bestand (fixe Standorte)
    if len(bestand_gdf) > 0:
        bestand_coords = _coords_utm(bestand_gdf)
        dist_sb = cdist(seg_coords, bestand_coords, metric="euclidean") * walking_factor
        min_dist_bestand = dist_sb.min(axis=1)  # (N,)
    else:
        min_dist_bestand = np.full(len(aktive), np.inf)

    # Aktuelle minimale Distanz pro Segment (nur Bestand)
    min_dist_aktuell = min_dist_bestand.copy()

    ausgewaehlt_idx: list[int] = []

    for iteration in range(min(n_neue, len(kandidaten_gdf))):
        # Berechne Gewinn durch jeden verbleibenden Kandidaten
        verbleibenend = [i for i in range(len(kandidaten_gdf)) if i not in ausgewaehlt_idx]

        bester_idx = -1
        bester_gewinn = -1.0

        for i in verbleibenend:
            neue_min_dist = np.minimum(min_dist_aktuell, dist_sk[:, i])
            gewinn = np.dot(bedarf_arr, min_dist_aktuell - neue_min_dist)
            if gewinn > bester_gewinn:
                bester_gewinn = gewinn
                bester_idx = i

        if bester_idx < 0:
            break

        ausgewaehlt_idx.append(bester_idx)
        min_dist_aktuell = np.minimum(min_dist_aktuell, dist_sk[:, bester_idx])
        logger.debug(
            "  p-Median Iteration %d: Kandidat %d, Gewinn=%.0f",
            iteration + 1,
            bester_idx,
            bester_gewinn,
        )

    logger.info("p-Median greedy: %d Standorte ausgewählt", len(ausgewaehlt_idx))

    if not ausgewaehlt_idx:
        return gpd.GeoDataFrame({"geometry": []}, crs=WGS84)

    result = kandidaten_gdf.iloc[ausgewaehlt_idx].copy()
    result["modell"] = "p_median"
    result = result.to_crs(WGS84)
    return result
