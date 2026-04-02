import { useMemo } from "react";
import useStore from "../store.js";
import { scoreToColor, dimensionKey, DIMENSION_LABELS } from "../utils/colors.js";
import { fmtScore, fmtInt } from "../utils/format.js";

/**
 * Übersichtstabelle aller Stadtbezirke.
 * Zeigt sortierte Bezirke nach mittlerem Wert der aktiven Dimension.
 */
export default function BezirkView({ onClose }) {
  const { indexData, activeDimension } = useStore();

  const activeKey = useMemo(() => dimensionKey(activeDimension), [activeDimension]);
  const activeLabel = DIMENSION_LABELS[activeDimension] || "Gesamt-Index";

  const bezirkStats = useMemo(() => {
    if (!indexData) return null;

    const bezirkMap = {};
    for (const feat of indexData.features) {
      const p = feat.properties;
      const b = p.bezirk || "Unbekannt";
      const val = p[activeKey];
      if (!bezirkMap[b]) bezirkMap[b] = { name: b, scores: [], count: 0 };
      if (val !== null && val !== undefined && !isNaN(val)) {
        bezirkMap[b].scores.push(val);
        bezirkMap[b].count++;
      }
    }

    return Object.values(bezirkMap)
      .map((b) => ({
        name: b.name,
        count: b.count,
        mean: b.scores.length > 0
          ? b.scores.reduce((a, c) => a + c, 0) / b.scores.length
          : null,
      }))
      .sort((a, b) => (b.mean || 0) - (a.mean || 0));
  }, [indexData, activeKey]);

  if (!bezirkStats) return null;

  return (
    <div className="absolute inset-0 bg-white z-40 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-primary-800">
        <h2 className="text-sm font-bold text-white">Alle Stadtbezirke — {activeLabel}</h2>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-full bg-primary-700 text-white hover:bg-primary-600"
          aria-label="Schließen"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>

      {/* Scrollbare Tabelle */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-2 text-gray-500 font-semibold">Bezirk</th>
              <th className="text-right px-3 py-2 text-gray-500 font-semibold">Ø {activeLabel}</th>
              <th className="text-right px-3 py-2 text-gray-500 font-semibold">Abschnitte</th>
              <th className="w-20 px-3 py-2 text-gray-500 font-semibold">Skala</th>
            </tr>
          </thead>
          <tbody>
            {bezirkStats.map((b, i) => (
              <tr
                key={b.name}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
              >
                <td className="px-4 py-2.5 font-medium text-gray-700">
                  {b.name.replace("Stuttgart-", "S-")}
                </td>
                <td
                  className="px-3 py-2.5 text-right font-bold"
                  style={{ color: scoreToColor(b.mean) }}
                >
                  {fmtScore(b.mean)}
                </td>
                <td className="px-3 py-2.5 text-right text-gray-400">
                  {fmtInt(b.count)}
                </td>
                <td className="px-3 py-2.5">
                  <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, (b.mean || 0) * 1.4)}%`,
                        backgroundColor: scoreToColor(b.mean),
                      }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
