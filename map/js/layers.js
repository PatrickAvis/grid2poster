import { LINE_TYPE_ORDER } from "./constants.js";
import { buildLayerConfig } from "./layerDefs.js";
import {
  buildLineLegend,
  buildPlantLegend,
  setLineLegendVisible,
  setPlantLegendVisible,
} from "./legends.js";
import { attachLazyPopup, plantPropsForPopup, popupRows, turbinePropsForPopup } from "./popups.js";
import { loadLayerData, createLayerFromData } from "./sources/index.js";
import {
  lineStyle,
  lineTypeBucket,
  plantMarkerStyle,
  plantPolygonStyle,
  plantSourceBucket,
  substationMarkerStyle,
  substationPolygonStyle,
  turbineMarkerStyle,
} from "./styles.js";
import { getLatLon, isPolygonGeometry } from "./utils.js";

export function createLayerManager(map, regionConfig, zoneFilter) {
  const config = {
    ...regionConfig,
    turbineMinZoom: regionConfig.turbineMinZoom ?? 9,
    bmuLookup: regionConfig.bmuLookup ?? null,
  };
  const LAYER_CONFIG = buildLayerConfig(config);
  const layerIds = config.layerIds || Object.keys(LAYER_CONFIG);

  const layerGroups = {};
  const layerCache = {};
  for (const id of layerIds) {
    layerGroups[id] = L.layerGroup();
    layerCache[id] = { loaded: false, loading: null, geoLayer: null, data: null, count: 0 };
  }
  if (layerGroups.plants) {
    layerGroups.plants.addTo(map);
  }

  const lineBucketGroups = {};
  const lineBucketVisibility = {};
  let lineWidthScale = 1;
  let turbinesRequested = false;
  const plantBucketGroups = {};
  const plantBucketVisibility = {};
  let searchHighlight = null;

  function scaledLineStyle(props) {
    const style = lineStyle(props);
    return {
      ...style,
      weight: style.weight ? style.weight * lineWidthScale : style.weight,
    };
  }

  function addGeometryAndMarkers(bucketGroup, features, layerConfig, filterGeometry = null) {
    const polygonFeatures = features.filter((feature) => isPolygonGeometry(feature.geometry));
    if (polygonFeatures.length) {
      const polygonLayer = L.geoJSON(
        { type: "FeatureCollection", features: polygonFeatures },
        {
          style: (feature) => layerConfig.polygonStyleFn(feature.properties || {}),
          onEachFeature: (feature, layer) => {
            const props = feature.properties || {};
            const popupProps = layerConfig.popupPropsFn ? layerConfig.popupPropsFn(props) : props;
            attachLazyPopup(layer, popupProps, layerConfig.popupKeys);
          },
        },
      );
      bucketGroup.addLayer(polygonLayer);
    }

    for (const feature of features) {
      const props = feature.properties || {};
      if (filterGeometry && layerConfig.filterable) {
        const latlon = getLatLon(props, feature);
        if (!latlon || !zoneFilter.pointInside(latlon[0], latlon[1], filterGeometry)) continue;
      }
      const latlon = getLatLon(props, feature);
      if (!latlon) continue;
      const marker = L.circleMarker(latlon, layerConfig.markerStyleFn(props));
      const popupProps = layerConfig.popupPropsFn ? layerConfig.popupPropsFn(props) : props;
      attachLazyPopup(marker, popupProps, layerConfig.popupKeys);
      bucketGroup.addLayer(marker);
    }
  }

  function createGeometryAndMarkerLayer(data, layerConfig, filterGeometry = null) {
    const container = L.featureGroup();
    addGeometryAndMarkers(container, data.features || [], layerConfig, filterGeometry);
    return container;
  }

  function createLineLayer(data, layerConfig) {
    const byBucket = new Map();
    for (const feature of data.features || []) {
      const bucket = lineTypeBucket(feature.properties || {});
      if (!byBucket.has(bucket)) byBucket.set(bucket, []);
      byBucket.get(bucket).push(feature);
    }

    const container = L.layerGroup();
    for (const bucket of Object.keys(lineBucketGroups)) {
      delete lineBucketGroups[bucket];
    }

    for (const bucket of LINE_TYPE_ORDER.filter((key) => byBucket.has(key))) {
      const bucketGroup = L.geoJSON(
        { type: "FeatureCollection", features: byBucket.get(bucket) },
        {
          style: (feature) => scaledLineStyle(feature.properties || {}),
          onEachFeature: (feature, layer) => {
            attachLazyPopup(layer, feature.properties || {}, layerConfig.popupKeys);
          },
        },
      );
      lineBucketGroups[bucket] = bucketGroup;
      lineBucketVisibility[bucket] = lineBucketVisibility[bucket] ?? true;
      if (lineBucketVisibility[bucket]) {
        container.addLayer(bucketGroup);
      }
    }

    return container;
  }

  function createPlantLayer(data, layerConfig, filterGeometry = null) {
    const byBucket = new Map();
    for (const feature of data.features || []) {
      const props = feature.properties || {};
      if (filterGeometry && layerConfig.filterable) {
        const latlon = getLatLon(props, feature);
        if (!latlon || !zoneFilter.pointInside(latlon[0], latlon[1], filterGeometry)) continue;
      }
      const bucket = plantSourceBucket(props);
      if (!byBucket.has(bucket)) byBucket.set(bucket, []);
      byBucket.get(bucket).push(feature);
    }

    const container = L.layerGroup();
    for (const bucket of Object.keys(plantBucketGroups)) {
      delete plantBucketGroups[bucket];
    }

    const orderedBuckets = [
      ...["nuclear", "gas", "coal", "wind", "solar", "hydro", "biomass", "oil", "other"].filter((b) => byBucket.has(b)),
      ...[...byBucket.keys()].filter((bucket) => !["nuclear", "gas", "coal", "wind", "solar", "hydro", "biomass", "oil", "other"].includes(bucket)).sort(),
    ];

    for (const bucket of orderedBuckets) {
      const bucketGroup = L.featureGroup();
      addGeometryAndMarkers(bucketGroup, byBucket.get(bucket), layerConfig, filterGeometry);
      plantBucketGroups[bucket] = bucketGroup;
      plantBucketVisibility[bucket] = plantBucketVisibility[bucket] ?? true;
      if (plantBucketVisibility[bucket]) {
        container.addLayer(bucketGroup);
      }
    }

    return container;
  }

  function buildGeoJsonLayer(layerKey, data, layerConfig) {
    if (layerKey === "lines") {
      return createLineLayer(data, layerConfig);
    }
    if (layerKey === "plants") {
      return createPlantLayer(data, layerConfig, zoneFilter.geometry);
    }
    if (layerConfig.combinedLayer) {
      return createGeometryAndMarkerLayer(data, layerConfig, zoneFilter.geometry);
    }
    if (layerConfig.zoneLayer) {
      return zoneFilter.createZoneLayer(data, layerConfig.zoneLayer);
    }
    const features = zoneFilter.geometry && layerConfig.filterable
      ? (data.features || []).filter((feature) => {
        const props = feature.properties || {};
        const latlon = getLatLon(props, feature);
        return latlon && zoneFilter.pointInside(latlon[0], latlon[1], zoneFilter.geometry);
      })
      : (data.features || []);
    return L.geoJSON(
      { type: "FeatureCollection", features },
      {
        style: layerConfig.styleFn
          ? (feature) => layerConfig.styleFn(feature.properties || {})
          : undefined,
        pointToLayer: layerConfig.pointLayer
          ? (feature, latlng) => L.circleMarker(latlng, layerConfig.styleFn(feature.properties || {}))
          : undefined,
        onEachFeature: (feature, layer) => {
          const props = feature.properties || {};
          const popupProps = layerConfig.popupPropsFn ? layerConfig.popupPropsFn(props) : props;
          attachLazyPopup(layer, popupProps, layerConfig.popupKeys);
        },
      },
    );
  }

  const geoJsonHelpers = {
    buildGeoJsonLayer,
    lineStyle: scaledLineStyle,
    lineWidthScale: () => lineWidthScale,
    turbineMarkerStyle,
    lineBucketGroups,
    lineBucketVisibility,
  };

  function lineLegendOptions() {
    return {
      widthScale: lineWidthScale,
      onWidthScaleChange: setLineWidthScale,
    };
  }

  function syncLineBucketLayers() {
    if (LAYER_CONFIG.lines?.type === "pmtiles") return;
    const parent = layerCache.lines?.geoLayer;
    if (!parent || !document.getElementById("toggle-lines")?.checked) return;
    for (const [bucket, group] of Object.entries(lineBucketGroups)) {
      const visible = lineBucketVisibility[bucket] !== false;
      if (visible && !parent.hasLayer(group)) parent.addLayer(group);
      if (!visible && parent.hasLayer(group)) parent.removeLayer(group);
    }
  }

  function setLineBucketVisible(bucket, visible) {
    if (!lineBucketGroups[bucket]) return;
    lineBucketVisibility[bucket] = visible;
    if (LAYER_CONFIG.lines?.type === "pmtiles") {
      rebuildPmtilesLineLayer();
      return;
    }
    syncLineBucketLayers();
  }

  async function setLineWidthScale(scale) {
    if (!Number.isFinite(scale) || scale <= 0) return;
    lineWidthScale = Math.max(0.5, Math.min(4, scale));
    if (!layerCache.lines?.loaded) return;
    if (LAYER_CONFIG.lines?.type === "pmtiles") {
      await rebuildPmtilesLineLayer();
      return;
    }
    const cache = layerCache.lines;
    layerGroups.lines.clearLayers();
    const geoLayer = createLineLayer(cache.data, LAYER_CONFIG.lines);
    layerGroups.lines.addLayer(geoLayer);
    cache.geoLayer = geoLayer;
    buildLineLegend(lineBucketGroups, lineBucketVisibility, setLineBucketVisible, lineLegendOptions());
    if (document.getElementById("toggle-lines")?.checked) {
      map.addLayer(layerGroups.lines);
      syncLineBucketLayers();
      setLineLegendVisible(true, lineBucketGroups);
    }
  }

  async function rebuildPmtilesLineLayer() {
    const cache = layerCache.lines;
    const layerConfig = LAYER_CONFIG.lines;
    if (!cache?.loaded || layerConfig?.type !== "pmtiles") return;
    try {
      layerGroups.lines.clearLayers();
      const geoLayer = await createLayerFromData(
        "lines",
        { type: "pmtiles", url: layerConfig.url, config: layerConfig },
        layerConfig,
        geoJsonHelpers,
      );
      layerGroups.lines.addLayer(geoLayer);
      cache.geoLayer = geoLayer;
      if (document.getElementById("toggle-lines")?.checked) {
        map.addLayer(layerGroups.lines);
      }
    } catch (error) {
      console.error("Failed to rebuild PMTiles line layer", error);
    }
  }

  function syncPlantBucketLayers() {
    const parent = layerCache.plants?.geoLayer;
    if (!parent || !document.getElementById("toggle-plants")?.checked) return;
    for (const [bucket, group] of Object.entries(plantBucketGroups)) {
      const visible = plantBucketVisibility[bucket] !== false;
      if (visible && !parent.hasLayer(group)) parent.addLayer(group);
      if (!visible && parent.hasLayer(group)) parent.removeLayer(group);
    }
  }

  function setPlantBucketVisible(bucket, visible) {
    if (!plantBucketGroups[bucket]) return;
    plantBucketVisibility[bucket] = visible;
    syncPlantBucketLayers();
  }

  function syncTurbineCheckboxes(enabled) {
    turbinesRequested = enabled;
    const main = document.getElementById("toggle-turbines");
    const sub = document.getElementById("toggle-wind-turbines");
    if (main) main.checked = enabled;
    if (sub) sub.checked = enabled;
  }

  function plantLegendOptions(setStatus) {
    return {
      turbineMinZoom: config.turbineMinZoom,
      turbinesEnabled: turbinesRequested,
      onTurbinesToggle: (enabled) => setLayerEnabled("turbines", enabled, setStatus),
    };
  }

  function turbineZoomOk() {
    return map.getZoom() >= config.turbineMinZoom;
  }

  function syncTurbineLayerOnMap() {
    if (!turbinesRequested || !layerCache.turbines?.loaded) return;
    if (turbineZoomOk()) {
      if (!map.hasLayer(layerGroups.turbines)) map.addLayer(layerGroups.turbines);
    } else if (map.hasLayer(layerGroups.turbines)) {
      map.removeLayer(layerGroups.turbines);
    }
  }

  function setStatusFromRebuild(message, isError = false) {
    const statusEl = document.getElementById("status");
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.classList.toggle("error", isError);
  }

  function rebuildFilterableLayers(filterGeometry) {
    for (const key of ["plants", "turbines"]) {
      if (!layerIds.includes(key)) continue;
      const cache = layerCache[key];
      if (!cache.loaded || !cache.data) continue;
      const layerConfig = LAYER_CONFIG[key];
      layerGroups[key].clearLayers();
      const geoLayer = key === "plants"
        ? createPlantLayer(cache.data, layerConfig, filterGeometry)
        : L.geoJSON(
          {
            type: "FeatureCollection",
            features: (cache.data.features || []).filter((feature) => {
              const props = feature.properties || {};
              const latlon = getLatLon(props, feature);
              return latlon && zoneFilter.pointInside(latlon[0], latlon[1], filterGeometry);
            }),
          },
          {
            pointToLayer: (feature, latlng) => L.circleMarker(latlng, layerConfig.styleFn(feature.properties || {})),
            onEachFeature: (feature, layer) => {
              const props = feature.properties || {};
              const popupProps = layerConfig.popupPropsFn ? layerConfig.popupPropsFn(props) : props;
              attachLazyPopup(layer, popupProps, layerConfig.popupKeys);
            },
          },
        );
      layerGroups[key].addLayer(geoLayer);
      cache.geoLayer = geoLayer;
      if (key === "plants") {
        buildPlantLegend(plantBucketGroups, plantBucketVisibility, setPlantBucketVisible, plantLegendOptions(setStatusFromRebuild));
        syncPlantBucketLayers();
      }
      if (document.getElementById(`toggle-${key}`)?.checked) {
        if (key === "turbines") syncTurbineLayerOnMap();
        else map.addLayer(layerGroups[key]);
      }
    }
  }

  function restoreFilterableLayers() {
    for (const key of ["plants", "turbines"]) {
      if (!layerIds.includes(key)) continue;
      const cache = layerCache[key];
      if (!cache.loaded || !cache.data) continue;
      const layerConfig = LAYER_CONFIG[key];
      layerGroups[key].clearLayers();
      const geoLayer = key === "plants"
        ? createPlantLayer(cache.data, layerConfig)
        : L.geoJSON(cache.data, {
          pointToLayer: (feature, latlng) => L.circleMarker(latlng, layerConfig.styleFn(feature.properties || {})),
          onEachFeature: (feature, layer) => {
            const props = feature.properties || {};
            const popupProps = layerConfig.popupPropsFn ? layerConfig.popupPropsFn(props) : props;
            attachLazyPopup(layer, popupProps, layerConfig.popupKeys);
          },
        });
      layerGroups[key].addLayer(geoLayer);
      cache.geoLayer = geoLayer;
      if (key === "plants") {
        buildPlantLegend(plantBucketGroups, plantBucketVisibility, setPlantBucketVisible, plantLegendOptions(setStatusFromRebuild));
        syncPlantBucketLayers();
      }
      if (document.getElementById(`toggle-${key}`)?.checked) {
        if (key === "turbines") syncTurbineLayerOnMap();
        else map.addLayer(layerGroups[key]);
      }
    }
  }

  async function loadLayer(layerKey, setStatus) {
    const cache = layerCache[layerKey];
    if (!cache) return null;
    if (cache.loaded) return cache.geoLayer;
    if (cache.loading) return cache.loading;

    const layerConfig = LAYER_CONFIG[layerKey];
    cache.loading = (async () => {
      setStatus(`Loading ${layerConfig.label}…`);
      const payload = await loadLayerData(layerConfig);
      const geoLayer = await createLayerFromData(layerKey, payload, layerConfig, geoJsonHelpers);
      layerGroups[layerKey].addLayer(geoLayer);
      if (document.getElementById(`toggle-${layerKey}`)?.checked) {
        if (layerKey === "turbines") {
          syncTurbineLayerOnMap();
        } else if (!layerConfig.zoneLayer) {
          map.addLayer(layerGroups[layerKey]);
        } else {
          map.addLayer(layerGroups[layerKey]);
        }
      }
      cache.geoLayer = geoLayer;
      if (payload.type === "geojson") {
        cache.data = payload.data;
        cache.count = payload.data.features?.length ?? geoLayer.getLayers?.().length ?? 0;
      } else {
        cache.data = null;
        cache.count = 0;
      }
      cache.loaded = true;
      cache.loading = null;
      if (layerKey === "lines") {
        buildLineLegend(lineBucketGroups, lineBucketVisibility, setLineBucketVisible, lineLegendOptions());
        setLineLegendVisible(document.getElementById("toggle-lines")?.checked, lineBucketGroups);
      }
      if (layerKey === "plants") {
        buildPlantLegend(plantBucketGroups, plantBucketVisibility, setPlantBucketVisible, plantLegendOptions(setStatus));
        setPlantLegendVisible(document.getElementById("toggle-plants")?.checked, plantBucketGroups);
      }
      return geoLayer;
    })();

    return cache.loading;
  }

  function updateStatusMessage(setStatus) {
    const parts = [];
    if (layerCache.plants?.loaded) parts.push(`${layerCache.plants.count.toLocaleString()} plants`);
    if (layerCache.turbines?.loaded) {
      const zoomNote = turbineZoomOk() ? "" : ` (zoom ${config.turbineMinZoom}+ to show)`;
      const turbineCount = LAYER_CONFIG.turbines?.type === "pmtiles"
        ? "tiled wind turbines"
        : `${layerCache.turbines.count.toLocaleString()} wind turbines`;
      parts.push(`${turbineCount}${zoomNote}`);
    }
    if (layerCache.lines?.loaded) {
      const lineCount = LAYER_CONFIG.lines?.type === "pmtiles"
        ? "tiled transmission lines"
        : `${layerCache.lines.count.toLocaleString()} transmission lines`;
      parts.push(lineCount);
    }
    if (layerCache.substations?.loaded) parts.push(`${layerCache.substations.count.toLocaleString()} substations`);
    if (layerCache.dno?.loaded) parts.push(`${layerCache.dno.count.toLocaleString()} DNO areas`);
    if (layerCache.gsp?.loaded) parts.push(`${layerCache.gsp.count.toLocaleString()} GSP regions`);
    if (zoneFilter.label) parts.push(`filter: ${zoneFilter.label}`);
    if (!parts.length) {
      setStatus("Ready. Enable a layer to load data.");
      return;
    }
    setStatus(`Loaded ${parts.join(", ")}.`);
  }

  function resultTitle(layerKey, props) {
    return props.name
      || props.gsp_name
      || props.gsp_id
      || props.operator
      || props.osm_id
      || layerKey;
  }

  function resultSubtitle(layerKey, props) {
    const label = LAYER_CONFIG[layerKey]?.label || layerKey;
    const details = [
      props.operator,
      props.bmu_id,
      props.ngc_bmu_id,
      props.gsp_id,
      props.dno_operator,
    ].filter(Boolean);
    return details.length ? `${label} · ${details.join(" · ")}` : label;
  }

  function searchableText(layerKey, props) {
    const keys = [
      "name",
      "operator",
      "osm_id",
      "bmu_id",
      "ngc_bmu_id",
      "gsp_id",
      "gsp_name",
      "dno_name",
      "dno_operator",
      "substation",
      "ref",
    ];
    return [
      LAYER_CONFIG[layerKey]?.label,
      ...keys.map((key) => props[key]),
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function searchFeatures(query) {
    const needle = query.trim().toLowerCase();
    if (needle.length < 2) return [];
    const results = [];
    for (const layerKey of layerIds) {
      const cache = layerCache[layerKey];
      if (!cache?.data?.features?.length) continue;
      for (const feature of cache.data.features) {
        const rawProps = feature.properties || {};
        const props = layerKey === "plants" && LAYER_CONFIG[layerKey]?.popupPropsFn
          ? LAYER_CONFIG[layerKey].popupPropsFn(rawProps)
          : rawProps;
        if (!searchableText(layerKey, props).includes(needle)) continue;
        results.push({
          layerKey,
          feature,
          props,
          title: resultTitle(layerKey, props),
          subtitle: resultSubtitle(layerKey, props),
        });
        if (results.length >= 20) return results;
      }
    }
    return results;
  }

  function focusSearchResult(result) {
    if (searchHighlight) {
      map.removeLayer(searchHighlight);
      searchHighlight = null;
    }
    const layerConfig = LAYER_CONFIG[result.layerKey] || {};
    const latlon = getLatLon(result.props, result.feature);
    const popupHtml = popupRows(result.props, layerConfig.popupKeys || []);

    if (latlon) {
      map.setView(latlon, Math.max(map.getZoom(), 14));
      searchHighlight = L.circleMarker(latlon, {
        radius: 9,
        color: "#ff6f00",
        weight: 3,
        fillColor: "#ffffff",
        fillOpacity: 0.4,
      }).addTo(map);
      searchHighlight.bindPopup(popupHtml).openPopup();
      return;
    }

    const layer = L.geoJSON(result.feature);
    const bounds = layer.getBounds();
    if (bounds?.isValid()) {
      map.fitBounds(bounds.pad(0.1));
      searchHighlight = L.geoJSON(result.feature, {
        style: {
          color: "#ff6f00",
          weight: 4,
          fillOpacity: 0.12,
        },
      }).addTo(map);
      searchHighlight.bindPopup(popupHtml).openPopup();
    }
  }

  async function setLayerEnabled(layerKey, enabled, setStatus) {
    const checkbox = document.getElementById(`toggle-${layerKey}`);
    try {
      if (layerKey === "turbines") {
        turbinesRequested = enabled;
      }
      if (enabled) {
        await loadLayer(layerKey, setStatus);
        if (layerKey === "turbines") {
          syncTurbineLayerOnMap();
        } else {
          map.addLayer(layerGroups[layerKey]);
        }
        if (layerKey === "lines") {
          syncLineBucketLayers();
          setLineLegendVisible(true, lineBucketGroups);
        }
        if (layerKey === "plants") {
          syncPlantBucketLayers();
          setPlantLegendVisible(true, plantBucketGroups);
        }
      } else {
        map.removeLayer(layerGroups[layerKey]);
        if (layerKey === "lines") setLineLegendVisible(false, lineBucketGroups);
        if (layerKey === "plants") setPlantLegendVisible(false, plantBucketGroups);
      }
      if (layerKey === "turbines") {
        syncTurbineCheckboxes(enabled);
      }
      updateStatusMessage(setStatus);
    } catch (error) {
      console.error(error);
      if (checkbox) checkbox.checked = false;
      if (layerKey === "turbines") syncTurbineCheckboxes(false);
      setStatus(`Failed to load ${LAYER_CONFIG[layerKey]?.label || layerKey}: ${error.message}`, true);
    }
  }

  function destroy() {
    for (const id of layerIds) {
      map.removeLayer(layerGroups[id]);
      layerGroups[id].clearLayers();
    }
  }

  return {
    layerIds,
    layerCache,
    layerGroups,
    LAYER_CONFIG,
    loadLayer,
    setLayerEnabled,
    syncTurbineLayerOnMap,
    updateStatusMessage,
    searchFeatures,
    focusSearchResult,
    rebuildFilterableLayers,
    restoreFilterableLayers,
    destroy,
  };
}
