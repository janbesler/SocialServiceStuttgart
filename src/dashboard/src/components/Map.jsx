import { useEffect, useRef, useMemo } from "react";
import maplibregl from "maplibre-gl";
import useStore from "../store.js";
import { scoreToColor, dimensionKey, POI_CONFIG } from "../utils/colors.js";
import { fmtScore } from "../utils/format.js";

// Stuttgart Zentrum und Grenzen
const STUTTGART_CENTER = [9.182, 48.775]; // MapLibre: [lng, lat]
const INITIAL_ZOOM = 11;

// Bounding Box mit leichtem Padding, verhindert Scrollen über Stuttgart hinaus
const STUTTGART_BOUNDS = [
  [9.0269, 48.6723], // SW
  [9.3360, 48.8841], // NE
];


/**
 * Erzeugt die MapLibre-Style-Expression für die Linienfarbe
 * basierend auf dem Score-Wert einer bestimmten Property.
 */
function buildColorExpression(propertyKey) {
  return [
    "case",
    ["==", ["get", propertyKey], null],
    "#9ca3af", // Grau für fehlende Daten
    [
      "interpolate",
      ["linear"],
      ["get", propertyKey],
      0, "#16a34a",
      25, "#22c55e",
      35, "#84cc16",
      45, "#eab308",
      55, "#f97316",
      65, "#ef4444",
      80, "#b91c1c",
      100, "#7f1d1d",
    ],
  ];
}

/**
 * Haupt-Kartenkomponente.
 * Verwendet MapLibre GL JS (WebGL) für zuverlässige GeoJSON-Darstellung
 * ohne Tailwind-CSS-Konflikte.
 */
