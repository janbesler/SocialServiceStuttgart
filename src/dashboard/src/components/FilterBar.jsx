import useStore from "../store.js";
import { DIMENSIONS } from "../utils/colors.js";

/**
 * Obere Navigationsleiste mit Titel und Dimensions-Auswahl.
 * Mobile-first: kompakt, 56px Höhe.
 */
export default function FilterBar() {
  const {
    activeDimension,
    setActiveDimension,
    showPois,
    togglePois,
    showPlacement,
    togglePlacement,
    loading,
  } = useStore();

  return (
    <header className="flex items-center justify-between px-3 h-14 bg-primary-800 text-white shadow-md z-20 flex-shrink-0">
      {/* Titel */}
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-bold tracking-wide truncate max-w-[160px]">
          Aufwachsindex
        </span>
        <span className="text-[10px] text-blue-200 font-normal">
          Stuttgart
        </span>
      </div>

      {/* Rechte Aktionen */}
      <div className="flex items-center gap-2">
        {/* Standortplanung-Toggle */}
        <button
          onClick={togglePlacement}
          disabled={loading}
          title={showPlacement ? "Standortplanung ausblenden" : "Standortplanung einblenden"}
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
            showPlacement
              ? "bg-orange-500 text-white"
              : "bg-primary-700 text-blue-200 hover:bg-primary-600"
          } disabled:opacity-40`}
        >
          <span>🏢</span>
          <span className="hidden sm:inline">Standortplanung</span>
        </button>

        {/* POI-Toggle */}
        <button
          onClick={togglePois}
          disabled={loading}
          title={showPois ? "POIs ausblenden" : "POIs einblenden"}
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
            showPois
              ? "bg-blue-500 text-white"
              : "bg-primary-700 text-blue-200 hover:bg-primary-600"
          } disabled:opacity-40`}
        >
          <span>📍</span>
          <span className="hidden sm:inline">Einrichtungen</span>
        </button>

        {/* Dimensions-Selector */}
        <select
          value={activeDimension}
          onChange={(e) => setActiveDimension(e.target.value)}
          disabled={loading}
          className="bg-primary-700 text-white text-xs font-medium px-2 py-1.5 rounded-md border border-primary-600 focus:outline-none focus:ring-2 focus:ring-blue-400 appearance-none cursor-pointer disabled:opacity-40 pr-6"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23bfdbfe' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 6px center",
          }}
        >
          {DIMENSIONS.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
