# Aufwachsindex Stuttgart

**Datenbasierte Entscheidungshilfe für die kommunale Sozialplanung**

---

## Was ist der Aufwachsindex?

Der Aufwachsindex ist ein digitales Werkzeug, das erstmals auf Straßenabschnittsebene sichtbar macht, wo in Stuttgart Kinder und Jugendliche unter schwierigen Bedingungen aufwachsen. Er kombiniert 18 offene Datensätze der Stadt Stuttgart zu einem zusammengesetzten Score (0–100) und zeigt auf einer interaktiven Karte, wo sozialer Handlungsbedarf besteht — nicht auf Bezirksebene, sondern Straße für Straße.

Das Ziel: Knappe Mittel der Kinder- und Jugendhilfe dorthin lenken, wo sie am meisten bewirken.

### Kernaussagen aus den Daten

- **10.893 Straßenabschnitte** in Stuttgart wurden analysiert und bewertet
- **Bad Cannstatt** (60,2), **Mühlhausen** (60,0) und **Wangen** (57,4) haben die höchste Belastung
- **Sillenbuch** (28,6), **Degerloch** (29,4) und **Vaihingen** (30,9) haben die besten Aufwachsbedingungen
- Die Spanne innerhalb einzelner Bezirke ist oft größer als zwischen Bezirken — Durchschnittswerte verdecken lokale Brennpunkte
- **67,6 %** des errechneten Bedarfs werden durch bestehende Einrichtungen nicht abgedeckt

---

## Was kann das Dashboard?

Das Dashboard ist eine mobile-fähige Web-Anwendung (Progressive Web App), die auch offline funktioniert — etwa bei Vor-Ort-Begehungen in den Stadtteilen.

### Interaktive Karte

Jeder Straßenabschnitt ist nach seinem Aufwachsindex eingefärbt: Grün bedeutet gute Bedingungen, Rot bedeutet hohe Belastung. Per Klick auf einen Abschnitt erscheinen alle Detaildaten — welche Dimension wie stark belastet ist, welche Datenquellen einfließen und wie sicher die Schätzung ist.

### Sieben Dimensionen

Der Aufwachsindex setzt sich aus sieben Dimensionen zusammen, die einzeln betrachtet werden können:

| Dimension | Gewicht | Was wird gemessen? |
|---|---|---|
| **Ökonomische Prekarität** | 25 % | SGB-II-Quote, Einkommen, Beschäftigung, Energieverbrauch |
| **Bildung** | 20 % | Gymnasialquote nach Bezirk, Jugendarbeitslosigkeit (unter 25) |
| **Gesundheit & Versorgung** | 15 % | Ärztedichte, Luftqualität (NO₂), Lärmbelastung |
| **Sicherheit** | 10 % | Straßenkriminalität, Verkehrsunfälle |
| **Wohnumfeld** | 10 % | Eigentümerquote, Sozialmietwohnungsdichte |
| **Mobilität & Teilhabe** | 10 % | ÖPNV-Erreichbarkeit, Entfernung zu Schulen/Spielplätzen/Sport, PKW-Dichte |
| **Soziale Kohäsion** | 10 % | Umzugshäufigkeit (Binnenumzüge) als Indikator für Instabilität |

Jede Dimension kann einzeln auf der Karte angezeigt werden. Die Methodik-Ansicht erklärt für jede Dimension transparent, welche Daten einfließen und wie sie berechnet werden.

### Zeitliche Entwicklung

Für alle Dimensionen zeigt das Dashboard die Entwicklung über die letzten drei Jahre als Quartalstrend. So wird sichtbar, ob sich Gebiete verbessern oder verschlechtern — und ob eingeleitete Maßnahmen wirken.

### Standortplanung für Sozialarbeit

Das Dashboard enthält ein Optimierungsmodul, das auf Basis des errechneten Bedarfs optimale Standorte für neue Sozialarbeiterstellen vorschlägt. Es beantwortet konkret die Frage: *Wenn wir X neue Stellen schaffen könnten, wo sollten sie sein?*

| Szenario | Neue Stellen | Jahreskosten | Neu erreichte Kinder |
|---|---|---|---|
| 1 neue Stelle | 1 | 68.000 € | 4.091 |
| 3 neue Stellen | 3 | 204.000 € | 10.133 |
| 5 neue Stellen | 5 | 340.000 € | 16.774 |
| 10 neue Stellen | 10 | 680.000 € | 30.584 |
| Budget 300.000 € | 4 | 272.000 € | 12.377 |
| Budget 500.000 € | 7 | 476.000 € | 22.976 |

Die Standortempfehlungen berücksichtigen:
- Den berechneten Bedarf pro Straßenabschnitt (Index × Kinderzahl)
- Bereits bestehende 211 Sozialeinrichtungen und deren Wirkungsradius
- ÖPNV-Erreichbarkeit der vorgeschlagenen Standorte (max. 300 m zur nächsten Haltestelle)
- Stuttgarts Topografie (Gehwegdistanzen statt Luftlinie, Faktor 1,4 für Hanglagen)
- Realistische Kosten nach TVöD S11b (60.000 €/Jahr Personalkosten + Miete + Sachkosten)

---

## Woher stammen die Daten?

