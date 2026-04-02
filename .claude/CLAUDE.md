# CLAUDE.md — Stuttgart Aufwachsindex / Sozialraum-Dashboard

## Projektübersicht

Dieses Projekt analysiert ~133 offene Datensätze der Stadt Stuttgart (opendata.stuttgart.de) und erstellt ein mobiles Dashboard für kommunale Entscheidungsträger. Ziel: Identifikation von Stadtgebieten, in denen Kinder und Jugendliche strukturell benachteiligt aufwachsen, um knappe soziale Ressourcen präventiv und gezielt einzusetzen.

**Kernprodukt:** Eine React-PWA (Progressive Web App), deutschsprachig, mobile-first, mit interaktiver Karte auf Straßenabschnittsebene.

**Zielgruppe:** Kommunale Entscheidungsträger (Sozialamt, Jugendamt, Gemeinderat).

**Lizenz aller Quelldaten:** CC BY 4.0 (Stadt Stuttgart).

---

## Architektur

```
stuttgart-sozialraum/
├── CLAUDE.md                    # Diese Datei
├── pyproject.toml               # uv/pip Projektdefinition
├── .env.example                 # Umgebungsvariablen-Template
├── data/
│   ├── raw/                     # Unveränderte CSV-Downloads von opendata.stuttgart.de
│   ├── catalog/                 # Automatisch generierter Datenkatalog (JSON)
│   ├── osm/                     # OpenStreetMap-Extrakte für Stuttgart
│   ├── zensus/                  # Zensus 2022 Gitterdaten (100m)
│   ├── processed/               # Bereinigte, normalisierte Datensätze
│   ├── disaggregated/           # Auf Straßenabschnitte disaggregierte Daten
│   └── indices/                 # Berechnete Indizes als GeoJSON/Parquet
├── src/
│   ├── catalog/                 # Phase 1: Datenkatalogisierung
│   │   ├── __init__.py
│   │   ├── scanner.py           # CSV-Dateien einlesen, Schema erkennen
│   │   ├── classifier.py        # Datensätze thematisch klassifizieren
│   │   ├── normalizer.py        # Spaltennamen, Bezirksnamen, Zeitformate vereinheitlichen
│   │   └── registry.py          # Zentrales Datensatz-Register (was existiert, welche Ebene, welcher Zeitraum)
│   ├── geo/                     # Phase 2: Geodaten-Pipeline
│   │   ├── __init__.py
│   │   ├── osm_extract.py       # Overpass-API: Stadtbezirke, Straßen, Gebäude, POIs
│   │   ├── street_splitter.py   # Straßen an Hauptkreuzungen aufteilen
│   │   ├── zensus_grid.py       # Zensus-Gitterdaten laden und auf Straßenabschnitte mappen
│   │   └── spatial_index.py     # R-Tree-Index für schnelle räumliche Zuordnung
│   ├── disagg/                  # Phase 3: Dasymetrische Disaggregation
│   │   ├── __init__.py
│   │   ├── dasymetric.py        # Kernaggregationslogik: Bezirk → Straßenabschnitt
│   │   ├── temporal.py          # Jährlich → monatliche Schätzung (wo sinnvoll)
│   │   ├── confidence.py        # Konfidenz-Flags und Unsicherheitsberechnung
│   │   └── validation.py        # Konsistenzprüfungen (Summen, Grenzen)
│   ├── index/                   # Phase 4: Index-Berechnung
│   │   ├── __init__.py
│   │   ├── aufwachsindex.py     # Haupt-Composite-Index "Aufwachsbedingungen"
│   │   ├── dimensions.py        # Teildimensionen (Bildung, Gesundheit, Sicherheit, ...)
│   │   ├── precarity.py         # Ökonomische Prekaritätsindikatoren
│   │   ├── explorer.py          # Explorative Analyse: Korrelationen, Cluster, Anomalien
│   │   └── weighting.py         # Gewichtungsmethoden (PCA, AHP, equal-weight)
│   ├── placement/               # Phase 6: Sozialarbeiter-Standortoptimierung
│   │   ├── __init__.py
│   │   ├── existing.py          # Bestehende Sozialeinrichtungen aus OSM laden
│   │   ├── demand.py            # Bedarfsmodell aus Aufwachsindex ableiten
│   │   ├── optimizer.py         # Facility Location Problem (p-median / MCLP)
│   │   ├── impact.py            # Wirkungsradius und Reichweite pro Standort
│   │   ├── cost_model.py        # Kostenmodell (Personal, Miete, Ausstattung)
│   │   └── scenarios.py         # Szenarien: n=1,2,5,10 neue Stellen, Budget-Limits
│   ├── dashboard/               # Phase 5: React-PWA
│   │   ├── public/
│   │   │   ├── manifest.json
│   │   │   └── index.html
│   │   ├── src/
│   │   │   ├── App.jsx
│   │   │   ├── components/
│   │   │   │   ├── Map.jsx          # Leaflet/deck.gl Kartenansicht
│   │   │   │   ├── IndexPanel.jsx   # Indexübersicht + Dimensionen
│   │   │   │   ├── StreetDetail.jsx # Detail-Ansicht pro Straßenabschnitt
│   │   │   │   ├── CompareView.jsx  # Bezirke/Straßen vergleichen
│   │   │   │   ├── TimeSlider.jsx   # Zeitliche Entwicklung
│   │   │   │   ├── FilterBar.jsx    # Dimensionsfilter
│   │   │   │   ├── PlacementMap.jsx # Standortoptimierung: bestehende + empfohlene Standorte
│   │   │   │   ├── ScenarioPanel.jsx# Szenarien-Vergleich (Budget, Anzahl Stellen)
│   │   │   │   └── ImpactRing.jsx   # Wirkungsradius-Visualisierung auf Karte
│   │   │   ├── hooks/
│   │   │   ├── utils/
│   │   │   └── data/                # Vorberechnete JSON/GeoJSON-Tiles
│   │   ├── package.json
│   │   └── vite.config.js
│   └── api/                     # Optional: FastAPI Backend für dynamische Abfragen
│       ├── __init__.py
│       ├── main.py
│       └── routes/
├── agents/                      # Agent-Definitionen für Claude Code Subagents
│   ├── catalog_agent.md
│   ├── geo_agent.md
│   ├── disagg_agent.md
│   ├── index_agent.md
│   ├── explorer_agent.md
│   ├── placement_agent.md
│   └── dashboard_agent.md
├── notebooks/                   # Explorative Analyse, nicht produktiv
│   └── exploration.ipynb
└── tests/
    ├── test_catalog.py
    ├── test_geo.py
    ├── test_disagg.py
    ├── test_index.py
    ├── test_placement.py
    └── conftest.py
```

