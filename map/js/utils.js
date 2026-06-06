export function parseVoltageKv(props) {
  if (props.voltage_kv != null && props.voltage_kv !== "") {
    const parsed = Number(props.voltage_kv);
    if (!Number.isNaN(parsed)) return parsed;
  }
  const raw = props.voltage;
  if (raw == null || raw === "") return null;
  const text = String(raw).toLowerCase().replace(/\s/g, "");
  const tokens = text.split(/[;,/|]+/).filter(Boolean);
  const values = [];
  for (const token of tokens) {
    let value = token;
    let multiplier = 1;
    if (value.endsWith("kv")) {
      value = value.slice(0, -2);
    } else if (value.endsWith("v")) {
      value = value.slice(0, -1);
      multiplier = 0.001;
    }
    const match = value.match(/\d+(?:\.\d+)?/);
    if (!match) continue;
    let number = Number(match[0]) * multiplier;
    if (multiplier === 1 && number > 1200) number /= 1000;
    values.push(number);
  }
  return values.length ? Math.max(...values) : null;
}

export function parseCapacityToMw(value) {
  if (value == null || value === "") return null;
  if (Array.isArray(value)) {
    const parsed = value.map(parseCapacityToMw).filter((item) => item != null);
    return parsed.length ? parsed.reduce((sum, item) => sum + item, 0) : null;
  }
  const text = String(value).toLowerCase().replace(/\s/g, "");
  const tokens = text.split(";");
  let total = 0;
  let found = false;
  for (const token of tokens) {
    if (!token) continue;
    let multiplier = 1;
    let part = token;
    if (part.endsWith("gw")) {
      multiplier = 1000;
      part = part.slice(0, -2);
    } else if (part.endsWith("mw")) {
      part = part.slice(0, -2);
    } else if (part.endsWith("kw")) {
      multiplier = 0.001;
      part = part.slice(0, -2);
    } else if (part.endsWith("w")) {
      multiplier = 1e-6;
      part = part.slice(0, -1);
    }
    part = part.replace(",", ".");
    const match = part.match(/\d+(?:\.\d+)?/);
    if (!match) continue;
    total += Number(match[0]) * multiplier;
    found = true;
  }
  return found ? total : null;
}

export function ringCentroid(ring) {
  let lon = 0;
  let lat = 0;
  const count = ring.length - 1;
  if (count <= 0) return null;
  for (let i = 0; i < count; i += 1) {
    lon += ring[i][0];
    lat += ring[i][1];
  }
  return [lon / count, lat / count];
}

export function featureToPoint(feature) {
  const geom = feature.geometry;
  if (!geom) return null;
  if (geom.type === "Point") {
    return { ...feature, geometry: geom };
  }
  if (geom.type === "Polygon") {
    const center = ringCentroid(geom.coordinates[0]);
    return center ? { ...feature, geometry: { type: "Point", coordinates: center } } : null;
  }
  if (geom.type === "MultiPolygon" && geom.coordinates.length) {
    const center = ringCentroid(geom.coordinates[0][0]);
    return center ? { ...feature, geometry: { type: "Point", coordinates: center } } : null;
  }
  return null;
}

export function isPolygonGeometry(geometry) {
  return geometry && (geometry.type === "Polygon" || geometry.type === "MultiPolygon");
}

export function getLatLon(props, feature) {
  if (props.latitude != null && props.longitude != null) {
    return [Number(props.latitude), Number(props.longitude)];
  }
  const pointFeature = featureToPoint(feature);
  if (!pointFeature) return null;
  const [lon, lat] = pointFeature.geometry.coordinates;
  return [lat, lon];
}

export function boundsFromGeoJson(data) {
  if (!data?.features?.length) return null;
  const temp = L.geoJSON(data);
  const bounds = temp.getBounds();
  return bounds?.isValid() ? bounds : null;
}

export function pointInRing(lat, lon, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect = ((yi > lat) !== (yj > lat))
      && (lon < ((xj - xi) * (lat - yi)) / (yj - yi + 0.0) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

export function pointInPolygonGeometry(lat, lon, geometry) {
  if (!geometry) return false;
  if (geometry.type === "Polygon") {
    const [outer, ...holes] = geometry.coordinates;
    if (!pointInRing(lat, lon, outer)) return false;
    return holes.every((hole) => !pointInRing(lat, lon, hole));
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.some(([outer, ...holes]) => {
      if (!pointInRing(lat, lon, outer)) return false;
      return holes.every((hole) => !pointInRing(lat, lon, hole));
    });
  }
  return false;
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
