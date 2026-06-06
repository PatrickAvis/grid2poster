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

const DNO_FILL_COLORS = [
  "#8e24aa",
  "#3949ab",
  "#1e88e5",
  "#00897b",
  "#43a047",
  "#c0ca33",
  "#fdd835",
  "#fb8c00",
  "#f4511e",
  "#6d4c41",
  "#546e7a",
  "#d81b60",
  "#5e35b1",
  "#039be5",
];

const DNO_ZONE_COLORS = {
  // Chosen against the DNO adjacency graph to keep neighbouring areas distinct.
  10: "#009e73", // UKPN East England
  11: "#d55e00", // NGED East Midlands
  12: "#56b4e9", // UKPN London
  13: "#ee6677", // SPEN North Wales, Merseyside and Cheshire
  14: "#0066cc", // NGED West Midlands
  15: "#332288", // NPG North East England
  16: "#f0e442", // Electricity North West
  17: "#117733", // SSEN North Scotland
  18: "#cc79a7", // SPEN South and Central Scotland
  19: "#aa4499", // UKPN South East England
  20: "#ddcc77", // SSEN Southern England
  21: "#88ccee", // NGED South Wales
  22: "#882255", // NGED South West England
  23: "#44aa99", // NPG Yorkshire
};

function isInterconnectorCable(props) {
  if (props.power !== "cable") return false;
  const location = String(props.location || "").toLowerCase();
  const frequency = String(props.frequency || "").trim().toLowerCase();
  const text = [
    props.name,
    props.operator,
    props.location,
  ].filter(Boolean).join(" ").toLowerCase();
  return (
    location === "underwater"
    || frequency === "0"
    || text.includes("interconnector")
    || text.includes("interconnect")
    || text.includes("hvdc")
    || text.includes("subsea")
    || text.includes("submarine")
  );
}

export function lineTypeBucket(props) {
  if (isInterconnectorCable(props)) return "interconnector";
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
  if (bucket === "interconnector") {
    return { color, weight: 2.5, opacity: 0.9, dashArray: "2 4" };
  }
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

function stableColorIndex(value, count) {
  const text = String(value || "");
  let hash = 0;
  for (let idx = 0; idx < text.length; idx += 1) {
    hash = (hash * 31 + text.charCodeAt(idx)) >>> 0;
  }
  return hash % count;
}

function dnoFillColor(props) {
  if (props.zone_id != null && DNO_ZONE_COLORS[props.zone_id]) {
    return DNO_ZONE_COLORS[props.zone_id];
  }
  const key = props.zone_id ?? props.name ?? props.operator ?? "";
  return DNO_FILL_COLORS[stableColorIndex(key, DNO_FILL_COLORS.length)];
}

function mixHex(color, target, amount) {
  const source = color.replace("#", "");
  const dest = target.replace("#", "");
  const sourceRgb = [0, 2, 4].map((idx) => parseInt(source.slice(idx, idx + 2), 16));
  const destRgb = [0, 2, 4].map((idx) => parseInt(dest.slice(idx, idx + 2), 16));
  const mixed = sourceRgb.map((channel, idx) => Math.round(channel + (destRgb[idx] - channel) * amount));
  return `#${mixed.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function gspFillColor(props) {
  if (props.dno_zone_id || props.dno_name || props.dno_operator) {
    const base = dnoFillColor({
      zone_id: props.dno_zone_id,
      name: props.dno_name,
      operator: props.dno_operator,
    });
    const key = props.gsp_id ?? props.gsp_name ?? "";
    const variants = [
      ["#ffffff", 0.16],
      ["#ffffff", 0.3],
      ["#ffffff", 0.44],
      ["#ffffff", 0.58],
      ["#000000", 0.08],
      ["#000000", 0.16],
      ["#000000", 0.24],
      ["#000000", 0.32],
    ];
    const [target, amount] = variants[stableColorIndex(key, variants.length)];
    return mixHex(base, target, amount);
  }
  const key = props.gsp_id ?? props.gsp_name ?? props.name ?? "";
  return DNO_FILL_COLORS[stableColorIndex(key, DNO_FILL_COLORS.length)];
}

export function zoneStyle(kind, selected = false, props = {}) {
  const color = kind === "dno" ? dnoFillColor(props) : gspFillColor(props);
  return {
    color: selected ? "#ff6f00" : "#37474f",
    weight: selected ? 3 : (kind === "dno" ? 1.4 : 1),
    opacity: selected ? 0.95 : 0.7,
    fillColor: color,
    fillOpacity: selected ? 0.44 : (kind === "gsp" ? 0.34 : 0.26),
  };
}
