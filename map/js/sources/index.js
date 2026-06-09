import { fetchGeoJson } from "./geojson.js";
import { createPmtilesLayer } from "./pmtiles.js";
import { LINE_TYPE_ORDER } from "../constants.js";

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
    if (layerKey === "lines" && helpers.lineBucketGroups && helpers.lineBucketVisibility) {
      for (const bucket of Object.keys(helpers.lineBucketGroups)) {
        delete helpers.lineBucketGroups[bucket];
      }
      for (const bucket of LINE_TYPE_ORDER) {
        helpers.lineBucketGroups[bucket] = true;
        helpers.lineBucketVisibility[bucket] = helpers.lineBucketVisibility[bucket] ?? true;
      }
      const visibleLineBuckets = LINE_TYPE_ORDER.filter(
        (bucket) => helpers.lineBucketVisibility[bucket] !== false,
      );
      return createPmtilesLayer(
        payload.url,
        {
          ...layerConfig,
          visibleLineBuckets,
          lineWidthScale: helpers.lineWidthScale?.() ?? 1,
        },
        (props) => helpers.lineStyle(props || {}),
      );
    }
    const styleFn = layerConfig.styleFn
      ? (props) => layerConfig.styleFn(props || {})
      : (props) => helpers.lineStyle(props || {});
    return createPmtilesLayer(payload.url, layerConfig, styleFn);
  }
  return helpers.buildGeoJsonLayer(layerKey, payload.data, layerConfig);
}
