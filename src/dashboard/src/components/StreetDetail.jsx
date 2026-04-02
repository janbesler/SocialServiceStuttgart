import { useEffect, useRef } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import useStore from "../store.js";
import { scoreToColor, konfidenzColor, konfidenzLabel } from "../utils/colors.js";
import {
  fmtScore,
  fmtKonfidenz,
  fmtLaenge,
  scoreLabel,
  scoreTailwindColor,
  truncate,
} from "../utils/format.js";

// Alle Dimensionen mit Labels und GeoJSON-Spalten
const DIMENSIONS = [
  { key: "dim_oekonomie", label: "Ökonomie", short: "Ökon." },
  { key: "dim_sicherheit", label: "Sicherheit", short: "Sicher." },
  { key: "dim_wohnen", label: "Wohnen", short: "Wohnen" },
  { key: "dim_soziale_koh\u00e4sion", label: "Soziale Kohäsion", short: "Kohäsion" },
  { key: "dim_mobilitaet", label: "Mobilität", short: "Mobil." },
];

/**
 * Benutzerdefinierter Radar-Tooltip.
 */
function CustomRadarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-2 py-1.5 text-xs shadow-md">
      <p className="font-semibold text-gray-700">{d.dimension}</p>
      <p style={{ color: scoreToColor(d.value) }} className="font-bold">
        {fmtScore(d.value)}
      </p>
    </div>
  );
}

/**
 * Detail-Bottom-Sheet für einen ausgewählten Straßenabschnitt.
 * Slides up from bottom, ~60vh Höhe, scrollbar.
 */
