import { fetchGeoJson } from "./geojson.js";
import { createPmtilesLayer } from "./pmtiles.js";

export async function loadLayerData(layerConfig) {
  if (layerConfig.type === "pmtiles") {
    return { type: "pmtiles", url: layerConfig.url, config: layerConfig };
  }
  const data = await fetchGeoJson(layerConfig.url);
  return { type: "geojson", data };
}

export async function createLayerFromData(
  layerKey,
  payload,
  layerConfig,
  helpers,
) {
  if (payload.type === "pmtiles") {
    const styleFn = layerKey === "turbines"
      ? () => helpers.turbineMarkerStyle()
      : (props) => helpers.lineStyle(props || {});
    return createPmtilesLayer(payload.url, layerConfig, styleFn);
  }
  return helpers.buildGeoJsonLayer(layerKey, payload.data, layerConfig);
}