Alle Daten sind öffentlich zugänglich und stammen aus drei Quellen:

1. **Open Data Stuttgart** ([opendata.stuttgart.de](https://opendata.stuttgart.de)) — 114 Datensätze zu Bevölkerung, Sozialleistungen, Bildung, Gesundheit, Kriminalität, Wohnen, Verkehr und Umwelt. Lizenz: CC BY 4.0.

2. **OpenStreetMap** — Straßennetz, Gebäude, Schulen, Kindergärten, Ärzte, Spielplätze, Sportanlagen, ÖPNV-Haltestellen, bestehende Sozialeinrichtungen.

3. **GTFS-Fahrplandaten** (VVS) — 2.351 Haltestellen im Stadtgebiet für die Berechnung der ÖPNV-Erreichbarkeit.

### Transparenz und Ehrlichkeit

Die Originaldaten liegen auf Stadtbezirksebene vor (23 Bezirke). Die Darstellung auf Straßenabschnittsebene basiert auf einer statistischen Schätzung (dasymetrische Disaggregation), bei der Bezirkswerte proportional zur Straßenlänge verteilt werden. Das Dashboard macht dies transparent:

- Jeder Wert trägt einen **Konfidenz-Score** (0–100 %), der anzeigt, wie vollständig die Datenbasis ist
- Bei Klick auf einen Straßenabschnitt werden **Datenquelle und Methode** angezeigt
- Die **Bezirksebene** (gemessene Daten) ist jederzeit als Alternative verfügbar
- Gesamtstädtische Daten (Gesundheit, Umwelt) werden mit dem Hinweis „synthetisch verteilt" gekennzeichnet
- Ein **Methodik-Button** erklärt die Berechnung verständlich für Nicht-Fachleute

---

## Technische Umsetzung (Überblick)

Das System besteht aus einer Datenverarbeitungspipeline und einer Web-Anwendung:

```
114 offene Datensätze        GTFS-Fahrplan        OpenStreetMap
        ↓                        ↓                     ↓
   Katalogisierung          Haltestellen          Straßennetz
   Normalisierung           Erreichbarkeit        10.893 Abschnitte
        ↓                        ↓                     ↓
   ┌─────────────────────────────────────────────────────────┐
   │           Disaggregation: Bezirk → Straße              │
   │    (18 Indikatoren, 7 Dimensionen, Konfidenz-Flags)    │
   └─────────────────────────────────────────────────────────┘
                              ↓
                    Aufwachsindex (0–100)
                    pro Straßenabschnitt
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
      Interaktive Karte              Standortoptimierung
      (Mobile Web-App)              (Mathematische Optimierung)
```

- **Datenverarbeitung:** Python (pandas, geopandas, scipy)
- **Optimierung:** HiGHS Open-Source-Solver (Maximal Covering Location Problem)
- **Dashboard:** React, MapLibre GL (WebGL-Kartendarstellung), Progressive Web App
- **Keine Cloud-Abhängigkeit:** Alle Daten werden lokal verarbeitet, das Dashboard läuft als statische Website

---

## Was wäre der nächste Schritt?

Dieses Projekt ist ein **Prototyp**, der zeigt, was mit vorhandenen offenen Daten möglich ist. Für den produktiven Einsatz wären folgende Schritte sinnvoll:

### Kurzfristig (mit bestehenden Daten)
- **Validierung** der Ergebnisse mit Fachleuten aus Jugendamt und Sozialplanung — stimmen die identifizierten Brennpunkte mit der Erfahrung überein?
- **Pilotbezirk** auswählen und die Standortempfehlungen mit realen Planungsprozessen abgleichen
- **Gewichtung** der Dimensionen gemeinsam mit Fachleuten anpassen (aktuell: Literatur-basierte Standardgewichte)

### Mittelfristig (mit zusätzlichen Daten)
- **Schuldaten auf Schulbezirksebene** würden die Bildungsdimension deutlich präziser machen
- **Kinderarzt-Standorte** und **Versorgungslücken** könnten die Gesundheitsdimension verbessern
- **Jugendhilfestatistik** (HzE-Daten) wäre der stärkste verfügbare Indikator — datenschutzrechtlich aber sensibel
- **Integration in bestehende GIS-Systeme** der Stadtverwaltung

### Langfristig (Skalierung)
- **Übertragbarkeit** auf andere Kommunen in Baden-Württemberg — die Methodik ist universell, nur die Datenquellen müssen angepasst werden
- **Automatische Aktualisierung** bei neuen Open-Data-Veröffentlichungen
- **Wirkungsmessung:** Den Index über Jahre verfolgen und prüfen, ob Investitionen in identifizierte Brennpunkte messbare Verbesserungen bringen

---

## Kontakt

Dieses Projekt wurde im Rahmen einer Analyse offener kommunaler Daten entwickelt. Bei Interesse an einer Präsentation, einem Pilotprojekt oder Fragen zur Methodik wenden Sie sich an:

**Jan Besler**

[E-Mail senden](mailto:jan%40familie-besler.de)

---

*Alle Quelldaten: Stadt Stuttgart, opendata.stuttgart.de (CC BY 4.0). Geodaten: OpenStreetMap-Mitwirkende. Fahrplandaten: VVS.*