---

## Phasen und Abhängigkeiten

```
Phase 1 (Katalog)  ──→  Phase 2 (Geo)  ──→  Phase 3 (Disaggregation)  ──→  Phase 4 (Indizes)  ──→  Phase 5 (Dashboard)
                                                                               ↑                        ↑
                                                                    Phase 4b (Explorer)          Phase 6 (Placement)
                                                                    kann parallel laufen          braucht Phase 2 + 4
```

### Phase 1: Datenkatalogisierung

**Ziel:** Alle ~114 CSV-Dateien aus `data/raw/` automatisch einlesen, Schemata erkennen, thematisch klassifizieren, und in ein maschinenlesbares Register überführen.

**Eingabe:** CSV-Dateien in `data/raw/` (direkte Downloads von opendata.stuttgart.de), nach deutschem CSV Standard.

**Ausgabe:** `data/catalog/registry.json` mit folgendem Schema pro Datensatz:

```json
{
  "id": "sozialgeldempfaenger-sgb-ii",
  "datei": "sozialgeldempfaenger_sgb_ii.csv",
  "titel": "Sozialgeldempfänger (SGB II)",
  "thema": "soziales",
  "dimensionen": ["aufwachs_ökonomie"],
  "raeumliche_ebene": "stadtbezirk",
  "zeitliche_ebene": "jaehrlich",
  "zeitraum": [2005, 2023],
  "spalten": {
    "bezirk": "Stadtbezirk",
    "jahr": "Jahr",
    "werte": ["Anzahl", "je_1000_EW"]
  },
  "einheit": "Anzahl und Rate",
  "qualitaet": {
    "luecken_prozent": 2.1,
    "bemerkungen": "Fehlende Werte 2020 wegen Corona-Umstellung"
  }
}
```

**Thematische Klassifikation** — ordne jeden Datensatz einer oder mehreren Dimensionen zu:

| Dimension | Beispiel-Datensätze |
|---|---|
| `bildung` | Schulen, Schüler, Schulabgänge, Grundschulübergang |
| `gesundheit` | Ärztliche Versorgung, Krankenhäuser, Pflegebedürftige |
| `sicherheit` | Straftaten, Tatverdächtige, Straßenkriminalität, Unfälle |
| `mobilitaet` | SSB-Fahrgäste, Verkehrsmittelwahl, GTFS |
| `wohnen` | Wohngebäude, Wohnfläche, Eigentümerquote, geförderte Wohnungen |
| `wirtschaft` | Beschäftigte, Unternehmen, Existenzgründungen |
| `umwelt` | Luftqualität, Lärmbelastung, Treibhausgase, Flächennutzung |
| `soziales` | Sozialgeldempfänger, Bevölkerungsentwicklung, Ausländer |
| `kultur_freizeit` | Schwimmbäder, Theater, Stadtbücherei |
| `demografie` | Einwohner, Wohndauer, Binnenumzüge |

**Nicht alle Datensätze sind relevant für den Aufwachsindex.** Datensätze wie Wahlergebnisse oder OB-Wahlen sind Kontextdaten, nicht Index-Inputs. Das Register markiert: `"index_relevant": true/false`.

**Stuttgarter Bezirksstruktur:** Stuttgart hat 23 Stadtbezirke, 152 Stadtteile. Die meisten Datensätze liegen auf Stadtbezirk-Ebene vor. Dies ist die native Auflösung — alles darunter ist geschätzt.

**Normalisierung:**
- Bezirksnamen einheitlich auf offizielle Schreibweise mappen (z.B. "S-Mitte" → "Stuttgart-Mitte", "Bad Cannstatt" etc.)
- Jahresspalten als Integer, nicht String
- Fehlwerte explizit als `null`, nicht als 0 oder leere Strings
- Encoding: UTF-8 (Umlaute prüfen)

### Phase 2: Geodaten-Pipeline

**Ziel:** Geographische Grundlage für die Disaggregation und das Dashboard schaffen.

**Datenquellen:**
1. **OpenStreetMap** via Overpass API:
   - Stadtbezirk-Grenzen (`admin_level=9` für Stuttgart)
   - Stadtteil-Grenzen (`admin_level=10`)
   - Straßennetz (highway=primary/secondary/tertiary/residential)
   - Gebäude-Footprints (building=*)
   - POIs: Schulen, Kitas, Ärzte, Spielplätze, Haltestellen, Sportanlagen
2. **Zensus 2022** 100m-Gitterdaten (Bevölkerungszahl pro Rasterzelle)
   - Quelle: https://www.zensus2022.de/DE/Ergebnisse-des-Zensus/_inhalt.html
   - Falls nicht direkt verfügbar: Zensus 2011 Gitterdaten als Fallback
3. **GTFS-Daten** (bereits auf dem Portal als Datensatz vorhanden)

**Straßen-Splitting-Algorithmus (`street_splitter.py`):**

