let protocolInstance = null;
let leafletPmModule = null;

async function loadPmtilesModules() {
  if (protocolInstance && leafletPmModule) {
    return { protocol: protocolInstance, leafletPm: leafletPmModule };
  }
  if (window.pmtiles?.Protocol) {
    protocolInstance = new window.pmtiles.Protocol();
    leafletPmModule = window.protomapsLeaflet;
    if (leafletPmModule?.leafletLayer) {
      return { protocol: protocolInstance, leafletPm: leafletPmModule };
    }
  }
  const pmtilesMod = await import("https://esm.run/pmtiles@3.2.1");
  const leafletPmMod = await import("https://esm.run/@protomaps/leaflet-pmtiles@2.0.0");
  protocolInstance = new pmtilesMod.Protocol();
  leafletPmModule = leafletPmMod;
  return { protocol: protocolInstance, leafletPm: leafletPmMod };
}

export async function createPmtilesLayer(url, layerConfig, styleFn) {
  const { protocol, leafletPm } = await loadPmtilesModules();
  const absUrl = new URL(url, window.location.href).href;
  const sourceLayer = layerConfig.sourceLayer || layerConfig.id || "default";

  return leafletPm.leafletLayer({
    url: protocol.getUrl(absUrl),
    paint_rules: [
      {
        dataLayer: sourceLayer,
        symbolizer: (feature) => styleFn(feature.props || {}),
      },
    ],
  });
}

export function isPmtilesAvailable() {
  return Boolean(window.pmtiles?.Protocol);
}