export default function StreetDetail() {
  const { selectedSegment, setSelectedSegment } = useStore();
  const sheetRef = useRef(null);

  // Slide-in Animation beim Öffnen
  useEffect(() => {
    if (!sheetRef.current) return;
    sheetRef.current.style.transform = "translateY(100%)";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (sheetRef.current) {
          sheetRef.current.style.transform = "translateY(0)";
        }
      });
    });
  }, [selectedSegment?.properties.segment_id]);

  if (!selectedSegment) return null;

  const p = selectedSegment.properties;
  const gesamt = p.aufwachsindex_gesamt;

  // Radar-Daten aufbereiten
  const radarData = DIMENSIONS.map((d) => ({
    dimension: d.short,
    fullLabel: d.label,
    value: p[d.key] ?? null,
  })).filter((d) => d.value !== null);

  const konfidenz = p.konfidenz_gesamt;
  const konfColor = konfidenzColor(konfidenz);
  const konfLbl = konfidenzLabel(konfidenz);

  const streetName = p.name || "Unbekannte Straße";
  const bezirk = p.bezirk || "Unbekannter Bezirk";
  const stadtteil = p.stadtteil || null;

  function handleClose() {
    if (sheetRef.current) {
      sheetRef.current.style.transform = "translateY(100%)";
      setTimeout(() => setSelectedSegment(null), 280);
    } else {
      setSelectedSegment(null);
    }
  }

  return (
    <div
      ref={sheetRef}
      className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-[0_-8px_32px_rgba(0,0,0,0.18)] z-30 flex flex-col"
      style={{
        height: "62vh",
        maxHeight: "520px",
        transform: "translateY(100%)",
        transition: "transform 300ms cubic-bezier(0.32, 0.72, 0, 1)",
        willChange: "transform",
      }}
    >
      {/* Drag Handle + Schließen-Button */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2 flex-shrink-0">
        <div className="w-8 h-1 bg-gray-300 rounded-full mx-auto absolute left-1/2 -translate-x-1/2 top-3" />
        <div className="w-6" /> {/* Spacer */}
        <button
          onClick={handleClose}
          className="ml-auto flex items-center justify-center w-7 h-7 rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 active:bg-gray-300 transition-colors"
          aria-label="Schließen"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>

      {/* Scrollbarer Inhalt */}
      <div className="flex-1 overflow-y-auto sheet-scroll px-4 pb-6 space-y-4">
        {/* Kopfzeile: Name + Score */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-gray-900 leading-tight truncate">
              {streetName}
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {bezirk}
              {stadtteil && stadtteil !== bezirk && (
                <span className="text-gray-400"> · {stadtteil}</span>
              )}
            </p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {/* Straßentyp */}
              {p.highway && (
                <span className="px-1.5 py-0.5 bg-gray-100 text-gray-500 text-[10px] rounded font-medium capitalize">
                  {p.highway}
                </span>
              )}
              {/* Länge */}
              <span className="text-[10px] text-gray-400">
                {fmtLaenge(p.laenge_m)}
              </span>
              {/* n Dimensionen */}
              <span className="text-[10px] text-gray-400">
                {p.n_dimensionen_verfuegbar ?? 0}/5 Dimensionen
              </span>
            </div>
          </div>

          {/* Haupt-Score */}
          <div className="flex-shrink-0 flex flex-col items-end">
            <span
              className="text-4xl font-black leading-none"
              style={{ color: scoreToColor(gesamt) }}
            >
              {fmtScore(gesamt)}
            </span>
            <span className="text-[10px] text-gray-400 mt-0.5">von 100</span>
            <span
              className={`text-[10px] font-semibold mt-0.5 ${scoreTailwindColor(gesamt)}`}
            >
              {scoreLabel(gesamt)}
            </span>
          </div>
        </div>

        {/* Konfidenz-Badge */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs"
          style={{
            borderColor: konfColor + "40",
            backgroundColor: konfColor + "10",
          }}
        >
          <div
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: konfColor }}
          />
          <span className="text-gray-600">
            <strong style={{ color: konfColor }}>Konfidenz: {konfLbl}</strong>
            {" "}({fmtKonfidenz(konfidenz)}) — Wert auf Basis disaggregierter Bezirksdaten.
          </span>
        </div>

        {/* Radar-Chart */}
        {radarData.length >= 3 && (
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">
              Dimensionsprofil
            </p>
            <ResponsiveContainer width="100%" height={180}>
              <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                <PolarGrid stroke="#e5e7eb" />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fontSize: 10, fill: "#6b7280", fontWeight: 500 }}
                />
                <Radar
                  dataKey="value"
                  stroke="#1e3a5f"
                  fill="#1e3a5f"
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
                <Tooltip content={<CustomRadarTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Einzelne Dimensions-Balken */}
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-2">
            Dimensionen im Detail
          </p>
          <div className="space-y-2">
            {DIMENSIONS.map((d) => {
              const val = p[d.key];
              const hasData = val !== null && val !== undefined && !isNaN(val);
              return (
                <DimensionBar
                  key={d.key}
                  label={d.label}
                  value={hasData ? val : null}
                />
              );
            })}
          </div>
        </div>

        {/* Metadaten */}
        <div className="border-t border-gray-100 pt-3">
          <p className="text-[10px] text-gray-400 leading-relaxed">
            Segment-ID: <code className="text-gray-500">{p.segment_id}</code>
            {" · "}OSM-ID: <code className="text-gray-500">{p.osm_id}</code>
          </p>
          <p className="text-[10px] text-gray-400 mt-1 leading-relaxed">
            Datenquelle: <a
              href="https://opendata.stuttgart.de"
              className="underline"
              target="_blank"
              rel="noopener noreferrer"
            >opendata.stuttgart.de</a> (CC BY 4.0) · Disaggregation: dasymetrisch, bevölkerungsgewichtet
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Einzelner Dimensionsbalken mit Label und Wert.
 */
function DimensionBar({ label, value }) {
  const hasData = value !== null && value !== undefined;
  const color = hasData ? scoreToColor(value) : "#e5e7eb";
  const pct = hasData ? Math.min(100, Math.max(0, value)) : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-xs text-gray-700 font-medium">{label}</span>
        <span
          className="text-xs font-bold"
          style={{ color: hasData ? color : "#9ca3af" }}
        >
          {hasData ? fmtScore(value) : "k.A."}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            backgroundColor: color,
            minWidth: hasData ? "4px" : "0",
          }}
        />
      </div>
    </div>
  );
}