```
Für jede Straße in Stuttgart:
  1. Lade den LineString aus OSM
  2. Identifiziere "große Kreuzungen" = Schnittpunkte mit primary/secondary roads
  3. Splitte den LineString an diesen Punkten
  4. Jeder resultierende Abschnitt bekommt eine ID: {street_name}_{bezirk}_{segment_nr}
  5. Weise jedem Abschnitt zu: Stadtbezirk, Stadtteil (via spatial join)
  6. Berechne: Länge, Anzahl Gebäude in 50m-Puffer, Bevölkerung (aus Zensus-Grid)
```

**Kreuzungs-Definition:** Eine Kreuzung ist "groß" wenn die kreuzende Straße mindestens `secondary` ist ODER wenn der kreuzende Knoten 3+ Straßen mit `highway ∈ {primary, secondary, tertiary}` verbindet. Reine Wohnstraßen-Kreuzungen splitten NICHT.

**Ausgabe:**
- `data/osm/bezirke.geojson` — Stadtbezirk-Polygone
- `data/osm/stadtteile.geojson` — Stadtteil-Polygone
- `data/osm/strassenabschnitte.geojson` — Gesplittete Straßenabschnitte mit Attributen
- `data/osm/gebaeude.parquet` — Gebäude-Footprints (zu groß für GeoJSON)
- `data/osm/pois.geojson` — Points of Interest nach Kategorie
- `data/zensus/population_grid.parquet` — 100m Raster mit Einwohnerzahl

### Phase 3: Dasymetrische Disaggregation

**Ziel:** Bezirkslevel-Daten auf Straßenabschnitte verteilen. Jährliche Daten wo sinnvoll auf Monate schätzen.

**KRITISCHE REGEL: Jeder disaggregierte Wert MUSS ein Konfidenz-Flag tragen.**

```python
class DisaggValue:
    """Ein disaggregierter Datenpunkt."""
    wert: float                    # Der geschätzte Wert
    konfidenz: Literal["gemessen", "geschaetzt_hoch", "geschaetzt_mittel", "geschaetzt_niedrig"]
    quelldatensatz: str            # ID aus dem Katalog
    quellwert_bezirk: float        # Originalwert auf Bezirksebene
    methode: str                   # z.B. "dasymetric_population", "dasymetric_building"
    unsicherheit_relativ: float    # Geschätzte relative Unsicherheit (0.0 - 1.0)
```

**Räumliche Disaggregation (Bezirk → Straßenabschnitt):**

Die Methode hängt von der Art der Daten ab:

| Datentyp | Hilfsgewicht | Beispiel |
|---|---|---|
| Bevölkerungsbezogen (Einwohner, Kinder, Ausländer) | Zensus-Grid Bevölkerung im Straßen-Puffer | Sozialgeldempfänger |
| Infrastruktur (Schulen, Ärzte) | POI-Standorte aus OSM, Erreichbarkeitsradius | Ärztliche Versorgung |
| Flächen (Grünfläche, Versiegelung) | Flächennutzung aus OSM | Flächennutzung |
| Wirtschaft (Unternehmen, Beschäftigte) | Gewerbegebäude aus OSM | Unternehmen |
| Infrastruktur-Dichte (ÖPNV) | Haltestellenabstand | SSB Fahrgäste |

**Grundformel für bevölkerungsgewichtete Disaggregation:**

```
wert_strassenabschnitt = wert_bezirk * (bevoelkerung_abschnitt / bevoelkerung_bezirk)
```

Bei Infrastrukturdaten stattdessen inverse Distanz zu nächstem POI als Gewicht.

**Temporale Disaggregation (jährlich → monatlich):**

NUR anwenden wo es sinnvoll ist:
- **Ja:** Bevölkerungszahlen (lineare Interpolation zwischen Jahreswerten), Verkehr (saisonale Schablone), Schwimmbad-Besucher
- **Nein:** Eigentümerquote, Schulabschlüsse (diese bleiben jährlich)
- Methode: Entweder lineare Interpolation oder Anwendung einer saisonalen Template-Kurve (z.B. aus GTFS-Monatsschwankungen)
- JEDER monatliche Wert bekommt `konfidenz: "geschaetzt_mittel"` oder niedriger

**Validierung:**
- Summe aller Straßenabschnitte eines Bezirks = Bezirkswert (± 0.1% Rundungsfehler)
- Keine negativen Werte wo physikalisch unmöglich
- Summe aller Monate ≈ Jahreswert (± saisonale Korrektur)

### Phase 4: Index-Berechnung

**Der Aufwachsindex** ist ein zusammengesetzter Score (0–100, höher = schwierigere Aufwachsbedingungen) aus folgenden Dimensionen:

| Dimension | Gewicht (Standard) | Indikatoren |
|---|---|---|
| Bildung | 20% | Grundschulübergangsquote Gymnasium, Schulabgänger ohne Abschluss, Schüler-Lehrer-Verhältnis |
| Ökonomische Prekarität | 25% | SGB-II-Quote, Beschäftigungsquote, Einkommen (falls verfügbar), Eigentümerquote (invers) |
| Gesundheit & Versorgung | 15% | Ärztedichte, Entfernung Kinderarzt/Krankenhaus, Pflegequote |
| Sicherheit | 15% | Straßenkriminalität, Gewaltkriminalität, Unfälle |
| Wohnumfeld | 10% | Wohnfläche/Person, Lärmbelastung, Luftqualität, Grünfläche |
| Mobilität & Teilhabe | 10% | ÖPNV-Erreichbarkeit, Entfernung zu Spielplätzen/Sport/Kultur |
| Soziale Kohäsion | 5% | Binnenumzugsrate (Instabilität), Wahlbeteiligung |

**Normalisierung:** Jeder Indikator wird per Min-Max auf [0, 1] normalisiert innerhalb Stuttgarts. Richtung: 1 = schlecht.

