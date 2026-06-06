import { attachLazyPopup } from "./popups.js";
import { zoneStyle } from "./styles.js";

export function createZoneFilter(layerManager, state) {
  let selectedLayer = null;

  function zoneLabel(props, kind) {
    if (kind === "dno") return props.name || props.operator || "DNO area";
    return props.gsp_name || props.gsp_id || props.name || "GSP region";
  }

  function updateFilterStatus() {
    const filterEl = document.getElementById("zone-filter-status");
    if (!filterEl) return;
    if (state.label) {
      filterEl.textContent = `Filtering plants & turbines: ${state.label}`;
      filterEl.hidden = false;
    } else {
      filterEl.textContent = "";
      filterEl.hidden = true;
    }
  }

  function clearSelection() {
    if (selectedLayer) {
      selectedLayer.setStyle(zoneStyle(selectedLayer._zoneKind, false, selectedLayer._zoneProps));
      selectedLayer = null;
    }
    state.geometry = null;
    state.label = null;
    updateFilterStatus();
    layerManager.restoreFilterableLayers();
    layerManager.updateStatusMessage(setStatusFromDom);
  }

  function selectZone(feature, layer, kind) {
    if (selectedLayer && selectedLayer !== layer) {
      selectedLayer.setStyle(zoneStyle(selectedLayer._zoneKind, false, selectedLayer._zoneProps));
    }
    selectedLayer = layer;
    selectedLayer._zoneKind = kind;
    selectedLayer._zoneProps = feature.properties || {};
    state.geometry = feature.geometry;
    state.label = zoneLabel(feature.properties || {}, kind);
    layer.setStyle(zoneStyle(kind, true, feature.properties || {}));
    updateFilterStatus();
    layerManager.rebuildFilterableLayers(state.geometry);
    layerManager.updateStatusMessage(setStatusFromDom);
  }

  function createZoneLayer(data, kind) {
    return L.geoJSON(data, {
      style: (feature) => zoneStyle(kind, false, feature?.properties || {}),
      onEachFeature: (feature, layer) => {
        const props = feature.properties || {};
        layer._zoneKind = kind;
        layer._zoneProps = props;
        attachLazyPopup(layer, props, kind === "dno"
          ? ["name", "operator"]
          : ["gsp_id", "gsp_name", "name"]);
        layer.on("click", (event) => {
          L.DomEvent.stopPropagation(event);
          selectZone(feature, layer, kind);
        });
      },
    });
  }

  const clearButton = document.getElementById("clear-zone-filter");
  if (clearButton) {
    clearButton.addEventListener("click", clearSelection);
  }

  return { createZoneLayer, clearSelection };
}

function setStatusFromDom(message, isError = false) {
  const statusEl = document.getElementById("status");
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}