export default function Map() {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const popupRef = useRef(null);

  const {
    indexData,
    bezirkeData,
    poisData,
    maskData,
    activeDimension,
    showPois,
    setSelectedSegment,
    selectedSegment,
    showPlacement,
    placementData,
    activeScenario,
    setPlacementData,
    setSelectedPlacement,
  } = useStore();

  const activeKey = useMemo(() => dimensionKey(activeDimension), [activeDimension]);
  const activeKeyRef = useRef(activeKey);
  activeKeyRef.current = activeKey;

  // Karte initialisieren (einmalig)
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> Mitwirkende | Daten: <a href="https://opendata.stuttgart.de">opendata.stuttgart.de</a> (CC BY 4.0)',
          },
        },
        layers: [
          {
            id: "osm-tiles",
            type: "raster",
            source: "osm",
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: STUTTGART_CENTER,
      zoom: INITIAL_ZOOM,
      minZoom: 11,
      maxZoom: 19,
      maxBounds: STUTTGART_BOUNDS,
      maxBoundsViscosity: 1.0, // Harte Grenze, kein Gummiband-Effekt
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    popupRef.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Daten-Quellen und Layer hinzufügen (wenn Karte und Daten bereit)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !indexData) return;

    const addLayers = () => {
      // Maske: Alles außerhalb Stuttgarts (+1km Puffer) abdunkeln
      if (maskData && !map.getSource("city-mask")) {
        map.addSource("city-mask", { type: "geojson", data: maskData });
        map.addLayer({
          id: "city-mask-fill",
          type: "fill",
          source: "city-mask",
          paint: {
            "fill-color": "#f3f4f6",
            "fill-opacity": 0.6,
          },
        });
      }

      // Bezirke (Hintergrund-Polygone)
      if (bezirkeData && !map.getSource("bezirke")) {
        map.addSource("bezirke", { type: "geojson", data: bezirkeData });
        map.addLayer({
          id: "bezirke-fill",
          type: "fill",
          source: "bezirke",
          paint: {
            "fill-color": "#1e3a5f",
            "fill-opacity": 0.04,
          },
        });
        map.addLayer({
          id: "bezirke-line",
          type: "line",
          source: "bezirke",
          paint: {
            "line-color": "#1e3a5f",
            "line-width": 1.5,
            "line-opacity": 0.25,
            "line-dasharray": [4, 4],
          },
        });
      }

      // Straßenabschnitte
      if (!map.getSource("segments")) {
        map.addSource("segments", { type: "geojson", data: indexData });

        map.addLayer({
          id: "segments-line",
          type: "line",
          source: "segments",
          paint: {
            "line-color": buildColorExpression(activeKeyRef.current),
            "line-width": [
              "interpolate", ["linear"], ["zoom"],
              10, 1.5,
              13, 4,
              16, 7,
            ],
            "line-opacity": 0.9,
          },
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
        });

        // Unsichtbare breitere Linie für bessere Klickbarkeit
        map.addLayer({
          id: "segments-hitarea",
          type: "line",
          source: "segments",
          paint: {
            "line-color": "transparent",
            "line-width": 16,
            "line-opacity": 0,
          },
        });

        // Highlight-Layer für ausgewähltes Segment
        map.addLayer({
          id: "segments-highlight",
          type: "line",
          source: "segments",
          paint: {
            "line-color": "#ffffff",
            "line-width": [
              "interpolate", ["linear"], ["zoom"],
              10, 3,
              13, 7,
              16, 10,
            ],
            "line-opacity": 0.9,
          },
          layout: {
            "line-cap": "round",
            "line-join": "round",
          },
          filter: ["==", "segment_id", ""], // Leer = nichts hervorgehoben
        });

        // Klick-Handler auf den Hit-Area-Layer
        map.on("click", "segments-hitarea", (e) => {
          if (e.features && e.features.length > 0) {
            const feature = e.features[0];
            setSelectedSegment({
              type: "Feature",
              properties: feature.properties,
              geometry: feature.geometry,
            });
          }
        });

        // Cursor ändern bei Hover
        map.on("mouseenter", "segments-hitarea", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "segments-hitarea", () => {
          map.getCanvas().style.cursor = "";
        });

        // Hover-Tooltip
        map.on("mousemove", "segments-hitarea", (e) => {
          if (e.features && e.features.length > 0) {
            const p = e.features[0].properties;
            const key = activeKeyRef.current;
            const score = p[key];
            const name = p.name || "Unbenannt";
            popupRef.current
              .setLngLat(e.lngLat)
              .setHTML(
                `<div style="font-size:12px;line-height:1.4">
                  <strong>${name}</strong><br/>
                  <span style="color:${scoreToColor(score)};font-weight:bold">${fmtScore(score)}</span>
                  <span style="color:#6b7280"> / 100</span>
                </div>`
              )
              .addTo(map);
          }
        });
        map.on("mouseleave", "segments-hitarea", () => {
          popupRef.current.remove();
        });

        // Klick auf leere Fläche schließt Auswahl
        map.on("click", (e) => {
          const features = map.queryRenderedFeatures(e.point, {
            layers: ["segments-hitarea"],
          });
          if (!features.length) {
            setSelectedSegment(null);
          }
        });
      }
    };

    if (map.isStyleLoaded()) {
      addLayers();
    } else {
      map.on("load", addLayers);
    }
  }, [indexData, bezirkeData, maskData, setSelectedSegment]);

  // POI-Layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !poisData) return;

    const updatePois = () => {
      if (!map.getSource("pois")) {
        map.addSource("pois", { type: "geojson", data: poisData });
      }

      if (showPois) {
        if (!map.getLayer("pois-circles")) {
          map.addLayer({
            id: "pois-circles",
            type: "circle",
            source: "pois",
            paint: {
              "circle-radius": [
                "interpolate", ["linear"], ["zoom"],
                10, 2,
                14, 5,
                18, 8,
              ],
              "circle-color": [
                "match",
                ["get", "amenity"],
                "school", POI_CONFIG.school.color,
                "kindergarten", POI_CONFIG.kindergarten.color,
                "doctors", POI_CONFIG.doctors.color,
                "clinic", POI_CONFIG.clinic.color,
                "hospital", POI_CONFIG.hospital.color,
                // Fallback — check leisure
                [
                  "match",
                  ["get", "leisure"],
                  "playground", POI_CONFIG.playground.color,
                  "sports_centre", POI_CONFIG.sports_centre.color,
                  "#6b7280",
                ],
              ],
              "circle-stroke-width": 1.5,
              "circle-stroke-color": "#ffffff",
            },
            filter: [
              "any",
              ["in", ["get", "amenity"], ["literal", ["school", "kindergarten", "doctors", "clinic", "hospital"]]],
              ["in", ["get", "leisure"], ["literal", ["playground", "sports_centre"]]],
            ],
          });
        }
      } else {
        if (map.getLayer("pois-circles")) {
          map.removeLayer("pois-circles");
        }
      }
    };

    if (map.isStyleLoaded()) {
      updatePois();
    } else {
      map.on("load", updatePois);
    }
  }, [poisData, showPois]);

  // Placement-Szenario laden wenn sich das aktive Szenario oder showPlacement ändert
  useEffect(() => {
    if (!showPlacement) return;

    fetch(`./data/placement/${activeScenario}.geojson`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setPlacementData(data);
      })
      .catch(() => {
        // Placement-Daten optional — kein Fehler
      });
  }, [activeScenario, showPlacement, setPlacementData]);

  // Placement-Layer hinzufügen / entfernen / aktualisieren
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const PLACEMENT_LAYERS = [
      "placement-coverage",
      "placement-existing",
      "placement-recommended",
    ];

    const removePlacementLayers = () => {
      for (const id of PLACEMENT_LAYERS) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      if (map.getSource("placement")) map.removeSource("placement");
    };

    const addPlacementLayers = (data) => {
      if (map.getSource("placement")) {
        map.getSource("placement").setData(data);
      } else {
        map.addSource("placement", { type: "geojson", data });
      }

      // Coverage rings (Polygon-Features)
      if (!map.getLayer("placement-coverage")) {
        map.addLayer({
          id: "placement-coverage",
          type: "fill",
          source: "placement",
          filter: ["==", ["geometry-type"], "Polygon"],
          paint: {
            "fill-color": "#f97316",
            "fill-opacity": 0.1,
            "fill-outline-color": "#f97316",
          },
        });
      }

      // Bestehende Einrichtungen (blau)
      if (!map.getLayer("placement-existing")) {
        map.addLayer({
          id: "placement-existing",
          type: "circle",
          source: "placement",
          filter: [
            "all",
            ["==", ["geometry-type"], "Point"],
            ["==", ["get", "ist_empfehlung"], false],
          ],
          paint: {
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              10, 6,
              15, 8,
            ],
            "circle-color": "#3b82f6",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
      }

      // Empfohlene neue Standorte (orange)
      if (!map.getLayer("placement-recommended")) {
        map.addLayer({
          id: "placement-recommended",
          type: "circle",
          source: "placement",
          filter: [
            "all",
            ["==", ["geometry-type"], "Point"],
            ["==", ["get", "ist_empfehlung"], true],
          ],
          paint: {
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              10, 8,
              15, 10,
            ],
            "circle-color": "#f97316",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Klick-Handler auf Placement-Marker
        map.on("click", "placement-recommended", (e) => {
          if (e.features && e.features.length > 0) {
            setSelectedPlacement({
              type: "Feature",
              properties: e.features[0].properties,
              geometry: e.features[0].geometry,
            });
            e.stopPropagation?.();
          }
        });
        map.on("click", "placement-existing", (e) => {
          if (e.features && e.features.length > 0) {
            setSelectedPlacement({
              type: "Feature",
              properties: e.features[0].properties,
              geometry: e.features[0].geometry,
            });
            e.stopPropagation?.();
          }
        });

        map.on("mouseenter", "placement-recommended", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "placement-recommended", () => {
          map.getCanvas().style.cursor = "";
        });
        map.on("mouseenter", "placement-existing", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "placement-existing", () => {
          map.getCanvas().style.cursor = "";
        });
      }
    };

    const applyUpdate = () => {
      if (!showPlacement || !placementData) {
        removePlacementLayers();
      } else {
        addPlacementLayers(placementData);
      }
    };

    if (map.isStyleLoaded()) {
      applyUpdate();
    } else {
      map.on("load", applyUpdate);
    }
  }, [showPlacement, placementData, setSelectedPlacement]);

  // Dimension wechseln → Farben aktualisieren
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("segments-line")) return;

    map.setPaintProperty(
      "segments-line",
      "line-color",
      buildColorExpression(activeKey),
    );
  }, [activeKey]);

  // Highlight des ausgewählten Segments
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("segments-highlight")) return;

    if (selectedSegment) {
      const sid = selectedSegment.properties.segment_id;
      map.setFilter("segments-highlight", ["==", "segment_id", sid]);

      // Zur Straße fliegen
      try {
        const coords = selectedSegment.geometry.coordinates;
        if (coords && coords.length > 0) {
          // Mittelpunkt der Linie
          const midIdx = Math.floor(coords.length / 2);
          const [lng, lat] = coords[midIdx];
          map.flyTo({ center: [lng, lat], duration: 500 });
        }
      } catch {
        // Geometrie ungültig
      }
    } else {
      map.setFilter("segments-highlight", ["==", "segment_id", ""]);
    }
  }, [selectedSegment]);

  return (
    <div ref={mapContainerRef} className="w-full h-full" />
  );
}
