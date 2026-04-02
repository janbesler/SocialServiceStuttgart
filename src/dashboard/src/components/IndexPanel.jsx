import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import useStore from "../store.js";
import { scoreToColor, dimensionKey, DIMENSION_LABELS, LEGEND_STOPS } from "../utils/colors.js";
import { fmtScore } from "../utils/format.js";

/**
 * Berechnet den Median eines Arrays.
 */
function median(arr) {
  if (!arr.length) return null;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Unteres Info-Panel (immer sichtbar wenn kein Segment ausgewählt).
 * Zeigt stadtweite Statistiken und Top-5 belastete Bezirke
 * für die aktuell gewählte Dimension.
 */
export default function IndexPanel() {
  const { indexData, activeDimension, temporalData } = useStore();
  const [showMethodik, setShowMethodik] = useState(false);
  const [showTrend, setShowTrend] = useState(false);

  const activeKey = useMemo(() => dimensionKey(activeDimension), [activeDimension]);
  const activeLabel = DIMENSION_LABELS[activeDimension] || "Gesamt-Index";

  // Stadtweite Kennzahlen für die aktive Dimension
  const cityStats = useMemo(() => {
    if (!indexData) return null;
    const scores = indexData.features
      .map((f) => f.properties[activeKey])
      .filter((v) => v !== null && v !== undefined && !isNaN(v));

    if (!scores.length) return null;

    const med = median(scores);
    const above50 = scores.filter((s) => s > 50).length;
    const pct50 = ((above50 / scores.length) * 100).toFixed(0);
    const max = Math.max(...scores);
    const min = Math.min(...scores);

    return { median: med, pct50: Number(pct50), max, min, total: scores.length };
  }, [indexData, activeKey]);

  // Top 5 Bezirke nach mittlerem Wert der aktiven Dimension
  const top5Bezirke = useMemo(() => {
    if (!indexData) return [];

    const bezirkMap = {};
    for (const feat of indexData.features) {
      const p = feat.properties;
      const b = p.bezirk || "Unbekannt";
      const val = p[activeKey];
      if (!bezirkMap[b]) bezirkMap[b] = { name: b, scores: [] };
      if (val !== null && val !== undefined && !isNaN(val)) {
        bezirkMap[b].scores.push(val);
      }
    }

    return Object.values(bezirkMap)
      .map((b) => ({
        name: b.name.replace("Stuttgart-", "S-"),
        value: b.scores.length > 0
          ? Number((b.scores.reduce((a, c) => a + c, 0) / b.scores.length).toFixed(1))
          : null,
      }))
      .filter((b) => b.value !== null)
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }, [indexData, activeKey]);

  const chartMax = useMemo(() => {
    if (!top5Bezirke.length) return 70;
    const maxVal = Math.max(...top5Bezirke.map((b) => b.value));
    return Math.ceil(maxVal / 10) * 10 + 10;
  }, [top5Bezirke]);

  // Trend-Sparkline: stadtweiter Durchschnitt über die Zeit für aktive Dimension
  const trendData = useMemo(() => {
    if (!temporalData || !temporalData.quarters) return null;
    const dimKey = activeDimension === "gesamt" ? null : activeDimension;
    const source = dimKey ? temporalData.dimensions?.[dimKey] : temporalData.gesamt;
    if (!source) return null;

    // Stadtweiter Durchschnitt pro Quartal
    return temporalData.quarters.map((q, i) => {
      let sum = 0;
      let count = 0;
      for (const bezirk of temporalData.bezirke) {
        const val = source[bezirk]?.[i];
        if (val !== null && val !== undefined) {
          sum += val;
          count++;
        }
      }
      return { quarter: q, value: count > 0 ? Math.round((sum / count) * 10) / 10 : null };
    });
  }, [temporalData, activeDimension]);

  return (
    <>
      <div className="flex-shrink-0 bg-white border-t border-gray-200 shadow-[0_-4px_12px_rgba(0,0,0,0.08)] z-10">
        {/* Drag-Handle */}
        <div className="flex justify-center pt-2 pb-1">
          <div className="w-8 h-1 bg-gray-300 rounded-full" />
        </div>

        <div className="px-4 pb-4 space-y-3">
          {/* Stadtweite Kennzahlen */}
          {cityStats && (
            <div className="flex gap-3">
              <StatCard
                label={`Median ${activeLabel}`}
                value={fmtScore(cityStats.median)}
                color={scoreToColor(cityStats.median)}
                sub={`${cityStats.total.toLocaleString("de-DE")} Abschnitte`}
              />
              <StatCard
                label="Wert > 50"
                value={`${cityStats.pct50} %`}
                color={cityStats.pct50 > 30 ? "#ef4444" : "#f97316"}
                sub="belastete Bereiche"
              />
              <StatCard
                label="Maximum"
                value={fmtScore(cityStats.max)}
                color={scoreToColor(cityStats.max)}
                sub="schlechtester Wert"
              />
            </div>
          )}

          {/* Top Bezirke Balkendiagramm */}
          {top5Bezirke.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1">
                Top 5 belastete Bezirke — {activeLabel}
              </p>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart
                  data={top5Bezirke}
                  layout="vertical"
                  margin={{ top: 2, right: 8, bottom: 2, left: 0 }}
                  barCategoryGap="25%"
                >
                  <XAxis
                    type="number"
                    domain={[0, chartMax]}
                    tick={{ fontSize: 9, fill: "#9ca3af" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={90}
                    tick={{ fontSize: 10, fill: "#374151" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    formatter={(v) => [`${fmtScore(v)}`, `Ø ${activeLabel}`]}
                    labelFormatter={(l) => l}
                    contentStyle={{
                      fontSize: 11,
                      padding: "4px 8px",
                      border: "1px solid #e5e7eb",
                      borderRadius: 6,
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={12}>
                    {top5Bezirke.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={scoreToColor(entry.value)}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trend-Sparkline */}
          {trendData && trendData.length > 1 && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  Trend — {activeLabel}
                </p>
                <button
                  onClick={() => setShowTrend(true)}
                  className="text-[10px] font-semibold text-primary-700 hover:text-primary-900"
                >
                  Zeitverlauf
                </button>
              </div>
              <ResponsiveContainer width="100%" height={50}>
                <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#1e3a5f"
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls
                  />
                  <Tooltip
                    formatter={(v) => [`${fmtScore(v)}`, activeLabel]}
                    labelFormatter={(l) => l}
                    contentStyle={{ fontSize: 10, padding: "2px 6px", borderRadius: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Farbskala Legende + Methodik-Button */}
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                Legende
              </p>
              <div className="flex gap-1">
                {LEGEND_STOPS.map((stop) => (
                  <div key={stop.label} className="flex-1 flex flex-col items-center gap-0.5">
                    <div
                      className="w-full h-3 rounded-sm"
                      style={{ backgroundColor: stop.color }}
                    />
                    <span className="text-[9px] text-gray-500 text-center leading-tight">
                      {stop.label}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[9px] text-green-600 font-medium">Gut</span>
                <span className="text-[9px] text-red-600 font-medium">Stark belastet</span>
              </div>
            </div>
            <button
              onClick={() => setShowMethodik(true)}
              className="flex-shrink-0 mt-3 px-3 py-1.5 text-[10px] font-semibold text-primary-700 bg-primary-50 border border-primary-200 rounded-lg hover:bg-primary-100 transition-colors"
              title="Methodik und Datenquellen anzeigen"
            >
              Methodik
            </button>
          </div>

          {/* Hinweis */}
          <p className="text-[9px] text-gray-400 leading-relaxed">
            Tippen Sie auf einen Straßenabschnitt für Details.
            Daten: <a href="https://opendata.stuttgart.de" className="underline" target="_blank" rel="noopener noreferrer">opendata.stuttgart.de</a> (CC BY 4.0)
          </p>
        </div>
      </div>

      {/* Methodik-Overlay — Portal zu document.body damit es über der Map liegt */}
      {showMethodik && createPortal(
        <MethodikOverlay activeDimension={activeDimension} onClose={() => setShowMethodik(false)} />,
        document.body,
      )}

      {/* Zeitverlauf-Overlay */}
      {showTrend && temporalData && createPortal(
        <TrendOverlay
          temporalData={temporalData}
          activeDimension={activeDimension}
          onClose={() => setShowTrend(false)}
        />,
        document.body,
      )}
    </>
  );
}

/**
 * Kleine Statistik-Karte.
 */
function StatCard({ label, value, color, sub }) {
  return (
    <div className="flex-1 bg-gray-50 rounded-xl p-2.5 border border-gray-100">
      <p className="text-[9px] font-medium text-gray-500 uppercase tracking-wide leading-tight mb-1">
        {label}
      </p>
      <p
        className="text-lg font-bold leading-none mb-0.5"
        style={{ color }}
      >
        {value}
      </p>
      <p className="text-[9px] text-gray-400 leading-tight">{sub}</p>
    </div>
  );
}

/**
 * Vollbild-Zeitverlauf-Overlay mit Linien pro Bezirk.
 */
function TrendOverlay({ temporalData, activeDimension, onClose }) {
  const activeLabel = DIMENSION_LABELS[activeDimension] || "Gesamt-Index";
  const dimKey = activeDimension === "gesamt" ? null : activeDimension;
  const source = dimKey ? temporalData.dimensions?.[dimKey] : temporalData.gesamt;

  // Top 5 Bezirke nach letztem Wert für farbige Linien
  const bezirkeRanked = useMemo(() => {
    if (!source) return [];
    return temporalData.bezirke
      .map((b) => {
        const vals = source[b] || [];
        const lastVal = [...vals].reverse().find((v) => v !== null);
        return { name: b, lastVal: lastVal ?? 0 };
      })
      .sort((a, b) => b.lastVal - a.lastVal);
  }, [source, temporalData.bezirke]);

  const top5 = bezirkeRanked.slice(0, 5);
  const top5Names = new Set(top5.map((b) => b.name));

  // Chart data: each quarter is a row, each Bezirk is a column
  const chartData = useMemo(() => {
    if (!source) return [];
    return temporalData.quarters.map((q, i) => {
      const row = { quarter: q };
      for (const b of top5) {
        row[b.name] = source[b.name]?.[i] ?? null;
      }
      // City average
      let sum = 0, count = 0;
      for (const b of temporalData.bezirke) {
        const v = source[b]?.[i];
        if (v !== null && v !== undefined) { sum += v; count++; }
      }
      row["Stuttgart (Ø)"] = count > 0 ? Math.round((sum / count) * 10) / 10 : null;
      return row;
    });
  }, [source, temporalData, top5]);

  const COLORS = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e", "#1e3a5f"];

  return (
    <div className="fixed inset-0 flex items-start justify-center pt-14 pb-4 px-4" style={{ zIndex: 10000 }}>
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[75vh] flex flex-col overflow-hidden border border-gray-200">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
          <h3 className="text-sm font-bold text-gray-800">Zeitverlauf — {activeLabel}</h3>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full text-gray-500 hover:bg-gray-200"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <p className="text-[10px] text-gray-500 mb-3">
            Top 5 belastete Bezirke + Stadtdurchschnitt (gestrichelt)
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <XAxis
                dataKey="quarter"
                tick={{ fontSize: 9, fill: "#9ca3af" }}
                tickLine={false}
                interval={Math.max(0, Math.floor(chartData.length / 6) - 1)}
              />
              <YAxis
                tick={{ fontSize: 9, fill: "#9ca3af" }}
                tickLine={false}
                axisLine={false}
                width={35}
              />
              <Tooltip
                contentStyle={{ fontSize: 10, padding: "4px 8px", borderRadius: 6 }}
                formatter={(v, name) => [fmtScore(v), name.replace("Stuttgart-", "S-")]}
              />
              {top5.map((b, i) => (
                <Line
                  key={b.name}
                  type="monotone"
                  dataKey={b.name}
                  stroke={COLORS[i]}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  name={b.name.replace("Stuttgart-", "S-")}
                />
              ))}
              <Line
                type="monotone"
                dataKey="Stuttgart (Ø)"
                stroke="#1e3a5f"
                strokeWidth={2}
                strokeDasharray="5 3"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
          {/* Legende */}
          <div className="flex flex-wrap gap-3 mt-3">
            {top5.map((b, i) => (
              <div key={b.name} className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 rounded" style={{ backgroundColor: COLORS[i] }} />
                <span className="text-[10px] text-gray-600">{b.name.replace("Stuttgart-", "S-")}</span>
              </div>
            ))}
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 rounded border-b border-dashed border-primary-800" style={{ borderWidth: 2 }} />
              <span className="text-[10px] text-gray-600 font-medium">Stuttgart (Ø)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Dimensions-Definitionen für die Methodik-Ansicht.
 * Jede Dimension hat: key, label, weight, description, indicators.
 */
const DIMENSION_INFO = {
  oekonomie: {
    label: "Ökonomische Prekarität",
    weight: "25 %",
    description:
      "Misst die finanzielle Belastung von Familien mit Kindern. " +
      "Hohe SGB-II-Quoten, niedriges Einkommen, geringe Beschäftigung und niedriger " +
      "Energieverbrauch (als Wirtschaftsindikator) weisen auf prekäre Bedingungen hin.",
    interpretation:
      "Hohe Werte zeigen Gebiete mit überdurchschnittlicher Kinderarmut, " +
      "niedrigem Haushaltseinkommen und geringer Erwerbsbeteiligung.",
    indicators: [
      { name: "SGB-II-Quote Kinder", source: "sozialgeldempfaenger_sgb_ii", weight: "40 %", method: "pro Kind (0–17)", direction: "higher_worse" },
      { name: "Einkommens-Index", source: "einkommen_index", weight: "25 %", method: "direkt (Rate)", direction: "higher_better" },
      { name: "Beschäftigungsquote", source: "sv_beschaeftigte", weight: "20 %", method: "pro Kind (0–17)", direction: "higher_better" },
      { name: "Energieverbrauch", source: "energie_und_wasserverbrauch", weight: "15 %", method: "pro 100m Straße", direction: "higher_better" },
    ],
  },
  bildung: {
    label: "Bildung",
    weight: "20 %",
    description:
      "Erfasst die Bildungschancen und -teilhabe im Wohnumfeld. " +
      "Der Anteil der Schüler an Gymnasien (Bezirksebene) und die " +
      "Jugendarbeitslosigkeit (unter 25 Jahre) dienen als Proxys für " +
      "Bildungszugang und -erfolg.",
    interpretation:
      "Hohe Werte zeigen Gebiete mit unterdurchschnittlicher Gymnasialquote " +
      "und überdurchschnittlicher Jugendarbeitslosigkeit. Beide Indikatoren " +
      "basieren auf realen Bezirksdaten.",
    indicators: [
      { name: "Gymnasialquote", source: "schulen_nach_stadtbezirken", weight: "50 %", method: "direkt (Rate)", direction: "higher_better" },
      { name: "Jugendarbeitslosigkeit", source: "arbeitslos_nach_stadtbezirken", weight: "50 %", method: "pro Kind (0–17)", direction: "higher_worse" },
    ],
  },
  gesundheit: {
    label: "Gesundheit & Versorgung",
    weight: "15 %",
    description:
      "Bewertet die gesundheitliche Versorgung und Umweltbelastung. " +
      "Ärztedichte, Luftqualität (NO₂) und Lärmbelastung beeinflussen " +
      "die Gesundheit von Kindern im Wohnumfeld.",
    interpretation:
      "Hohe Werte zeigen Gebiete mit geringer Ärztedichte, hoher " +
      "NO₂-Belastung und starkem Straßenlärm. Die Basisdaten sind " +
      "gesamtstädtisch und werden mit Bezirks-spezifischer Varianz verteilt.",
    indicators: [
      { name: "Ärztedichte", source: "arztliche_versorgung", weight: "40 %", method: "direkt (Rate)", direction: "higher_better" },
      { name: "Luftqualität (NO₂)", source: "luftqualitat", weight: "35 %", method: "direkt (Rate)", direction: "higher_worse" },
      { name: "Lärmbelastung", source: "larmbelastung", weight: "25 %", method: "direkt (Rate)", direction: "higher_worse" },
    ],
  },
  sicherheit: {
    label: "Sicherheit",
    weight: "10 %",
    description:
      "Bewertet die Sicherheitslage im direkten Wohnumfeld. " +
      "Straßenkriminalität und Verkehrsunfälle beeinflussen die " +
      "Bewegungsfreiheit und das Sicherheitsgefühl von Kindern.",
    interpretation:
      "Hohe Werte kennzeichnen Straßenabschnitte mit überdurchschnittlicher " +
      "Kriminalitäts- und Unfallbelastung pro 100 m Straßenlänge.",
    indicators: [
      { name: "Straßenkriminalität", source: "kriminalitaet", weight: "60 %", method: "pro 100m Straße", direction: "higher_worse" },
      { name: "Unfälle", source: "unfaelle", weight: "40 %", method: "pro 100m Straße", direction: "higher_worse" },
    ],
  },
  wohnen: {
    label: "Wohnumfeld",
    weight: "10 %",
    description:
      "Erfasst die Wohnstruktur und Wohnstabilität. " +
      "Geringe Eigentümerquoten und hohe Sozialmietwohnungsdichte " +
      "korrelieren mit weniger stabilen Nachbarschaften.",
    interpretation:
      "Hohe Werte zeigen Gebiete mit wenig Wohneigentum und hoher " +
      "Konzentration von Sozialmietwohnungen.",
    indicators: [
      { name: "Eigentümerquote", source: "eigentuemer_quote", weight: "60 %", method: "direkt (Rate, invers)", direction: "higher_better" },
      { name: "Sozialmietwohnungsdichte", source: "sozialmietwohnungen_2023", weight: "40 %", method: "pro 100m Straße", direction: "higher_worse" },
    ],
  },
  mobilitaet: {
    label: "Mobilität & Teilhabe",
    weight: "10 %",
    description:
      "Bewertet die Erreichbarkeit von ÖPNV, Bildungs-, Sport- und Kultureinrichtungen " +
      "sowie die PKW-Dichte als Indikator für autogerechte Straßen. " +
      "Basiert auf GTFS-Haltestellendaten und OSM-POI-Distanzen.",
    interpretation:
      "Hohe Werte zeigen Straßen mit schlechter ÖPNV-Anbindung, " +
      "weiten Wegen zu Schulen, Spielplätzen und Sportstätten, " +
      "sowie hohem PKW-Aufkommen.",
    indicators: [
      { name: "ÖPNV-Erreichbarkeit", source: "gtfs_stops", weight: "35 %", method: "Distanz zur nächsten Haltestelle", direction: "higher_worse" },
      { name: "Schulerreichbarkeit", source: "osm_pois", weight: "20 %", method: "Distanz zur nächsten Schule", direction: "higher_worse" },
      { name: "Spielplatzerreichbarkeit", source: "osm_pois", weight: "15 %", method: "Distanz zum nächsten Spielplatz", direction: "higher_worse" },
      { name: "Sporterreichbarkeit", source: "osm_pois", weight: "10 %", method: "Distanz zur nächsten Sportstätte", direction: "higher_worse" },
      { name: "PKW-Dichte", source: "pkw_bestand", weight: "20 %", method: "pro 100m Straße", direction: "higher_worse" },
    ],
  },
  soziale_kohaesion: {
    label: "Soziale Kohäsion",
    weight: "10 %",
    description:
      "Misst die soziale Stabilität und den Zusammenhalt in der Nachbarschaft. " +
      "Häufige Umzüge (Binnenumzüge) deuten auf instabile Sozialstrukturen hin.",
    interpretation:
      "Hohe Werte zeigen Gebiete mit überdurchschnittlicher Fluktuation. " +
      "Kinder in Umzugsgebieten verlieren häufiger soziale Bindungen.",
    indicators: [
      { name: "Binnenumzugsrate", source: "binnenumzuege", weight: "100 %", method: "pro Kind (0–17)", direction: "higher_worse" },
    ],
  },
};

/**
 * Methodik- und Datenquellen-Overlay.
 * Zeigt je nach activeDimension entweder die Gesamtübersicht oder
 * eine detaillierte Erklärung der ausgewählten Dimension.
 */
function MethodikOverlay({ activeDimension, onClose }) {
  const isGesamt = activeDimension === "gesamt";
  const dimInfo = !isGesamt ? DIMENSION_INFO[activeDimension] : null;

  return (
    <div className="fixed inset-0 flex items-start justify-center pt-14 pb-4 px-4" style={{ zIndex: 10000 }}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Content */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[70vh] flex flex-col overflow-hidden border border-gray-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
          <h3 className="text-sm font-bold text-gray-800">
            {isGesamt ? "Methodik — Gesamt-Index" : `Methodik — ${dimInfo?.label || activeDimension}`}
          </h3>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-full text-gray-500 hover:bg-gray-200"
            aria-label="Schließen"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs text-gray-700 leading-relaxed sheet-scroll">
          {isGesamt ? <GesamtMethodik /> : <DimensionMethodik dim={dimInfo} />}

          <section>
            <h4 className="font-bold text-gray-800 mb-1">Datenquellen</h4>
            <p>
              Alle Quelldaten stammen von{" "}
              <a href="https://opendata.stuttgart.de" className="text-blue-600 underline" target="_blank" rel="noopener noreferrer">
                opendata.stuttgart.de
              </a>{" "}
              (Lizenz: CC BY 4.0, Stadt Stuttgart). Geodaten: OpenStreetMap.
              Referenzjahr: 2022 (Fallback auf aktuellstes verfügbares Jahr).
            </p>
          </section>

          <section>
            <h4 className="font-bold text-gray-800 mb-1">Konfidenz</h4>
            <p>
              Da die Originaldaten auf Stadtbezirksebene vorliegen und auf
              Straßenabschnitte <strong>geschätzt</strong> werden, ist jeder Wert mit
              einem Konfidenz-Score versehen (0–100 %). Die Straßenabschnitts-Werte
              sind <strong>keine Messungen</strong>, sondern statistische Schätzungen.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

/**
 * Gesamt-Index Methodik (alle Dimensionen).
 */
function GesamtMethodik() {
  return (
    <>
      <section>
        <h4 className="font-bold text-gray-800 mb-1">Was ist der Aufwachsindex?</h4>
        <p>
          Der Aufwachsindex ist ein zusammengesetzter Indikator (0–100), der die
          Aufwachsbedingungen von Kindern und Jugendlichen in Stuttgart auf
          Straßenabschnittsebene bewertet. Ein <strong>hoher Wert</strong> bedeutet
          schlechtere Bedingungen. Er dient als Entscheidungshilfe für die kommunale
          Sozialplanung.
        </p>
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-1">Berechnungsmethode</h4>
        <ol className="list-decimal list-inside space-y-1.5">
          <li>
            <strong>Disaggregation:</strong> Bezirks-Statistiken werden mittels
            dasymetrischer Methoden (Straßenlänge als Gewicht) auf 10.893
            Straßenabschnitte verteilt.
          </li>
          <li>
            <strong>Normalisierung:</strong> Jeder Indikator wird per Min-Max auf
            [0, 1] normalisiert (robuste 2./98. Perzentil-Grenzen). Richtung: 1 = schlecht.
          </li>
          <li>
            <strong>Aggregation:</strong> Gewichteter Durchschnitt innerhalb jeder
            Dimension, dann gewichteter Durchschnitt der Dimensionen zum Gesamtindex.
          </li>
          <li>
            <strong>Skalierung:</strong> Endergebnis wird auf 0–100 skaliert.
          </li>
        </ol>
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-2">Dimensionen und Gewichte</h4>
        {Object.entries(DIMENSION_INFO).map(([key, dim]) => (
          <DimCard key={key} name={dim.label} weight={dim.weight} indicators={dim.indicators} />
        ))}
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-1">Datenebenen</h4>
        <p>
          <strong>Bezirksebene:</strong> Ökonomie, Bildung, Sicherheit, Wohnen, Soziale Kohäsion
          basieren auf realen Stadtbezirk-Daten (23 Bezirke).<br/>
          <strong>Gesamtstädtisch + synthetisch:</strong> Gesundheit (Ärztedichte, Luft, Lärm)
          basiert auf stadtweiten Messwerten, auf Bezirke mit heuristischer Varianz verteilt.<br/>
          <strong>Segmentebene:</strong> Mobilität (ÖPNV, POI-Distanzen) wird direkt pro
          Straßenabschnitt aus GTFS- und OSM-Daten berechnet.
        </p>
      </section>
    </>
  );
}

/**
 * Einzeldimension-Methodik (detailliert).
 */
function DimensionMethodik({ dim }) {
  if (!dim) return null;

  return (
    <>
      <section>
        <div className="flex items-center gap-2 mb-2">
          <h4 className="font-bold text-gray-800">{dim.label}</h4>
          <span className="text-[10px] text-white font-medium bg-primary-700 px-2 py-0.5 rounded-full">
            {dim.weight} im Gesamtindex
          </span>
        </div>
        <p>{dim.description}</p>
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-1">Interpretation</h4>
        <p>{dim.interpretation}</p>
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-2">Indikatoren</h4>
        {dim.indicators.map((ind) => (
          <div key={ind.name} className="bg-gray-50 rounded-lg p-3 mb-2 border border-gray-100">
            <div className="flex justify-between items-center mb-1">
              <span className="font-semibold text-gray-800">{ind.name}</span>
              <span className="text-[10px] text-gray-500 font-medium bg-gray-200 px-1.5 py-0.5 rounded">
                {ind.weight}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] mt-1.5">
              <div>
                <span className="text-gray-400">Quelle: </span>
                <span className="font-mono text-gray-600">{ind.source}</span>
              </div>
              <div>
                <span className="text-gray-400">Methode: </span>
                <span className="text-gray-600">{ind.method}</span>
              </div>
              <div className="col-span-2">
                <span className="text-gray-400">Richtung: </span>
                <span className="text-gray-600">
                  {ind.direction === "higher_worse"
                    ? "Hoher Rohwert = schlechter (direkt)"
                    : "Hoher Rohwert = besser (wird invertiert)"}
                </span>
              </div>
            </div>
          </div>
        ))}
      </section>

      <section>
        <h4 className="font-bold text-gray-800 mb-1">Berechnung dieser Dimension</h4>
        <ol className="list-decimal list-inside space-y-1.5">
          <li>
            Jeder Indikator wird auf Straßenabschnittsebene disaggregiert
            (Bezirkswert {"\u00d7"} Straßenlängen-Anteil).
          </li>
          <li>
            {dim.indicators.some((i) => i.method.includes("pro Kind"))
              ? "Rate wird berechnet: Rohwert geteilt durch Kinder (0–17 Jahre) im Abschnitt."
              : dim.indicators.some((i) => i.method.includes("pro 100m"))
                ? "Dichte wird berechnet: Rohwert geteilt durch Straßenlänge \u00d7 100."
                : "Wert wird direkt als Rate übernommen."}
          </li>
          <li>
            Min-Max-Normalisierung auf [0, 1] mit robusten Grenzen (2. und 98. Perzentil).
            {dim.indicators.some((i) => i.direction === "higher_better")
              ? " Indikatoren mit Richtung \"higher_better\" werden invertiert (1 \u2212 Wert)."
              : ""}
          </li>
          <li>
            Gewichteter Durchschnitt der {dim.indicators.length > 1 ? `${dim.indicators.length} Indikatoren` : "Indikatoren"}.
            Fehlende Werte werden ignoriert (Gewichte der vorhandenen Indikatoren werden renormalisiert).
          </li>
          <li>
            Skalierung auf 0–100.
          </li>
        </ol>
      </section>
    </>
  );
}

/**
 * Dimensions-Karte für die Methodik-Übersicht (kompakte Tabellenansicht).
 */
function DimCard({ name, weight, indicators }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 mb-2 border border-gray-100">
      <div className="flex justify-between items-center mb-1.5">
        <span className="font-semibold text-gray-800">{name}</span>
        <span className="text-[10px] text-gray-500 font-medium bg-gray-200 px-1.5 py-0.5 rounded">
          {weight}
        </span>
      </div>
      <table className="w-full text-[10px]">
        <thead>
          <tr className="text-gray-400">
            <th className="text-left font-medium pb-0.5">Indikator</th>
            <th className="text-left font-medium pb-0.5">Quelle</th>
            <th className="text-right font-medium pb-0.5">Gewicht</th>
            <th className="text-right font-medium pb-0.5">Methode</th>
          </tr>
        </thead>
        <tbody>
          {indicators.map((ind) => (
            <tr key={ind.name} className="text-gray-600">
              <td className="py-0.5 pr-2">{ind.name}</td>
              <td className="py-0.5 pr-2 text-gray-400 font-mono text-[9px]">{ind.source}</td>
              <td className="py-0.5 text-right">{ind.weight}</td>
              <td className="py-0.5 text-right text-gray-400">{ind.method}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
