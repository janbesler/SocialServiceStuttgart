/**
 * Formatierungshilfsfunktionen für das Aufwachsindex-Dashboard.
 * Alle Ausgaben auf Deutsch.
 */

/**
 * Formatiert einen Index-Score auf eine Dezimalstelle.
 * @param {number|null} v - Score 0-100
 * @returns {string} Formatierter Score oder "k.A."
 */
export function fmtScore(v) {
  if (v === null || v === undefined || isNaN(v)) return "k.A.";
  return Number(v).toFixed(1);
}

/**
 * Formatiert einen Konfidenzwert als Prozentangabe.
 * @param {number|null} v - Konfidenz 0-1
 * @returns {string} Prozentangabe oder "k.A."
 */
export function fmtKonfidenz(v) {
  if (v === null || v === undefined || isNaN(v)) return "k.A.";
  return `${Math.round(Number(v) * 100)} %`;
}

/**
 * Formatiert eine Länge in Metern.
 * @param {number|null} v - Länge in Metern
 * @returns {string} Formatierte Länge
 */
export function fmtLaenge(v) {
  if (v === null || v === undefined || isNaN(v)) return "k.A.";
  const m = Number(v);
  if (m >= 1000) return `${(m / 1000).toFixed(2)} km`;
  return `${Math.round(m)} m`;
}

/**
 * Gibt eine textuelle Bewertung für einen Index-Score zurück.
 * @param {number|null} v - Score 0-100
 * @returns {string} Bewertungstext
 */
export function scoreLabel(v) {
  if (v === null || v === undefined || isNaN(v)) return "Keine Daten";
  if (v < 25) return "Sehr gute Bedingungen";
  if (v < 40) return "Gute Bedingungen";
  if (v < 55) return "Leicht belastet";
  if (v < 65) return "Belastet";
  if (v < 80) return "Stark belastet";
  return "Sehr stark belastet";
}

/**
 * Gibt eine Farb-Klasse für einen Bewertungstext zurück.
 * @param {number|null} v - Score 0-100
 * @returns {string} Tailwind-Textfarbe
 */
export function scoreTailwindColor(v) {
  if (v === null || v === undefined || isNaN(v)) return "text-gray-400";
  if (v < 25) return "text-green-600";
  if (v < 40) return "text-green-500";
  if (v < 55) return "text-yellow-600";
  if (v < 65) return "text-orange-500";
  if (v < 80) return "text-red-500";
  return "text-red-800";
}

/**
 * Formatiert eine Zahl als deutsche Ganzzahl.
 * @param {number} v
 * @returns {string}
 */
export function fmtInt(v) {
  if (v === null || v === undefined || isNaN(v)) return "k.A.";
  return new Intl.NumberFormat("de-DE").format(Math.round(v));
}

/**
 * Kürzt einen langen Straßennamen für enge Anzeigen.
 * @param {string} name
 * @param {number} maxLen
 * @returns {string}
 */
export function truncate(name, maxLen = 28) {
  if (!name) return "Unbekannte Straße";
  if (name.length <= maxLen) return name;
  return name.slice(0, maxLen - 1) + "…";
}

/**
 * Gibt einen menschenlesbaren Namen für eine Dimension zurück.
 * @param {string} dimKey - GeoJSON-Spaltenname
 * @returns {string}
 */
export function dimKeyToLabel(dimKey) {
  const map = {
    aufwachsindex_gesamt: "Gesamt",
    dim_oekonomie: "Ökonomie",
    dim_sicherheit: "Sicherheit",
    dim_wohnen: "Wohnen",
    "dim_soziale_koh\u00e4sion": "Soziale Kohäsion",
    dim_mobilitaet: "Mobilität",
  };
  return map[dimKey] || dimKey;
}
