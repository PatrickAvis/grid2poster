let leafletPmModule = null;

import { LINE_TYPE_COLORS, LINE_TYPE_ORDER } from "../constants.js";
import { lineTypeBucket } from "../styles.js";

function featureProps(feature) {
  return feature?.props || feature?.properties || {};
}

async function loadPmtilesModules() {
  if (leafletPmModule) {
    return { leafletPm: leafletPmModule };
  }

  leafletPmModule = window.protomapsL || window.protomapsLeaflet;
  if (!leafletPmModule?.leafletLayer) {
    throw new Error("Protomaps Leaflet library not loaded");
  }
  return { leafletPm: leafletPmModule };
}

function parseDashArray(value) {
  if (!value) return [];
  return String(value)
    .split(/[,\s]+/)
    .map((part) => Number(part))
    .filter((part) => Number.isFinite(part) && part > 0);
}

class LineStyleSymbolizer {
  constructor(styleFn) {
    this.styleFn = styleFn;
  }

  draw(context, geom, _z, feature) {
    const style = this.styleFn(feature.props || {});
    context.save();
    context.strokeStyle = style.color || "#1976d2";
    context.lineWidth = style.weight || 2;
    context.globalAlpha = style.opacity ?? 0.85;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.setLineDash(parseDashArray(style.dashArray));
    context.beginPath();
    for (const line of geom) {
      for (let idx = 0; idx < line.length; idx += 1) {
        const point = line[idx];
        if (idx === 0) context.moveTo(point.x, point.y);
        else context.lineTo(point.x, point.y);
      }
    }
    context.stroke();
    context.restore();
  }
}

class PointStyleSymbolizer {
  constructor(styleFn) {
    this.styleFn = styleFn;
  }

  draw(context, geom, _z, feature) {
    const point = geom?.[0]?.[0];
    if (!point) return;
    const style = this.styleFn(feature.props || {});
    context.save();
    context.globalAlpha = style.opacity ?? 0.85;
    context.fillStyle = style.fillColor || "#0288d1";
    context.strokeStyle = style.color || "#263238";
    context.lineWidth = style.weight ?? 0.5;
    context.beginPath();
    context.arc(point.x, point.y, style.radius || 2, 0, 2 * Math.PI);
    context.fill();
    if (context.lineWidth > 0) context.stroke();
    context.restore();
  }
}

export async function createPmtilesLayer(url, layerConfig, styleFn) {
  const { leafletPm } = await loadPmtilesModules();
  const absUrl = new URL(url, window.location.href).href;
  const sourceLayer = layerConfig.sourceLayer || layerConfig.id || "default";
  let paintRules;
  if (layerConfig.kind === "lines" && leafletPm.LineSymbolizer) {
    const widthScale = layerConfig.lineWidthScale ?? 1;
    const visibleBuckets = new Set(
      layerConfig.visibleLineBuckets || (layerConfig.lineBucket ? [layerConfig.lineBucket] : LINE_TYPE_ORDER),
    );
    const featureBucket = (feature) => lineTypeBucket(featureProps(feature));
    const isVisible = (feature) => visibleBuckets.has(featureBucket(feature));
    paintRules = [{
      dataLayer: sourceLayer,
      symbolizer: new leafletPm.LineSymbolizer({
        color: (_zoom, feature) => LINE_TYPE_COLORS[featureBucket(feature)] || LINE_TYPE_COLORS.lv,
        width: (zoom, feature) => {
          if (!isVisible(feature)) return 0;
          const bucket = featureBucket(feature);
          const zoomBoost = Math.max(0, Math.min(2, (zoom - 8) * 0.25));
          if (bucket === "ehv") return (4 + zoomBoost) * widthScale;
          if (bucket === "hv") return (3.5 + zoomBoost) * widthScale;
          if (bucket === "mv") return (3 + zoomBoost) * widthScale;
          if (bucket === "interconnector") return (2.5 + zoomBoost) * widthScale;
          return (2 + zoomBoost) * widthScale;
        },
        opacity: (_zoom, feature) => {
          if (!isVisible(feature)) return 0;
          return featureBucket(feature) === "cable" ? 0.85 : 0.9;
        },
        dash: (_zoom, feature) => {
          const bucket = featureBucket(feature);
          if (bucket === "interconnector") return [2, 4];
          if (bucket === "cable") return [6, 4];
          return [];
        },
        dashColor: (_zoom, feature) => LINE_TYPE_COLORS[featureBucket(feature)] || LINE_TYPE_COLORS.lv,
        dashWidth: 2,
        lineCap: "round",
        lineJoin: "round",
      }),
    }];
  } else {
    const symbolizer = layerConfig.pointLayer
      ? new PointStyleSymbolizer(styleFn)
      : new LineStyleSymbolizer(styleFn);
    paintRules = [
      {
        dataLayer: sourceLayer,
        symbolizer,
      },
    ];
  }

  return leafletPm.leafletLayer({
    url: absUrl,
    paintRules,
    paint_rules: paintRules,
    labelRules: [],
    label_rules: [],
    zIndex: 450,
    // Archives are tiled to z14 (see scripts/build_tiles.py). Tell the renderer
    // the real max data zoom so it overzooms the deepest tiles past z15 instead
    // of requesting non-existent z15+ tiles (which made points vanish at z16+).
    maxDataZoom: layerConfig.maxDataZoom ?? 14,
  });
}

export function isPmtilesAvailable() {
  return Boolean(window.pmtiles?.Protocol);
}
