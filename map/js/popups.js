import { escapeHtml, parseCapacityToMw } from "./utils.js";
import { plantCapacityMw } from "./styles.js";

const POPUP_KEY_LABELS = {
  bmu_id: "BMU",
  ngc_bmu_id: "NGC BMU ID",
  bmu_type: "BMU type",
};

export function plantPropsForPopup(props, bmuLookup = null) {
  const mw = plantCapacityMw(props);
  const bmu = bmuLookup ? bmuLookup(props) : {};
  return {
    ...props,
    ...bmu,
    capacity_mw: mw != null ? `${mw.toFixed(1)} MW` : undefined,
  };
}

export function turbinePropsForPopup(props) {
  const mw = props.capacity_mw != null && props.capacity_mw !== ""
    ? Number(props.capacity_mw)
    : parseCapacityToMw(props["generator:output:electricity"]);
  return {
    ...props,
    capacity_mw: mw != null && !Number.isNaN(mw) ? `${mw.toFixed(2)} MW` : undefined,
    height_m: props.height_m != null && props.height_m !== "" ? `${props.height_m} m` : undefined,
    rotor_diameter_m: props.rotor_diameter_m != null && props.rotor_diameter_m !== ""
      ? `${props.rotor_diameter_m} m`
      : undefined,
  };
}

export function popupRows(props, preferredKeys) {
  const rows = [];
  const seen = new Set();
  for (const key of preferredKeys) {
    if (props[key] == null || props[key] === "") continue;
    rows.push([key, props[key]]);
    seen.add(key);
  }
  for (const [key, value] of Object.entries(props)) {
    if (seen.has(key) || value == null || value === "") continue;
    if (key === "geometry" || key.startsWith("bbox")) continue;
    rows.push([key, value]);
  }
  if (!rows.length) return "<em>No properties</em>";
  return `<table class="popup-table">${rows
    .slice(0, 12)
    .map(([key, value]) => {
      const label = POPUP_KEY_LABELS[key] || key;
      return `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`;
    })
    .join("")}</table>`;
}

export function attachLazyPopup(layer, props, preferredKeys) {
  layer.on("click", function handleClick() {
    if (!this.getPopup()) {
      this.bindPopup(popupRows(props, preferredKeys));
    }
    this.openPopup();
  });
}
