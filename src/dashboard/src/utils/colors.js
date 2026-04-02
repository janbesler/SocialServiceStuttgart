/**
 * Hilfsfunktionen für Farbgebung des Aufwachsindex-Dashboards.
 * Divergierende Farbskala: Grün (gut) → Rot (schlecht).
 * Farbenblind-sicher (Rot-Grün-Vermeidung bei starken Pastelltönen).
 */

// Farbstufen für den Index (0–100, höher = schlechtere Bedingungen)
const COLOR_STOPS = [
  { threshold: 0, color: "#16a34a" }, // Grün - sehr gut
  { threshold: 25, color: "#22c55e" }, // Hell-Grün - gut
  { threshold: 35, color: "#84cc16" }, // Gelb-Grün - leicht belastet
  { threshold: 45, color: "#eab308" }, // Gelb - mittel belastet
  { threshold: 55, color: "#f97316" }, // Orange - belastet
  { threshold: 65, color: "#ef4444" }, // Rot - stark belastet
  { threshold: 80, color: "#b91c1c" }, // Dunkel-Rot - sehr stark belastet
  { threshold: 100, color: "#7f1d1d" }, // Tiefrot
];

/**
 * Gibt eine Hex-Farbe für einen Index-Wert zurück.
 * @param {number|null} score - Index-Wert 0-100
 * @returns {string} Hex-Farbcode
 */
export function scoreToColor(score) {
  if (score === null || score === undefined || isNaN(score)) {
    return "#9ca3af"; // Grau für fehlende Daten
  }

  const clamped = Math.max(0, Math.min(100, score));

  // Lineare Interpolation zwischen den Farbstufen
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const lower = COLOR_STOPS[i];
    const upper = COLOR_STOPS[i + 1];
    if (clamped >= lower.threshold && clamped <= upper.threshold) {
      const t = (clamped - lower.threshold) / (upper.threshold - lower.threshold);
      return interpolateHex(lower.color, upper.color, t);
    }
  }

  return COLOR_STOPS[COLOR_STOPS.length - 1].color;
}

/**
 * Interpoliert zwischen zwei Hex-Farben.
 * @param {string} hex1 - Startfarbe
 * @param {string} hex2 - Endfarbe
 * @param {number} t - Interpolationsfaktor 0-1
 * @returns {string} Interpolierte Hex-Farbe
 */
function interpolateHex(hex1, hex2, t) {
  const r1 = parseInt(hex1.slice(1, 3), 16);
  const g1 = parseInt(hex1.slice(3, 5), 16);
  const b1 = parseInt(hex1.slice(5, 7), 16);
  const r2 = parseInt(hex2.slice(1, 3), 16);
  const g2 = parseInt(hex2.slice(3, 5), 16);
  const b2 = parseInt(hex2.slice(5, 7), 16);

  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);

  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

/**
 * Mappt eine Dimension-ID auf den GeoJSON-Spaltennamen.
 * @param {string} dim - Dimension-ID aus dem Store
 * @returns {string} GeoJSON-Spaltenname
 */
export function dimensionKey(dim) {
  const mapping = {
    gesamt: "aufwachsindex_gesamt",
    oekonomie: "dim_oekonomie",
    bildung: "dim_bildung",
    gesundheit: "dim_gesundheit",
    sicherheit: "dim_sicherheit",
    wohnen: "dim_wohnen",
    mobilitaet: "dim_mobilitaet",
    // Umlaut-Variante aus den echten Daten
    soziale_kohaesion: "dim_soziale_koh\u00e4sion",
  };
  return mapping[dim] || "aufwachsindex_gesamt";
}

/**
 * Gibt die deutschen Bezeichnungen der Dimensionen zurück.
 */
export const DIMENSION_LABELS = {
  gesamt: "Gesamt-Index",
  oekonomie: "Ökonomie",
  bildung: "Bildung",
  gesundheit: "Gesundheit",
  sicherheit: "Sicherheit",
  wohnen: "Wohnen",
  mobilitaet: "Mobilität",
  soziale_kohaesion: "Soziale Kohäsion",
};

/**
 * Alle verfügbaren Dimensionen als Array für Dropdowns.
 */
export const DIMENSIONS = Object.entries(DIMENSION_LABELS).map(
  ([id, label]) => ({ id, label })
);

/**
 * Konfidenz-Wert zu Farbe (für Badges).
 * @param {number} v - Konfidenz 0-1
 * @returns {string} Tailwind-Klasse oder Farbcode
 */
export function konfidenzColor(v) {
  if (v === null || v === undefined || isNaN(v)) return "#9ca3af";
  if (v >= 0.8) return "#16a34a";
  if (v >= 0.5) return "#f59e0b";
  return "#ef4444";
}

/**
 * Gibt Label-Text für Konfidenz zurück.
 */
export function konfidenzLabel(v) {
  if (v === null || v === undefined || isNaN(v)) return "Unbekannt";
  if (v >= 0.8) return "Hoch";
  if (v >= 0.5) return "Mittel";
  return "Niedrig";
}

/**
 * Farbskala-Stufen für die Legende.
 */
export const LEGEND_STOPS = [
  { label: "0–25", color: "#22c55e", text: "Gut" },
  { label: "25–40", color: "#84cc16", text: "Leicht belastet" },
  { label: "40–55", color: "#eab308", text: "Mittel belastet" },
  { label: "55–70", color: "#f97316", text: "Belastet" },
  { label: "70–100", color: "#b91c1c", text: "Stark belastet" },
];

/**
 * POI-Kategorien zu Farben und Labels.
 */
export const POI_CONFIG = {
  school: { color: "#3b82f6", label: "Schule", emoji: "🏫" },
  kindergarten: { color: "#8b5cf6", label: "Kita", emoji: "🧒" },
  doctors: { color: "#06b6d4", label: "Arzt", emoji: "⚕️" },
  clinic: { color: "#0891b2", label: "Klinik", emoji: "🏥" },
  hospital: { color: "#0e7490", label: "Krankenhaus", emoji: "🏥" },
  playground: { color: "#f59e0b", label: "Spielplatz", emoji: "🛝" },
  sports_centre: { color: "#10b981", label: "Sport", emoji: "⚽" },
  stop_position: { color: "#6b7280", label: "Haltestelle", emoji: "🚌" },
};
