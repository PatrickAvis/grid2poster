import {
  LINE_TYPE_COLORS,
  LINE_TYPE_LABELS,
  LINE_TYPE_ORDER,
} from "./constants.js";
import { fuelTypeColor, fuelTypeLabel, fuelTypeOrder } from "./fuelTypes.js";

export function buildLineLegend(
  lineBucketGroups,
  lineBucketVisibility,
  setLineBucketVisible,
  options = {},
) {
  const legendEl = document.getElementById("line-legend");
  const listEl = document.getElementById("line-legend-list");
  listEl.replaceChildren();

  const buckets = LINE_TYPE_ORDER.filter((bucket) => lineBucketGroups[bucket]);

  for (const bucket of buckets) {
    const label = document.createElement("label");
    label.className = "plant-legend-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = lineBucketVisibility[bucket] !== false;
    checkbox.addEventListener("change", (event) => {
      setLineBucketVisible(bucket, event.target.checked);
    });

    const swatch = document.createElement("span");
    swatch.className = "line-swatch";
    swatch.style.background = LINE_TYPE_COLORS[bucket];

    const text = document.createTextNode(LINE_TYPE_LABELS[bucket]);

    label.append(checkbox, swatch, text);
    listEl.appendChild(label);
  }

  if (buckets.length && options.onWidthScaleChange) {
    const widthLabel = document.createElement("label");
    widthLabel.className = "legend-control";

    const text = document.createElement("span");
    text.textContent = "Line thickness x";

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0.5";
    input.max = "4";
    input.step = "0.25";
    input.value = String(options.widthScale ?? 1);
    input.title = "Transmission line width multiplier";
    input.addEventListener("change", (event) => {
      options.onWidthScaleChange(Number(event.target.value));
    });

    widthLabel.append(text, input);
    listEl.appendChild(widthLabel);
  }

  legendEl.hidden = buckets.length === 0;
}

export function setLineLegendVisible(visible, lineBucketGroups) {
  const legendEl = document.getElementById("line-legend");
  if (!legendEl) return;
  legendEl.hidden = !visible || Object.keys(lineBucketGroups).length === 0;
}

export function buildPlantLegend(
  plantBucketGroups,
  plantBucketVisibility,
  setPlantBucketVisible,
  options = {},
) {
  const legendEl = document.getElementById("plant-legend");
  const listEl = document.getElementById("plant-legend-list");
  listEl.replaceChildren();

  const buckets = [
    ...fuelTypeOrder().filter((bucket) => plantBucketGroups[bucket]),
    ...Object.keys(plantBucketGroups)
      .filter((bucket) => !fuelTypeOrder().includes(bucket))
      .sort(),
  ];
  let turbineToggleAdded = false;

  for (const bucket of buckets) {
    const label = document.createElement("label");
    label.className = "plant-legend-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = plantBucketVisibility[bucket] !== false;
    checkbox.addEventListener("change", (event) => {
      setPlantBucketVisible(bucket, event.target.checked);
    });

    const swatch = document.createElement("span");
    swatch.className = "plant-swatch";
    swatch.style.background = fuelTypeColor(bucket);

    const text = document.createTextNode(fuelTypeLabel(bucket));

    label.append(checkbox, swatch, text);
    listEl.appendChild(label);

    if (bucket.startsWith("wind") && options.onTurbinesToggle && !turbineToggleAdded) {
      turbineToggleAdded = true;
      const subLabel = document.createElement("label");
      subLabel.className = "plant-legend-item plant-legend-subitem";

      const subCheckbox = document.createElement("input");
      subCheckbox.type = "checkbox";
      subCheckbox.id = "toggle-wind-turbines";
      subCheckbox.checked = options.turbinesEnabled ?? false;
      subCheckbox.addEventListener("change", (event) => {
        options.onTurbinesToggle(event.target.checked);
      });

      const subText = document.createTextNode(
        `Individual turbines (zoom ${options.turbineMinZoom ?? 9}+)`,
      );

      subLabel.append(subCheckbox, subText);
      listEl.appendChild(subLabel);
    }
  }

  legendEl.hidden = buckets.length === 0;
}

export function setPlantLegendVisible(visible, plantBucketGroups) {
  const legendEl = document.getElementById("plant-legend");
  if (!legendEl) return;
  legendEl.hidden = !visible || Object.keys(plantBucketGroups).length === 0;
}
