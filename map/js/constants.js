export const PLANT_COLORS = {
  solar: "#f9a825",
  wind: "#0288d1",
  hydro: "#00695c",
  nuclear: "#6a1b9a",
  coal: "#4e342e",
  gas: "#ef6c00",
  oil: "#5d4037",
  biomass: "#558b2f",
  other: "#757575",
};

export const PLANT_BUCKET_LABELS = {
  solar: "Solar",
  wind: "Wind",
  hydro: "Hydro",
  nuclear: "Nuclear",
  coal: "Coal",
  gas: "Gas",
  oil: "Oil",
  biomass: "Biomass",
  other: "Other",
};

export const LINE_TYPE_COLORS = {
  ehv: "#7b1fa2",
  hv: "#d32f2f",
  mv: "#f57c00",
  lv: "#1976d2",
  cable: "#00838f",
  interconnector: "#5d4037",
};

export const LINE_TYPE_LABELS = {
  ehv: "Extra-high voltage (500 kV+)",
  hv: "High voltage (300-499 kV, incl. 400 kV)",
  mv: "Medium voltage (150-299 kV, incl. 275 kV)",
  lv: "Low / unknown (<150 kV)",
  cable: "Cables",
  interconnector: "Interconnectors / subsea cables",
};

export const LINE_TYPE_ORDER = ["ehv", "hv", "mv", "lv", "cable", "interconnector"];

export const PLANT_BUCKET_ORDER = [
  "nuclear",
  "gas",
  "coal",
  "wind",
  "solar",
  "hydro",
  "biomass",
  "oil",
  "other",
];

export const SUBSTATION_COLORS = {
  transmission: "#c62828",
  distribution: "#1565c0",
  converter: "#6a1b9a",
  traction: "#455a64",
  other: "#78909c",
};

export const ZONE_COLORS = {
  dno: "#7e57c2",
  gsp: "#26a69a",
};

export const PLANT_CAP_REF_MW = 2000;
export const PLANT_MARKER_MIN_RADIUS = 3;
export const PLANT_MARKER_MAX_RADIUS = 16;
export const PLANT_MARKER_FALLBACK_RADIUS = 4;
