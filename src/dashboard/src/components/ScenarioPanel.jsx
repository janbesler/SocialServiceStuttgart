import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import useStore from "../store.js";

/** Alle verfügbaren Szenarien mit Anzeigenamen */
const SZENARIEN = [
  { id: "baseline", label: "Nur Bestand" },
  { id: "n1_optimal", label: "1 neue Stelle" },
  { id: "n3_optimal", label: "3 neue Stellen" },
  { id: "n5_optimal", label: "5 neue Stellen" },
  { id: "n10_optimal", label: "10 neue Stellen" },
  { id: "budget_100k", label: "Budget 100.000 €" },
  { id: "budget_300k", label: "Budget 300.000 €" },
  { id: "budget_500k", label: "Budget 500.000 €" },
];

/**
 * Formatiert einen Euro-Betrag als lesbare Zeichenkette (z.B. "204.000 €").
 */
function fmtEur(value) {
  if (value == null) return "–";
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Formatiert eine ganze Zahl mit Tausender-Trennzeichen.
 */
function fmtInt(value) {
  if (value == null) return "–";
  return new Intl.NumberFormat("de-DE").format(value);
}

/**
 * Formatiert eine Prozentzahl mit einer Nachkommastelle.
 */
function fmtPct(value) {
  if (value == null) return "–";
  return `${Number(value).toFixed(1)} %`;
}

/**
 * Einzelne Kennzahl-Karte im Raster.
 */
function MetricCard({ label, value, highlight }) {
  return (
    <div
      className={`rounded-lg p-3 flex flex-col gap-0.5 ${
        highlight ? "bg-orange-50 border border-orange-200" : "bg-gray-50 border border-gray-200"
      }`}
    >
      <span className="text-[10px] text-gray-500 uppercase tracking-wide leading-tight">
        {label}
      </span>
      <span
        className={`text-base font-bold leading-tight ${
          highlight ? "text-orange-700" : "text-gray-800"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

/**
 * Benutzerdefinierter Tooltip für das Balkendiagramm.
 */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm text-xs">
      <p className="font-medium text-gray-700 mb-0.5">{label}</p>
      <p className="text-orange-600 font-bold">
        {fmtInt(payload[0].value)} Kinder
      </p>
    </div>
  );
}

/**
 * Panel für die Standortoptimierung (ersetzt IndexPanel wenn showPlacement aktiv).
 * Zeigt Szenario-Auswahl, Kennzahlen und Vergleichs-Balkendiagramm.
 */
export default function ScenarioPanel() {
  const {
    kostenNutzenData,
    activeScenario,
    setActiveScenario,
    selectedPlacement,
    setSelectedPlacement,
  } = useStore();

  const szenarien = kostenNutzenData?.szenarien ?? null;
  const aktiv = szenarien?.[activeScenario] ?? null;

  // Daten für das Vergleichs-Balkendiagramm (alle Szenarien ohne baseline)
  const chartData = useMemo(() => {
    if (!szenarien) return [];
    return SZENARIEN.filter((s) => s.id !== "baseline").map((s) => ({
      name: s.label,
      id: s.id,
      kinder: szenarien[s.id]?.erreichte_kinder_neu ?? 0,
    }));
  }, [szenarien]);

  return (
    <div className="flex-shrink-0 bg-white border-t border-gray-200 shadow-lg overflow-y-auto max-h-[45vh]">
      {/* Detail-Overlay für ausgewählten Standort */}
      {selectedPlacement && (
        <div className="border-b border-orange-100 bg-orange-50 px-4 py-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    selectedPlacement.properties.ist_empfehlung
                      ? "bg-orange-500"
                      : "bg-blue-500"
                  }`}
                />
                <span className="text-xs font-semibold text-gray-800 truncate">
                  {selectedPlacement.properties.name || "Unbenannter Standort"}
                </span>
                {selectedPlacement.properties.ist_empfehlung && (
                  <span className="text-[10px] bg-orange-200 text-orange-800 px-1.5 py-0.5 rounded font-medium flex-shrink-0">
                    Empfehlung
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                {selectedPlacement.properties.kosten_jahr != null && (
                  <span>
                    <span className="text-gray-400 block text-[10px]">Kosten/Jahr</span>
                    {fmtEur(selectedPlacement.properties.kosten_jahr)}
                  </span>
                )}
                {selectedPlacement.properties.erreichte_kinder != null && (
                  <span>
                    <span className="text-gray-400 block text-[10px]">Kinder</span>
                    {fmtInt(selectedPlacement.properties.erreichte_kinder)}
                  </span>
                )}
                {selectedPlacement.properties.abgedeckter_bedarf != null && (
                  <span>
                    <span className="text-gray-400 block text-[10px]">Bedarf</span>
                    {Number(selectedPlacement.properties.abgedeckter_bedarf).toFixed(1)}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => setSelectedPlacement(null)}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none flex-shrink-0"
              aria-label="Standort-Detail schließen"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="px-4 pt-3 pb-4 space-y-4">
        {/* Szenario-Auswahl */}
        <div className="flex items-center gap-2">
          <label
            htmlFor="szenario-select"
            className="text-xs font-semibold text-gray-600 whitespace-nowrap flex-shrink-0"
          >
            Szenario:
          </label>
          <select
            id="szenario-select"
            value={activeScenario}
            onChange={(e) => setActiveScenario(e.target.value)}
            className="flex-1 text-xs font-medium px-2 py-1.5 rounded-md border border-gray-300 bg-white text-gray-800 focus:outline-none focus:ring-2 focus:ring-orange-400 appearance-none cursor-pointer"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 6px center",
              paddingRight: "24px",
            }}
          >
            {SZENARIEN.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Kennzahlen-Karten */}
        {aktiv ? (
          <div className="grid grid-cols-2 gap-2">
            <MetricCard
              label="Neue Standorte"
              value={fmtInt(aktiv.n_neue_stellen)}
              highlight={aktiv.n_neue_stellen > 0}
            />
            <MetricCard
              label="Kosten / Jahr"
              value={fmtEur(aktiv.gesamtkosten_jahr_eur)}
              highlight={aktiv.gesamtkosten_jahr_eur > 0}
            />
            <MetricCard
              label="Neu erreichte Kinder"
              value={fmtInt(aktiv.erreichte_kinder_neu)}
              highlight={aktiv.erreichte_kinder_neu > 0}
            />
            <MetricCard
              label="Bedarfsdeckung"
              value={fmtPct(aktiv.anteil_bedarf_abgedeckt_pct)}
              highlight={false}
            />
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 rounded-lg bg-gray-100 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Vergleichs-Balkendiagramm */}
        {chartData.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Neu erreichte Kinder je Szenario
            </p>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart
                data={chartData}
                margin={{ top: 0, right: 4, left: -20, bottom: 0 }}
                barCategoryGap="20%"
              >
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 9, fill: "#6b7280" }}
                  tickLine={false}
                  axisLine={false}
                  interval={0}
                  angle={-30}
                  textAnchor="end"
                  height={36}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f3f4f6" }} />
                <Bar dataKey="kinder" radius={[3, 3, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.id}
                      fill={entry.id === activeScenario ? "#f97316" : "#d1d5db"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Methodenhinweis */}
        <p className="text-[10px] text-gray-400 leading-relaxed">
          Modell: MCLP (Maximal Covering Location). Gehweg-Radius: 800 m.
          Bestehende Einrichtungen{" "}
          <span className="inline-block w-2 h-2 rounded-full bg-blue-500 align-middle" />{" "}
          und Empfehlungen{" "}
          <span className="inline-block w-2 h-2 rounded-full bg-orange-500 align-middle" />{" "}
          auf Karte sichtbar.
        </p>
      </div>
    </div>
  );
}
