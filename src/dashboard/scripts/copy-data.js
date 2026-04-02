/**
 * Kopiert GeoJSON-Dateien aus data/ nach public/data/ für den Dev-Server und Build.
 * Wird als predev und prebuild Script ausgeführt.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "../../..");

const sources = [
  {
    src: path.join(projectRoot, "data/indices/aufwachsindex.geojson"),
    dest: path.join(__dirname, "../public/data/aufwachsindex.geojson"),
  },
  {
    src: path.join(projectRoot, "data/osm/bezirke.geojson"),
    dest: path.join(__dirname, "../public/data/bezirke.geojson"),
  },
  {
    src: path.join(projectRoot, "data/osm/pois.geojson"),
    dest: path.join(__dirname, "../public/data/pois.geojson"),
  },
  {
    src: path.join(projectRoot, "data/osm/stuttgart_mask.geojson"),
    dest: path.join(__dirname, "../public/data/stuttgart_mask.geojson"),
  },
  {
    src: path.join(projectRoot, "data/indices/temporal_quarterly.json"),
    dest: path.join(__dirname, "../public/data/temporal_quarterly.json"),
  },
  // Placement / Standortoptimierung
  {
    src: path.join(projectRoot, "data/placement/kosten_nutzen.json"),
    dest: path.join(__dirname, "../public/data/placement/kosten_nutzen.json"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/baseline.geojson"),
    dest: path.join(__dirname, "../public/data/placement/baseline.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/n1_optimal.geojson"),
    dest: path.join(__dirname, "../public/data/placement/n1_optimal.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/n3_optimal.geojson"),
    dest: path.join(__dirname, "../public/data/placement/n3_optimal.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/n5_optimal.geojson"),
    dest: path.join(__dirname, "../public/data/placement/n5_optimal.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/n10_optimal.geojson"),
    dest: path.join(__dirname, "../public/data/placement/n10_optimal.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/budget_100k.geojson"),
    dest: path.join(__dirname, "../public/data/placement/budget_100k.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/budget_300k.geojson"),
    dest: path.join(__dirname, "../public/data/placement/budget_300k.geojson"),
  },
  {
    src: path.join(projectRoot, "data/placement/szenarien/budget_500k.geojson"),
    dest: path.join(__dirname, "../public/data/placement/budget_500k.geojson"),
  },
];

const destDir = path.join(__dirname, "../public/data");
if (!fs.existsSync(destDir)) {
  fs.mkdirSync(destDir, { recursive: true });
}

const placementDestDir = path.join(__dirname, "../public/data/placement");
if (!fs.existsSync(placementDestDir)) {
  fs.mkdirSync(placementDestDir, { recursive: true });
}

for (const { src, dest } of sources) {
  if (!fs.existsSync(src)) {
    console.warn(`[copy-data] Warnung: Quelldatei nicht gefunden: ${src}`);
    continue;
  }
  fs.copyFileSync(src, dest);
  const sizeMB = (fs.statSync(dest).size / 1024 / 1024).toFixed(1);
  console.log(`[copy-data] Kopiert: ${path.basename(dest)} (${sizeMB} MB)`);
}
