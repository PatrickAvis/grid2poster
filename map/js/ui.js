export function buildLayerPanel(regionConfig, onToggle) {
  const container = document.getElementById("layer-list");
  container.replaceChildren();

  for (const layerId of regionConfig.layerIds) {
    if (layerId === "turbines") continue;
    const layer = regionConfig.layers[layerId];
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `toggle-${layerId}`;
    checkbox.checked = Boolean(layer.defaultOn);
    checkbox.addEventListener("change", (event) => {
      onToggle(layerId, event.target.checked);
    });
    label.append(checkbox, document.createTextNode(layer.label || layerId));
    container.appendChild(label);
  }

  const hasZones = regionConfig.layerIds.some((id) => regionConfig.layers[id]?.zone);
  const clearBtn = document.getElementById("clear-zone-filter");
  if (clearBtn) {
    clearBtn.hidden = !hasZones;
  }
}

export function buildRegionSelector(catalog, currentRegionId, onChange) {
  const select = document.getElementById("region-select");
  if (!select) return;

  select.replaceChildren();
  const selectable = Object.entries(catalog.regions)
    .filter(([, region]) => Object.keys(region.layers || {}).length > 0)
    .sort(([, a], [, b]) => a.title.localeCompare(b.title));

  const groups = new Map();
  for (const [id, region] of selectable) {
    const groupKey = region.parent || id;
    if (!groups.has(groupKey)) {
      groups.set(groupKey, []);
    }
    groups.get(groupKey).push({ id, title: region.title });
  }

  for (const [groupKey, items] of [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const optgroup = document.createElement("optgroup");
    const parentRegion = catalog.regions[groupKey];
    optgroup.label = parentRegion?.title || groupKey.replace(/_/g, " ");
    for (const item of items.sort((a, b) => a.title.localeCompare(b.title))) {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.title;
      if (item.id === currentRegionId) {
        option.selected = true;
      }
      optgroup.appendChild(option);
    }
    select.appendChild(optgroup);
  }

  select.addEventListener("change", () => {
    onChange(select.value);
  });
}

export function buildSearchPanel(onSearch, onSelect) {
  const input = document.getElementById("map-search");
  const resultsEl = document.getElementById("search-results");
  if (!input || !resultsEl) return;

  function renderResults(results) {
    resultsEl.replaceChildren();
    if (!results.length) {
      resultsEl.hidden = true;
      return;
    }
    for (const result of results) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-result";

      const title = document.createElement("div");
      title.className = "search-result-title";
      title.textContent = result.title;

      const meta = document.createElement("div");
      meta.className = "search-result-meta";
      meta.textContent = result.subtitle;

      button.append(title, meta);
      button.addEventListener("click", () => {
        resultsEl.hidden = true;
        onSelect(result);
      });
      resultsEl.appendChild(button);
    }
    resultsEl.hidden = false;
  }

  input.oninput = () => {
    const query = input.value.trim();
    if (query.length < 2) {
      renderResults([]);
      return;
    }
    renderResults(onSearch(query));
  };
}

export function setMapTitle(title) {
  const heading = document.getElementById("map-title");
  if (heading) {
    heading.textContent = title;
  }
  document.title = `${title} — Power Map`;
}

export function fitRegionBounds(map, bounds) {
  if (!bounds || bounds.length !== 2) return;
  const [[south, west], [north, east]] = bounds;
  map.fitBounds([[south, west], [north, east]], { padding: [20, 20] });
}