**Gewichtung:** Standardmäßig wie oben. Das Dashboard erlaubt dem Nutzer, Gewichte interaktiv zu ändern. Zusätzlich PCA-basierte Gewichtung als Alternative berechnen.

**Output:** `data/indices/aufwachsindex.geojson` — jeder Straßenabschnitt mit:
- `aufwachsindex_gesamt`: 0–100
- `dim_bildung`: 0–100
- `dim_oekonomie`: 0–100
- ... (alle Dimensionen)
- `konfidenz_gesamt`: gewichteter Durchschnitt der Konfidenz-Flags
- `n_indikatoren_verfuegbar`: Wie viele der theoretischen Indikatoren Daten haben

### Phase 4b: Explorative Analyse (Explorer-Agent)

Der Explorer-Agent arbeitet parallel und sucht nach Mustern, die über den vordefinierten Index hinausgehen:

**Aufgaben:**
1. **Korrelationsanalyse** zwischen allen verfügbaren Datensätzen — welche Indikatoren hängen unerwartet zusammen?
2. **Cluster-Analyse** (k-means, DBSCAN) auf Bezirksebene — gibt es Bezirks-Typen die der Index nicht abbildet?
3. **Ökonomische Prekaritätsindikatoren:**
   - Vergleich: SGB-II-Quote vs. Beschäftigungsquote — hohe Beschäftigung + hohe SGB-II-Quote → Working Poor
   - Vergleich: Existenzgründungen vs. Sozialgeldempfänger — Korrelation könnte auf Scheinselbständigkeit hindeuten
   - Vergleich: Eigentümerquote vs. Wohnfläche/Person — kleine Eigentumswohnungen = andere Demografie als Mietviertel
