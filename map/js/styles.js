import {
  LINE_TYPE_COLORS,
  PLANT_CAP_REF_MW,
  PLANT_COLORS,
  PLANT_MARKER_FALLBACK_RADIUS,
  PLANT_MARKER_MAX_RADIUS,
  PLANT_MARKER_MIN_RADIUS,
  SUBSTATION_COLORS,
} from "./constants.js";
import { parseCapacityToMw, parseVoltageKv } from "./utils.js";

export function lineTypeBucket(props) {
  if (props.power === "cable") return "cable";
  const kv = parseVoltageKv(props);
  if (kv == null) return "lv";
  if (kv >= 500) return "ehv";
  if (kv >= 300) return "hv";
  if (kv >= 150) return "mv";
  return "lv";
}

export function lineStyle(props) {
  const bucket = lineTypeBucket(props);
  const color = LINE_TYPE_COLORS[bucket];
  if (bucket === "cable") {
    return { color, weight: 2, opacity: 0.85, dashArray: "6 4" };
  }
  if (bucket === "ehv") return { color, weight: 4, opacity: 0.9 };
  if (bucket === "hv") return { color, weight: 3.5, opacity: 0.9 };
  if (bucket === "mv") return { color, weight: 3, opacity: 0.85 };
  const kv = parseVoltageKv(props);
  return { color, weight: 2, opacity: kv == null ? 0.75 : 0.8 };
}

export function plantCapacityMw(props) {
  if (props.capacity_mw != null && props.capacity_mw !== "") {
    const parsed = Number(props.capacity_mw);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return parseCapacityToMw(
    props["plant:output:electricity"] ?? props["generator:output:electricity"],
  );
}

export function bucketPlantSource(source) {
  if (!source) return "other";
  const text = String(source).toLowerCase();
  if (text.includes("solar") || text.includes("photovoltaic") || text.includes("pv")) return "solar";
  if (text.includes("wind")) return "wind";
  if (text.includes("hydro") || text.includes("tidal") || text.includes("wave")) return "hydro";
  if (text.includes("nuclear")) return "nuclear";
  if (text.includes("coal") || text.includes("lignite")) return "coal";
  if (text.includes("biomass") || text.includes("biogas") || text.includes("wood")) return "biomass";
  if (text.includes("gas")) return "gas";
  if (text.includes("oil") || text.includes("diesel") || text.includes("petroleum")) return "oil";
  return "other";
}

export function plantSourceBucket(props) {
  const bucket = props.source_bucket || bucketPlantSource(
    props["plant:source"] || props.generator_source || props.source,
  );
  return PLANT_COLORS[bucket] ? bucket : "other";
}

export function plantMarkerRadius(props) {
  const mw = plantCapacityMw(props);
  if (mw == null) return PLANT_MARKER_FALLBACK_RADIUS;
  const frac = Math.sqrt(Math.min(mw, PLANT_CAP_REF_MW) / PLANT_CAP_REF_MW);
  return PLANT_MARKER_MIN_RADIUS + frac * (PLANT_MARKER_MAX_RADIUS - PLANT_MARKER_MIN_RADIUS);
}

export function plantPolygonStyle(props) {
  const bucket = plantSourceBucket(props);
  const color = PLANT_COLORS[bucket] || PLANT_COLORS.other;
  return {
    color: "#263238",
    weight: 1,
    opacity: 0.75,
    fillColor: color,
    fillOpacity: 0.35,
  };
}

export function plantMarkerStyle(props) {
  const bucket = plantSourceBucket(props);
  const color = PLANT_COLORS[bucket] || PLANT_COLORS.other;
  return {
    radius: plantMarkerRadius(props),
    fillColor: color,
    color: "#263238",
    weight: 1,
    opacity: 0.95,
    fillOpacity: 0.9,
  };
}

export function substationPolygonStyle(props) {
  const type = String(props.substation || "other").toLowerCase();
  const color = SUBSTATION_COLORS[type] || SUBSTATION_COLORS.other;
  return {
    color,
    weight: 1.5,
    opacity: 0.85,
    fillColor: color,
    fillOpacity: 0.2,
  };
}

export function substationMarkerStyle(props) {
  const type = String(props.substation || "other").toLowerCase();
  const color = SUBSTATION_COLORS[type] || SUBSTATION_COLORS.other;
  return {
    radius: 4,
    fillColor: color,
    color: "#ffffff",
    weight: 1,
    opacity: 0.95,
    fillOpacity: 0.95,
  };
}

export function turbineMarkerStyle() {
  return {
    radius: 2,
    fillColor: PLANT_COLORS.wind,
    color: "#263238",
    weight: 0.5,
    opacity: 0.85,
    fillOpacity: 0.75,
  };
}

export function zoneStyle(kind, selected = false) {
  const color = kind === "dno" ? "#7e57c2" : "#26a69a";
  return {
    color: selected ? "#ff6f00" : color,
    weight: selected ? 3 : 1.5,
    opacity: 0.9,
    fillColor: color,
    fillOpacity: selected ? 0.25 : 0.08,
  };
}
