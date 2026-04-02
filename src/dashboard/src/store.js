import { create } from "zustand";

/**
 * Zustand store für den Aufwachsindex Dashboard.
 * Globaler State: ausgewählter Straßenabschnitt, aktive Dimension,
 * geladene Geodaten, UI-Zustand, temporale Daten.
 */
const useStore = create((set) => ({
  // Ausgewählter Straßenabschnitt (GeoJSON Feature)
  selectedSegment: null,
  setSelectedSegment: (feature) => set({ selectedSegment: feature }),

  // Aktive Anzeigedimension
  activeDimension: "gesamt",
  setActiveDimension: (dim) => set({ activeDimension: dim }),

  // POI-Overlay sichtbar?
  showPois: false,
  togglePois: () => set((s) => ({ showPois: !s.showPois })),

  // Geladene Geodaten
  indexData: null,
  bezirkeData: null,
  poisData: null,
  maskData: null,
  setIndexData: (data) => set({ indexData: data }),
  setBezirkeData: (data) => set({ bezirkeData: data }),
  setPoisData: (data) => set({ poisData: data }),
  setMaskData: (data) => set({ maskData: data }),

  // Temporale Quartalsdaten für Trend-Charts
  temporalData: null,
  setTemporalData: (data) => set({ temporalData: data }),

  // Placement / Standortoptimierung
  placementData: null,
  kostenNutzenData: null,
  activeScenario: "n3_optimal",
  showPlacement: false,
  selectedPlacement: null,
  setPlacementData: (data) => set({ placementData: data }),
  setKostenNutzenData: (data) => set({ kostenNutzenData: data }),
  setActiveScenario: (s) => set({ activeScenario: s }),
  togglePlacement: () => set((s) => ({ showPlacement: !s.showPlacement })),
  setSelectedPlacement: (feature) => set({ selectedPlacement: feature }),

  // Ladezustand
  loading: true,
  loadingError: null,
  setLoading: (v) => set({ loading: v }),
  setLoadingError: (err) => set({ loadingError: err, loading: false }),
}));

export default useStore;