4. **Zeitreihen-Anomalien:** Wo verschlechtern sich Indikatoren schneller als der Stadtdurchschnitt?
5. **Räumliche Autokorrelation** (Moran's I): Gibt es Cluster benachteiligter Straßenabschnitte die über Bezirksgrenzen hinausgehen?
6. **Unerwartete Muster:** z.B. hohe Arzt-Dichte aber schlechte Gesundheitsindikatoren → Versorgung existiert, wird aber nicht genutzt

**Output:** `data/indices/explorer_report.json` mit gefundenen Mustern, Visualisierungen, und Empfehlungen für zusätzliche Index-Dimensionen.

### Phase 5: Dashboard (React PWA)

**Design-Prinzipien:**
- **Mobile-first.** Alles muss auf einem 375px-Bildschirm funktionieren.
- **Karte zentral.** Die Karte nimmt 70%+ des Viewports ein. Panels sind Overlays/Sheets.
- **Deutsche Sprache.** Alle Labels, Tooltips, Erklärungen auf Deutsch. Fachbegriffe mit Tooltip-Erklärung.
- **Farbskala:** Divergierend (Grün → Gelb → Rot), farbenblind-sicher. Grün = gute Aufwachsbedingungen.
- **Kein Dark-Mode.** Kommunale Entscheidungsträger erwarten hellen, sachlichen Look.
- **Datenherkunft transparent.** Jeder Wert zeigt per Tap: Quelldatensatz, Konfidenz, Methode.
- **Export:** PDF-Bericht pro Bezirk/Straßenabschnitt für Gremiensitzungen.

**Kartenansichten:**
1. **Choropleth Aufwachsindex** — Straßenabschnitte eingefärbt nach Gesamtindex
2. **Einzeldimension** — Umschaltbar auf jede der 7 Dimensionen
3. **Vergleichsmodus** — 2 Bezirke/Straßen nebeneinander
4. **Zeitverlauf** — Slider über Jahre, Animation der Veränderung
5. **POI-Overlay** — Schulen, Kitas, Ärzte, Spielplätze, Haltestellen als Marker

**Mobile Interaktion:**
- Tippe auf Straßenabschnitt → Bottom-Sheet mit Schnellübersicht
- Wische hoch → volle Detailansicht mit Radar-Chart der Dimensionen
- Pinch-Zoom auf Karte
- Suchleiste oben: Straße oder Bezirk eingeben

**Technologie:**
- React 18+ mit Vite
- Leaflet + react-leaflet für Basiskarte (OpenStreetMap-Tiles)
- deck.gl für performante GeoJSON-Overlay bei 10.000+ Straßenabschnitten
- Zustand oder Context für State Management (kein Redux — Overkill hier)
- Tailwind CSS für Styling (mobile-first Utilities)
- PWA via Workbox (Offline-Karte für Vor-Ort-Begehungen)
- Vorberechnete Daten als statische JSON/GeoJSON — kein Backend nötig für MVP
- Optional: FastAPI Backend für dynamische Abfragen in Phase 2

**Performance-Budget:**
- First Contentful Paint < 2s auf 4G
- Karteninteraktion 60fps
- GeoJSON-Dateien als Vector Tiles oder vereinfacht für Zoom-Stufen

### Phase 6: Sozialarbeiter-Standortoptimierung

**Ziel:** Optimale Standorte für neue Sozialarbeiterstellen identifizieren, Wirkung und Kosten modellieren, bestehende Infrastruktur berücksichtigen.

**Eingabe:**
- `data/indices/aufwachsindex.geojson` (Bedarf pro Straßenabschnitt)
- `data/osm/sozialeinrichtungen.geojson` (bestehende Standorte, siehe Overpass-Query unten)
- `data/osm/strassenabschnitte.geojson` (Straßennetz für Erreichbarkeit)
- Kostenparameter (konfigurierbar)

**Ausgabe:**
- `data/placement/bestand.geojson` — Bestehende Sozialeinrichtungen mit Typ und Kapazität
- `data/placement/szenarien/*.geojson` — Pro Szenario: empfohlene Standorte + Wirkungsradien
- `data/placement/kosten_nutzen.json` — Kostenmodell pro Szenario

#### 6a: Bestehende Sozialeinrichtungen erfassen (`existing.py`)

Aus OSM extrahieren (siehe Overpass-Query unten):
- Jugendhäuser, Jugendtreffs
- Beratungsstellen (Schuldnerberatung, Familienberatung, Suchtberatung)
- Soziale Einrichtungen (Mehrgenerationenhäuser, Bürgerzentren)
- Schulsozialarbeit-Standorte (aus Schul-POIs + ggf. manueller Ergänzung)
- Mobile Jugendarbeit (Standorte aus kommunalen Quellen, falls verfügbar)

Für jeden Bestandsstandort erfassen:
```json
{
  "id": "sozial_001",
  "name": "Jugendhaus Mitte",
  "typ": "jugendhaus",
  "lat": 48.775,
  "lon": 9.178,
  "bezirk": "Stuttgart-Mitte",
  "kapazitaet_geschaetzt": null,
  "quelle": "osm",
  "osm_id": "node/123456"
}
```

#### 6b: Bedarfsmodell (`demand.py`)

Der Bedarf pro Straßenabschnitt leitet sich aus dem Aufwachsindex ab, gewichtet mit der Kinderzahl (0–17 Jahre):

```
bedarf_abschnitt = aufwachsindex_abschnitt * kinder_abschnitt
```

Zusätzlich: Bereits versorgte Gebiete (im Wirkungsradius einer bestehenden Einrichtung) haben reduzierten Bedarf. Reduktion hängt von Entfernung ab (linearer Abfall über Gehminuten).

**Unversorgter Bedarf:**
```
unversorgter_bedarf = bedarf - sum(versorgung_durch_bestehende_einrichtungen)
```

#### 6c: Standortoptimierung (`optimizer.py`)

Zwei Optimierungsmodelle:

**Modell 1: Maximal Covering Location Problem (MCLP)**
- Gegeben: Budget für n neue Stellen
- Gesucht: n Standorte die den maximalen unversorgten Bedarf abdecken
- Wirkungsradius: konfigurierbar (Standard: 800m Gehweg = ~10 Min)
- Lösung via PuLP (Open-Source LP/MILP Solver) oder scipy.optimize

**Modell 2: p-Median**
- Minimiere die bedarfsgewichtete Gesamtdistanz aller Straßenabschnitte zum nächsten Sozialarbeiter-Standort
- Berücksichtigt bestehende Einrichtungen als fixe Standorte

**Kandidatenstandorte:** Nicht jeder Punkt in Stuttgart ist ein sinnvoller Standort. Kandidaten sind:
- Bestehende öffentliche Gebäude (Schulen, Bürgerhäuser, Stadtteilbibliotheken) — geringere Mietkosten
- Leerstehende Gewerberäume (aus Bauabgänge-Datensatz + OSM `shop=vacant`)
- Haltestellennähe (< 300m zur nächsten ÖPNV-Haltestelle) — Erreichbarkeit
- Schwerpunkt: Im oder nahe am Bedarfsgebiet

#### 6d: Wirkungsradius und Reichweite (`impact.py`)

Jeder Standort (bestehend oder empfohlen) bekommt einen Wirkungsbereich:

```python
class StandortWirkung:
    standort_id: str
    position: Point                   # Standort-Koordinate
    wirkungsradius_m: int             # Gehweg-Meter, nicht Luftlinie
    erreichte_abschnitte: list[str]   # IDs der Straßenabschnitte im Radius
    erreichte_kinder: int             # Geschätzte Kinderzahl im Radius
    abgedeckter_bedarf: float         # Summe des abgedeckten Bedarfs
    kategorien: dict[str, float]      # Wirkung aufgeschlüsselt nach Dimension
```

**Wirkung nach Kategorie:** Der Wirkungsradius ist nicht für alle Dimensionen gleich:

| Kategorie | Effektiver Radius | Begründung |
|---|---|---|
| Bildung (Nachhilfe, Lernhilfe) | 500m / 7 Min Gehweg | Kinder kommen regelmäßig, Radius klein |
| Freizeitangebote, Sport | 800m / 10 Min | Jugendliche sind mobiler |
| Elternberatung, Familienarbeit | 1200m / 15 Min | Erwachsene kommen gezielt |
| Streetwork, aufsuchende Arbeit | 2000m / mobil | Sozialarbeiter geht zum Klient |
| Erreichbarkeit via ÖPNV | Isochronen-basiert | Falls Haltestelle in Standortnähe |

#### 6e: Kostenmodell (`cost_model.py`)

```python
class StandortKosten:
    personalkosten_jahr: float     # Vollzeitstelle Sozialarbeiter (TVöD S11b/S12)
    mietkosten_jahr: float         # Abhängig von Standorttyp (öffentlich vs. privat)
    sachkosten_jahr: float         # Ausstattung, Material, Fahrtkosten
    einmalkosten: float            # Einrichtung, IT, Erstausstattung
    gesamtkosten_jahr: float
    kosten_pro_erreichtes_kind: float  # = gesamtkosten / erreichte_kinder
```

**Referenzwerte (konfigurierbar in `.env`):**
- TVöD-SuE S11b Stufe 3: ~48.000 €/Jahr brutto + ~25% AG-Anteil ≈ 60.000 €
- TVöD-SuE S12 Stufe 3: ~52.000 €/Jahr brutto + AG ≈ 65.000 €
- Miete öffentliches Gebäude: 0–5.000 €/Jahr (Nutzungspauschale)
- Miete privater Raum: 8.000–15.000 €/Jahr (abhängig von Bezirk und Fläche)
- Sachkosten: 3.000–8.000 €/Jahr
- Einmalkosten: 5.000–15.000 €

#### 6f: Szenarien (`scenarios.py`)

Das Dashboard zeigt vorberechnete Szenarien:

| Szenario | Beschreibung |
|---|---|
| `baseline` | Nur bestehende Einrichtungen, keine neuen Stellen |
| `n1_optimal` | 1 neue Stelle am optimalen Standort |
| `n3_optimal` | 3 neue Stellen, optimal verteilt |
| `n5_optimal` | 5 neue Stellen |
| `n10_optimal` | 10 neue Stellen |
| `budget_100k` | Maximale Abdeckung mit 100.000 € Jahresbudget |
| `budget_300k` | Maximale Abdeckung mit 300.000 € |
| `budget_500k` | Maximale Abdeckung mit 500.000 € |
| `luecke_bildung` | Nur Dimension Bildung optimieren |
| `luecke_sicherheit` | Nur Dimension Sicherheit optimieren |

Jedes Szenario enthält:
- Empfohlene Standorte (Koordinaten, Adresse, Typ)
- Gesamtkosten pro Jahr
- Anzahl erreichter Kinder (gesamt + neu versorgt)
- Veränderung im mittleren unversorgten Bedarf (%)
- Aufschlüsselung nach Dimension

#### Dashboard-Integration (Phase 5 Erweiterung)

Neue Kartenansicht **"Standortplanung":**
- Bestehende Einrichtungen als blaue Marker
- Empfohlene neue Standorte als orange Marker (pulsierend)
- Wirkungsradien als halbtransparente Kreise/Isochronen
- Unversorgte Gebiete in Rot (Bedarf ohne Abdeckung)
- Szenario-Switcher oben: Dropdown oder Tabs
- Bottom-Sheet pro Standort: Kosten, erreichte Kinder, Dimensionen
- Vergleichsansicht: 2 Szenarien nebeneinander mit Delta

---

## Agent-Definitionen → VoltAgent Mapping

Jeder Projekt-Agent wird auf einen oder mehrere VoltAgent-Subagents gemappt. Die Zuordnung bestimmt, welcher Subagent bei `claude code` für welche Aufgabe aufgerufen wird.

### `catalog_agent` → `voltagent-data-ai:data-engineer` (sonnet)
- **Liest:** `data/raw/*.csv`
- **Schreibt:** `data/catalog/registry.json`, `data/processed/*.parquet`
- **Darf:** Dateien lesen, pandas benutzen, CKAN-API abfragen (https://opendata.stuttgart.de/api/3)
- **Darf nicht:** Daten verändern, Werte schätzen, Geodaten anfassen
- **Unterstützung:** `voltagent-lang:python-pro` für Implementierung, `voltagent-data-ai:data-analyst` (haiku) für schnelle Schema-Checks

### `geo_agent` → `voltagent-data-ai:data-engineer` (sonnet) + `voltagent-lang:python-pro` (sonnet)
- **Liest:** Overpass API, Zensus-Download, GTFS
- **Schreibt:** `data/osm/*`, `data/zensus/*`
- **Darf:** HTTP-Requests an Overpass API, OSM-Daten verarbeiten, geopandas/shapely nutzen
- **Darf nicht:** Katalog-Daten anfassen, Index berechnen
- **Caching:** Overpass-Antworten in `data/osm/.cache/` cachen — API nicht bei jedem Run abfragen

### `disagg_agent` → `voltagent-data-ai:data-scientist` (sonnet)
- **Liest:** `data/catalog/registry.json`, `data/processed/*`, `data/osm/*`, `data/zensus/*`
- **Schreibt:** `data/disaggregated/*`
- **Darf:** Dasymetrische Disaggregation durchführen
- **MUSS:** Konfidenz-Flags setzen, Validierungschecks ausführen
- **Darf nicht:** Rohdaten verändern, Index berechnen
- **Unterstützung:** `voltagent-data-ai:data-analyst` (haiku) für Schnellvalidierung

### `index_agent` → `voltagent-data-ai:data-scientist` (sonnet)
- **Liest:** `data/disaggregated/*`, `data/catalog/registry.json`
- **Schreibt:** `data/indices/aufwachsindex.geojson`, `data/indices/dimensionen/*.geojson`
- **Darf:** Normalisierung, Gewichtung, Aggregation
- **Darf nicht:** Quelldaten verändern, Dashboard-Code anfassen

### `explorer_agent` → `voltagent-research:data-researcher` (sonnet) + `voltagent-data-ai:data-scientist` (sonnet)
- **Liest:** Alles in `data/`
- **Schreibt:** `data/indices/explorer_report.json`, `notebooks/exploration.ipynb`
- **Darf:** Freie explorative Analyse, Hypothesen generieren, scipy/sklearn nutzen
- **MUSS:** Jede Erkenntnis mit statistischer Signifikanz untermauern
- **Darf nicht:** Den Aufwachsindex selbst verändern
- **Unterstützung:** `voltagent-research:research-analyst` für Literaturrecherche zu Methodik, `voltagent-biz:business-analyst` für kommunalpolitische Einordnung

### `placement_agent` → `voltagent-domains:quant-analyst` (opus) + `voltagent-data-ai:data-scientist` (sonnet)
- **Liest:** `data/indices/*`, `data/osm/*`, `data/placement/bestand.geojson`
- **Schreibt:** `data/placement/szenarien/*.geojson`, `data/placement/kosten_nutzen.json`
- **Darf:** Optimierungsmodelle lösen (PuLP/scipy), Kostenberechnungen, Netzwerkdistanzen
- **MUSS:** Jedes Szenario mit Kosten-Nutzen-Zusammenfassung ausgeben
- **Darf nicht:** Index-Daten oder Quelldaten verändern
- **Warum opus:** Das Facility-Location-Problem mit Mehrfach-Constraints (Budget, Erreichbarkeit, Dimensionsgewichte) erfordert die höchste Modellqualität für korrekte Formulierung
- **Unterstützung:** `voltagent-biz:business-analyst` (sonnet) für Kostenparameter-Plausibilisierung

### `dashboard_agent` → `voltagent-lang:react-specialist` (sonnet) + `voltagent-core-dev:ui-designer` (sonnet)
- **Liest:** `data/indices/*`, `data/osm/strassenabschnitte.geojson`, `data/placement/*`
- **Schreibt:** `src/dashboard/*`
- **Darf:** React-Komponenten schreiben, Tailwind nutzen
- **Darf nicht:** Python-Code anfassen, Daten transformieren
- **Unterstützung:** `voltagent-core-dev:frontend-developer` für Build-Konfiguration, `voltagent-biz:ux-researcher` für Nutzerführung auf Mobilgeräten

### Koordination und Qualitätssicherung

| Aufgabe | VoltAgent |
|---|---|
| Pipeline-Orchestrierung | `voltagent-meta:workflow-orchestrator` (opus) |
| Code-Reviews nach jeder Phase | `voltagent-qa-sec:code-reviewer` (opus) |
| Test-Erstellung | `voltagent-qa-sec:qa-expert` (sonnet) |
| Performance-Optimierung Dashboard | `voltagent-qa-sec:performance-engineer` (sonnet) |
| API-Design (falls FastAPI Backend) | `voltagent-core-dev:api-designer` (sonnet) + `voltagent-lang:fastapi-developer` (sonnet) |
| Datenschutz-Review | `voltagent-biz:legal-advisor` (sonnet) — prüft DSGVO-Konformität der Disaggregation |
| Dokumentation | `voltagent-biz:technical-writer` (haiku) |

### Agent-Aufruf-Konventionen

Bei `claude code` Subagent-Aufrufen:
```
# Beispiel: Katalog-Agent starten
@voltagent-data-ai:data-engineer Lies alle CSVs in data/raw/ ein und erstelle data/catalog/registry.json gemäß dem Schema in CLAUDE.md Phase 1.

# Beispiel: Placement-Agent Szenario berechnen
@voltagent-domains:quant-analyst Berechne Szenario n5_optimal: 5 neue Sozialarbeiter-Standorte, MCLP-Modell, 800m Gehwegradius. Input: data/indices/aufwachsindex.geojson + data/placement/bestand.geojson.

# Beispiel: Code-Review nach Phase 3
@voltagent-qa-sec:code-reviewer Review src/disagg/ — prüfe besonders ob Konfidenz-Flags korrekt gesetzt werden und ob Summen-Validierung implementiert ist.
```

---

## Coding-Standards

### Python
- **Formatter:** ruff format
- **Linter:** ruff check (config in pyproject.toml)
- **Type Hints:** Pflicht für alle Funktionen (Eingabe UND Ausgabe)
- **Docstrings:** Google-Style, auf Deutsch für öffentliche Funktionen
- **Datenformate:**
  - Intermediär: Parquet (schnell, typisiert, kompakt)
  - Geo-Output: GeoJSON für < 10MB, Parquet + separate Geo-Referenz für größere Dateien
  - Dashboard-Input: GeoJSON (Leaflet-kompatibel)
- **Logging:** `logging` Modul, nicht print(). Level: INFO für Pipeline-Fortschritt, DEBUG für Details
- **Tests:** pytest, mindestens ein Test pro Modul der die Kernfunktion abdeckt, möglichst anspruchsvoll geschrieben der alle erdenklichen edge-cases abdeckt und nur mit den vorhandenen Daten getestet wird
- **Dependencies:** In pyproject.toml, gepinnt mit uv.lock
- Keine `*`-Imports
- Kein Code in `__init__.py` außer Re-Exports

### JavaScript/React
- **Formatter:** Prettier
- **Linter:** ESLint mit React-Plugin
- **Komponenten:** Funktionale Komponenten mit Hooks, keine Klassen
- **Styling:** Tailwind CSS, keine inline-styles, keine CSS-Module
- **State:** Zustand für globalen State, useState für lokalen
- **Prop-Types:** TypeScript-artige JSDoc-Kommentare oder PropTypes
- **Dateien:** Eine Komponente pro Datei, PascalCase Dateinamen

### Git
- **Commits:** Konventionelle Commits (feat:, fix:, data:, docs:)
- **Branching:** main + feature-branches pro Phase
- `data/raw/` ist in `.gitignore` (zu groß, CC BY lizensiert → README verlinkt Quelle)
- `data/catalog/` und `data/indices/` werden committed (reproduzierbar, aber nützlich vorberechnet)

---

## Externe Abhängigkeiten

### Python
```
pandas >= 2.0
geopandas >= 0.14
shapely >= 2.0
pyproj
requests          # Overpass API, CKAN API
pyarrow           # Parquet I/O
scipy             # Statistik, Interpolation
scikit-learn      # Clustering, PCA
rtree             # Spatial Index
networkx          # Straßennetz-Graphen für Gehweg-Distanzen
PuLP              # MILP Solver für Standortoptimierung (MCLP, p-median)
folium            # Schnelle Kartenerstellung für Debugging
ruff              # Linter/Formatter
pytest
```

### JavaScript
```
react, react-dom
react-leaflet, leaflet
@deck.gl/core, @deck.gl/layers, @deck.gl/react
zustand
tailwindcss
vite
workbox (PWA)
recharts           # Für Balken/Radar-Charts im Detail-Panel
```

---

## CKAN-API Referenz

Die Datensätze können auch programmatisch abgefragt werden:

```bash
# Alle Datensätze auflisten
curl "https://opendata.stuttgart.de/api/3/action/package_list"

# Details zu einem Datensatz
curl "https://opendata.stuttgart.de/api/3/action/package_show?id=sozialgeldempfaenger-sgb-ii"

# Suche
curl "https://opendata.stuttgart.de/api/3/action/package_search?q=kriminalitaet"
```

Nutze die API in `catalog/scanner.py` um Metadaten automatisch anzureichern (Beschreibungen, Tags, Update-Frequenz).

---

## Datenqualität und Ehrlichkeit

**Zentrale Regel:** Das Dashboard darf NIEMALS den Eindruck erwecken, gemessene Daten zu zeigen, wo tatsächlich geschätzte Daten vorliegen.

- Jeder Straßenabschnitt zeigt ein Konfidenz-Indikator (z.B. Farbsättigung: hohe Konfidenz = satt, niedrige = blass)
- Tooltips zeigen immer: "Geschätzt auf Basis von [Quelle], Konfidenz: [mittel/niedrig]"
- Die native Bezirks-Ebene ist immer als alternative Ansicht verfügbar
- Ein "Methodik"-Button erklärt die Disaggregation verständlich
- PDF-Export enthält methodischen Anhang

---

## Overpass-API Queries (Referenz)

### Stadtbezirke
```
[out:json][timeout:60];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
rel(area.stuttgart)["admin_level"="9"];
out body;
>;
out skel qt;
```

### Straßennetz
```
[out:json][timeout:120];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
way(area.stuttgart)["highway"~"primary|secondary|tertiary|residential"];
out body;
>;
out skel qt;
```

### Gebäude
```
[out:json][timeout:300];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
way(area.stuttgart)["building"];
out body;
>;
out skel qt;
```

### POIs (Schulen, Kitas, Ärzte, etc.)
```
[out:json][timeout:60];
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
```

### Sozialeinrichtungen (Phase 6)
```
[out:json][timeout:60];
area["name"="Stuttgart"]["admin_level"="6"]->.stuttgart;
(
  // Soziale Einrichtungen allgemein
  nwr(area.stuttgart)["amenity"="social_facility"];
  nwr(area.stuttgart)["social_facility"];
  nwr(area.stuttgart)["amenity"="social_centre"];
  nwr(area.stuttgart)["amenity"="community_centre"];
  // Jugendeinrichtungen
  nwr(area.stuttgart)["amenity"="youth_centre"];
  nwr(area.stuttgart)["social_facility"="youth_centre"];
  nwr(area.stuttgart)["social_facility"="outreach"];
  // Beratungsstellen
  nwr(area.stuttgart)["office"="social_services"];
  nwr(area.stuttgart)["office"="counselling"];
  nwr(area.stuttgart)["social_facility"="counselling"];
  // Familienzentren, Mehrgenerationenhäuser
  nwr(area.stuttgart)["social_facility"="group_home"];
  nwr(area.stuttgart)["community_centre:for"="juvenile"];
  nwr(area.stuttgart)["community_centre:for"="family"];
);
out body;
>;
out skel qt;
```

**Hinweis:** OSM-Abdeckung für Sozialeinrichtungen ist unvollständig. Der `placement_agent` muss die OSM-Daten mit dem Stuttgarter Sozialatlas und ggf. manuellen Ergänzungen abgleichen. Das CLAUDE.md-Schema in Phase 6a erlaubt `"quelle": "manuell"` für Einträge die nicht aus OSM stammen.

---

## Hinweise für Agents

1. **Immer zuerst `data/catalog/registry.json` prüfen** bevor du einen Datensatz verwendest. Wenn er nicht im Register ist, muss der catalog_agent ihn erst aufnehmen.
2. **Kein Overpass-API-Aufruf ohne Cache-Check.** Die API hat Rate-Limits.
3. **Koordinatensystem:** EPSG:4326 (WGS84) für GeoJSON-Outputs. EPSG:25832 (UTM 32N) für Flächenberechnungen und Distanzen. Immer explizit angeben.
4. **Dateigrößen im Blick behalten.** Das Dashboard muss auf Mobilgeräten laden. GeoJSON-Dateien für die Karte sollten < 5MB sein. Ggf. Geometrien vereinfachen (Douglas-Peucker).
5. **Fehlende Daten sind OK.** Nicht jeder Bezirk hat alle Indikatoren. Der Index muss damit umgehen können (gewichteter Durchschnitt der verfügbaren Dimensionen).
6. **Stuttgart hat Topografie.** Die Stadt liegt in einem Talkessel. Luftliniendistanzen sind oft irreführend. Für Erreichbarkeitsanalysen wenn möglich Netzwerkdistanzen (Straßennetz) statt Luftlinie verwenden.
7. **Datenschutz:** Keine Disaggregation auf Einzelpersonen-Ebene. Wenn ein Straßenabschnitt < 50 Einwohner hat, auf Stadtteil-Ebene aggregieren.
8. **Sprache:** Python-Code und Variablennamen auf Englisch. Kommentare und Docstrings auf Deutsch. Dashboard-UI auf Deutsch.
9. **Gehweg-Distanzen statt Luftlinie (Phase 6):** Für die Standortoptimierung MUSS das Straßennetz als networkx-Graph aufgebaut werden. Kantengewichte = Straßenlänge in Metern. Stuttgarts Topografie macht Luftlinien-Radien irreführend — 800m Luftlinie bergauf kann 15+ Minuten Gehzeit bedeuten. Wo möglich: Steigung als Multiplikator auf die Kantenlänge (Höhendaten aus SRTM oder OSM `ele`-Tags).
10. **PuLP-Solver:** Standardmäßig den mitgelieferten CBC-Solver verwenden. Für Szenarien mit n≥10 Standorten kann die Laufzeit steigen — dann ggf. Zeitlimit setzen (`pulp.PULP_CBC_CMD(timeLimit=120)`). Gurobi NICHT verwenden (kommerzielle Lizenz, für dieses Projekt nicht nötig).
11. **OSM-Sozialeinrichtungen sind unvollständig.** Der placement_agent muss eine manuelle Ergänzungsliste (`data/placement/bestand_manuell.json`) unterstützen die mit OSM-Daten gemergt wird. Jugendhäuser und Beratungsstellen sind in OSM schlecht getaggt.
