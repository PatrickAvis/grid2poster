const DEFAULT_FUEL_TYPES = [
  { id: "nuclear", label: "Nuclear", color: "#6a1b9a", keywords: ["nuclear"] },
  { id: "gas", label: "Gas", color: "#e65100", keywords: ["natural gas", "gas"] },
  { id: "coal", label: "Coal", color: "#4e342e", keywords: ["lignite", "coal"] },
  { id: "wind", label: "Wind", color: "#03a9f4", keywords: ["wind"] },
  { id: "solar", label: "Solar", color: "#f9a825", keywords: ["photovoltaic", "solar", "pv"] },
  { id: "hydro_non_pumped", label: "Non-pumped hydro", color: "#00897b", keywords: ["hydro", "water"] },
  { id: "hydro_pumped", label: "Pumped storage", color: "#004d40", keywords: ["pumped storage", "pumped-storage"] },
  { id: "biomass", label: "Biomass", color: "#558b2f", keywords: ["biomass", "wood"] },
  { id: "oil", label: "Oil", color: "#5d4037", keywords: ["diesel", "petroleum", "oil"] },
  { id: "other", label: "Other", color: "#757575", keywords: [] },
];

let fuelTypes = DEFAULT_FUEL_TYPES;

export async function loadFuelTypes(url = "../data/shared/fuel_types.json") {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (Array.isArray(data.types) && data.types.length) {
      fuelTypes = data.types;
    }
  } catch (error) {
    console.warn("Fuel taxonomy not loaded; using defaults.", error);
  }
  return fuelTypes;
}

export function fuelTypeOrder() {
  return fuelTypes.map((item) => item.id);
}

export function fuelTypeColor(id) {
  return fuelTypes.find((item) => item.id === id)?.color
    || fuelTypes.find((item) => item.id === "other")?.color
    || "#757575";
}

export function fuelTypeLabel(id) {
  return fuelTypes.find((item) => item.id === id)?.label || id;
}

export function hasFuelType(id) {
  return fuelTypes.some((item) => item.id === id);
}

function sourceTokens(source) {
  if (!source) return [];
  if (Array.isArray(source)) return source.flatMap(sourceTokens);
  return String(source)
    .toLowerCase()
    .split(/[;,/|]+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function bucketFuelSource(source) {
  for (const token of sourceTokens(source)) {
    for (const fuelType of fuelTypes) {
      for (const keyword of fuelType.keywords || []) {
        if (token.includes(String(keyword).toLowerCase())) {
          return fuelType.id;
        }
      }
    }
  }
  return "other";
}

export function bucketFuelProperties(source, ...contextFields) {
  const context = contextFields
    .filter(Boolean)
    .map((value) => String(value).toLowerCase())
    .join(" ");
  if (context) {
    for (const fuelType of fuelTypes) {
      for (const keyword of fuelType.name_keywords || []) {
        if (context.includes(String(keyword).toLowerCase())) {
          return fuelType.id;
        }
      }
    }
  }
  return bucketFuelSource(source);
}
