import { useEffect, useCallback } from "react";
import useStore from "./store.js";
import FilterBar from "./components/FilterBar.jsx";
import Map from "./components/Map.jsx";
import IndexPanel from "./components/IndexPanel.jsx";
import StreetDetail from "./components/StreetDetail.jsx";
import ScenarioPanel from "./components/ScenarioPanel.jsx";

export default function App() {
  const {
    setIndexData,
    setBezirkeData,
    setPoisData,
    setMaskData,
    setTemporalData,
    setKostenNutzenData,
    setLoading,
    setLoadingError,
    loading,
    loadingError,
    selectedSegment,
    showPlacement,
  } = useStore();

  // Lade alle GeoJSON-Daten beim Start
  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      // Parallel laden für bessere Performance
      const [indexRes, bezirkeRes, poisRes, maskRes] = await Promise.all([
        fetch("./data/aufwachsindex.geojson"),
        fetch("./data/bezirke.geojson"),
        fetch("./data/pois.geojson"),
        fetch("./data/stuttgart_mask.geojson"),
      ]);

      if (!indexRes.ok) throw new Error(`Aufwachsindex: HTTP ${indexRes.status}`);
      if (!bezirkeRes.ok) throw new Error(`Bezirke: HTTP ${bezirkeRes.status}`);
      if (!poisRes.ok) throw new Error(`POIs: HTTP ${poisRes.status}`);
      if (!maskRes.ok) throw new Error(`Maske: HTTP ${maskRes.status}`);

      const [indexData, bezirkeData, poisData, maskData] = await Promise.all([
        indexRes.json(),
        bezirkeRes.json(),
        poisRes.json(),
        maskRes.json(),
      ]);

      setIndexData(indexData);
      setBezirkeData(bezirkeData);
      setPoisData(poisData);
      setMaskData(maskData);

      setLoading(false);

      // Temporale Daten nachladen (nicht-blockierend)
      fetch("./data/temporal_quarterly.json")
        .then((r) => r.ok ? r.json() : null)
        .then((data) => { if (data) setTemporalData(data); })
        .catch(() => { /* Temporale Daten optional */ });

      // Kosten-Nutzen-Daten nachladen (nicht-blockierend, optional)
      fetch("./data/placement/kosten_nutzen.json")
        .then((r) => r.ok ? r.json() : null)
        .then((data) => { if (data) setKostenNutzenData(data); })
        .catch(() => { /* Placement-Daten optional */ });
    } catch (err) {
      console.error("Fehler beim Laden der Daten:", err);
      setLoadingError(err.message);
    }
  }, [setIndexData, setBezirkeData, setPoisData, setMaskData, setTemporalData, setKostenNutzenData, setLoading, setLoadingError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loadingError) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-white p-6">
        <div className="text-red-500 text-5xl mb-4">⚠</div>
        <h1 className="text-xl font-semibold text-gray-800 mb-2">
          Daten konnten nicht geladen werden
        </h1>
        <p className="text-gray-500 text-sm text-center max-w-xs mb-4">
          {loadingError}
        </p>
        <p className="text-gray-400 text-xs text-center max-w-xs">
          Stellen Sie sicher, dass die GeoJSON-Dateien im Ordner{" "}
          <code className="bg-gray-100 px-1 rounded">public/data/</code> vorhanden sind.
        </p>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-2 bg-primary-800 text-white rounded-lg text-sm font-medium"
        >
          Erneut versuchen
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full overflow-hidden bg-white">
      {/* Header mit FilterBar */}
      <FilterBar />

      {/* Kartenbereich — nimmt den verbleibenden Platz */}
      <div className="flex-1 relative overflow-hidden">
        {loading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 z-10">
            <div className="w-10 h-10 border-4 border-primary-800 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-gray-600 text-sm font-medium">
              Kartendaten werden geladen…
            </p>
            <p className="text-gray-400 text-xs mt-1">
              (6,7 MB Geodaten)
            </p>
          </div>
        ) : (
          <Map />
        )}
      </div>

      {/* Bottom Sheet: Standortplanung, Strassendetail oder IndexPanel */}
      {showPlacement ? (
        <ScenarioPanel />
      ) : selectedSegment ? (
        <StreetDetail />
      ) : (
        <IndexPanel />
      )}
    </div>
  );
}
