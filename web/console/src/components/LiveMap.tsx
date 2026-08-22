import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { Protocol } from "pmtiles";
import type { GeoFeatureCollection, MapPayload, PublicConfig } from "../lib/api";
import "maplibre-gl/dist/maplibre-gl.css";

if (!maplibregl.getWorkerUrl()) {
  maplibregl.setWorkerUrl(workerUrl);
}

let protocolRegistered = false;
const seenAlertIds = new Set<number>();
let seededAlerts = false;

function registerPmtiles() {
  if (protocolRegistered) return;
  maplibregl.addProtocol("pmtiles", new Protocol().tile);
  protocolRegistered = true;
}

function ringCenter(ring: unknown): [number, number] | null {
  if (!Array.isArray(ring) || ring.length === 0) return null;
  let x = 0;
  let y = 0;
  let n = 0;
  for (const pair of ring) {
    if (!Array.isArray(pair) || pair.length < 2) continue;
    x += Number(pair[0]);
    y += Number(pair[1]);
    n += 1;
  }
  if (!n) return null;
  return [x / n, y / n];
}

function featureCenter(feature: GeoFeatureCollection["features"][number]): [number, number] | null {
  const geom = feature.geometry as { type?: string; coordinates?: unknown };
  if (geom.type === "Point" && Array.isArray(geom.coordinates)) {
    return [Number(geom.coordinates[0]), Number(geom.coordinates[1])];
  }
  if (geom.type === "Polygon" && Array.isArray(geom.coordinates)) {
    return ringCenter(geom.coordinates[0]);
  }
  if (geom.type === "MultiPolygon" && Array.isArray(geom.coordinates)) {
    const first = geom.coordinates[0];
    return Array.isArray(first) ? ringCenter(first[0]) : null;
  }
  return null;
}

function baseStyle(): Record<string, unknown> {
  return {
    version: 8,
    glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
    sources: {},
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#1e2a3a" },
      },
    ],
  };
}

function addPlaceNames(map: maplibregl.Map) {
  if (!map.getSource("basemap") || map.getLayer("places")) return;
  map.addLayer({
    id: "places",
    type: "symbol",
    source: "basemap",
    "source-layer": "places",
    layout: {
      "text-field": ["coalesce", ["get", "name:en"], ["get", "name"], ""],
      "text-font": ["Noto Sans Regular"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 5, 11, 10, 14],
      "text-max-width": 8,
      "text-optional": true,
      "symbol-sort-key": ["coalesce", ["get", "sort_key"], 0],
    },
    paint: {
      "text-color": "#e8ebf0",
      "text-halo-color": "#0b0d10",
      "text-halo-width": 1.4,
    },
  });
  map.addLayer({
    id: "water-label",
    type: "symbol",
    source: "basemap",
    "source-layer": "water",
    minzoom: 6,
    layout: {
      "text-field": ["coalesce", ["get", "name:en"], ["get", "name"], ""],
      "text-font": ["Noto Sans Regular"],
      "text-size": 11,
      "text-optional": true,
    },
    paint: {
      "text-color": "#8aa0b8",
      "text-halo-color": "#0b0d10",
      "text-halo-width": 1,
    },
  });
  map.addLayer({
    id: "roads-label",
    type: "symbol",
    source: "basemap",
    "source-layer": "roads",
    minzoom: 9,
    layout: {
      "symbol-placement": "line",
      "text-field": ["coalesce", ["get", "name:en"], ["get", "name"], ""],
      "text-font": ["Noto Sans Regular"],
      "text-size": 10,
      "text-optional": true,
    },
    paint: {
      "text-color": "#9aa3b2",
      "text-halo-color": "#0b0d10",
      "text-halo-width": 1,
    },
  });
}

function addUnitLayers(
  map: maplibregl.Map,
  units: GeoFeatureCollection,
  onUnit: ((id: number) => void) | undefined,
) {
  if (!map.getSource("units")) {
    map.addSource("units", { type: "geojson", data: units as never });
  }
  if (!map.getLayer("units-fill")) {
    map.addLayer({
      id: "units-fill",
      type: "fill",
      source: "units",
      paint: {
        "fill-color": [
          "case",
          ["==", ["typeof", ["get", "recipient_reach_pct"]], "number"],
          [
            "interpolate",
            ["linear"],
            ["get", "recipient_reach_pct"],
            0,
            "#ff6b6b",
            50,
            "#ffa94d",
            100,
            "#51cf66",
          ],
          "#3d8fd1",
        ],
        "fill-opacity": 0.62,
      },
    });
  }
  if (!map.getLayer("units-line")) {
    map.addLayer({
      id: "units-line",
      type: "line",
      source: "units",
      paint: { "line-color": "#f4f7fb", "line-width": 1.8 },
    });
  }
  if (onUnit) {
    map.on("click", "units-fill", (event: maplibregl.MapLayerMouseEvent) => {
      const raw = event.features?.[0]?.properties?.unit_id;
      const id = typeof raw === "number" ? raw : Number(raw);
      if (Number.isFinite(id)) onUnit(id);
    });
  }
}

async function attachBasemap(
  map: maplibregl.Map,
  cfg: PublicConfig | null,
  payload: MapPayload,
): Promise<void> {
  const source = String(cfg?.["map.tile_source"] ?? payload.tile_source);
  if (source !== "pmtiles_local" || map.getSource("basemap") || map.getSource("openmaptiles")) return;
  const probe = await fetch("/tiles/setu-basemap.pmtiles", {
    headers: { Range: "bytes=0-6" },
  });
  if (!probe.ok && probe.status !== 206) return;
  const range = probe.headers.get("content-range") ?? "";
  const total = range.includes("/") ? Number(range.split("/").pop()) : NaN;
  const bytes = Number.isFinite(total) ? total : Number(probe.headers.get("content-length") || 0);
  const minBytes = Number(cfg?.["map.pmtiles_min_bytes"] ?? payload.pmtiles_min_bytes);
  if (!Number.isFinite(minBytes) || !(bytes > minBytes)) return;
  map.addSource("basemap", {
    type: "vector",
    url: "pmtiles:///tiles/setu-basemap.pmtiles",
    attribution: "© OpenStreetMap contributors",
  });
  const before = map.getLayer("units-fill") ? "units-fill" : undefined;
  map.addLayer(
    {
      id: "earth",
      type: "fill",
      source: "basemap",
      "source-layer": "earth",
      paint: { "fill-color": "#2d3d52" },
    },
    before,
  );
  map.addLayer(
    {
      id: "water",
      type: "fill",
      source: "basemap",
      "source-layer": "water",
      paint: { "fill-color": "#15202b" },
    },
    before,
  );
  map.addLayer(
    {
      id: "roads",
      type: "line",
      source: "basemap",
      "source-layer": "roads",
      paint: { "line-color": "#8b96a8", "line-width": 1.1 },
    },
    before,
  );
}

function extendPair(
  bounds: [number, number, number, number] | null,
  lon: number,
  lat: number,
): [number, number, number, number] {
  if (!bounds) return [lon, lat, lon, lat];
  return [
    Math.min(bounds[0], lon),
    Math.min(bounds[1], lat),
    Math.max(bounds[2], lon),
    Math.max(bounds[3], lat),
  ];
}

function collectionBounds(fc: GeoFeatureCollection): [number, number, number, number] | null {
  let bounds: [number, number, number, number] | null = null;
  for (const feature of fc.features) {
    const geom = feature.geometry as { type?: string; coordinates?: unknown };
    if (geom.type === "Point" && Array.isArray(geom.coordinates) && geom.coordinates.length >= 2) {
      bounds = extendPair(bounds, Number(geom.coordinates[0]), Number(geom.coordinates[1]));
      continue;
    }
    const rings: unknown[] = [];
    if (geom.type === "Polygon" && Array.isArray(geom.coordinates)) rings.push(geom.coordinates[0]);
    if (geom.type === "MultiPolygon" && Array.isArray(geom.coordinates)) {
      for (const poly of geom.coordinates) {
        if (Array.isArray(poly)) rings.push(poly[0]);
      }
    }
    for (const ring of rings) {
      if (!Array.isArray(ring)) continue;
      for (const pair of ring) {
        if (!Array.isArray(pair) || pair.length < 2) continue;
        const lon = Number(pair[0]);
        const lat = Number(pair[1]);
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
        bounds = extendPair(bounds, lon, lat);
      }
    }
  }
  return bounds;
}

function fitFeatures(map: maplibregl.Map, payload: MapPayload) {
  const bounds = collectionBounds(payload.units) ?? collectionBounds(payload.alerts);
  if (!bounds) return;
  const [minLon, minLat, maxLon, maxLat] = bounds;
  if (minLon === maxLon && minLat === maxLat) {
    map.jumpTo({ center: [minLon, minLat], zoom: 10 });
    return;
  }
  map.fitBounds(
    [
      [minLon, minLat],
      [maxLon, maxLat],
    ],
    { padding: 36, maxZoom: 11, duration: 0 },
  );
}

function placeLabels(map: maplibregl.Map, payload: MapPayload, markers: maplibregl.Marker[]) {
  while (markers.length) {
    markers.pop()?.remove();
  }
  const features = payload.units.features;
  if (features.length > 80) return;
  for (const feature of features) {
    const name = feature.properties?.name;
    if (typeof name !== "string" || !name.trim()) continue;
    const center = featureCenter(feature);
    if (!center) continue;
    const el = document.createElement("div");
    const level = Number(feature.properties?.level);
    el.className = level >= 5 ? "map-unit-label map-unit-label--local" : "map-unit-label";
    el.textContent = name;
    markers.push(new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(center).addTo(map));
  }
}

function ping(map: maplibregl.Map, lngLat: [number, number], severity: string) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const el = document.createElement("div");
  el.className = `radar-ping radar-ping--${severity}`;
  const marker = new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(lngLat).addTo(map);
  el.addEventListener("animationend", () => marker.remove(), { once: true });
}

function applySources(map: maplibregl.Map, payload: MapPayload, pingNew: boolean) {
  const units = map.getSource("units") as maplibregl.GeoJSONSource | undefined;
  if (units) units.setData(payload.units as never);
  if (!pingNew) return;
  const incoming: number[] = [];
  for (const feature of payload.alerts.features) {
    const id = feature.properties?.alert_id;
    if (typeof id === "number") incoming.push(id);
  }
  if (!seededAlerts) {
    incoming.forEach((id) => seenAlertIds.add(id));
    seededAlerts = true;
    return;
  }
  for (const feature of payload.alerts.features) {
    const id = feature.properties?.alert_id;
    if (typeof id !== "number" || seenAlertIds.has(id)) continue;
    seenAlertIds.add(id);
    const center = featureCenter(feature);
    if (!center) continue;
    const severity = String(feature.properties?.severity ?? "");
    if (!severity) continue;
    ping(map, center, severity);
  }
}

export function LiveMap({
  payload,
  cfg,
  onUnit,
  draw,
  onPolygon,
}: {
  payload: MapPayload | null;
  cfg: PublicConfig | null;
  onUnit?: (id: number) => void;
  draw?: boolean;
  onPolygon?: (geojson: Record<string, unknown>) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const points = useRef<number[][]>([]);
  const onUnitRef = useRef(onUnit);
  const onPolygonRef = useRef(onPolygon);
  const labelMarkers = useRef<maplibregl.Marker[]>([]);
  onUnitRef.current = onUnit;
  onPolygonRef.current = onPolygon;

  useEffect(() => {
    if (!ref.current || !payload || mapRef.current) return;
    registerPmtiles();
    let observer: ResizeObserver | null = null;
    const container = ref.current;
    const first = payload;
    const bootCfg = cfg;

    const map = new maplibregl.Map({
      container,
      style: baseStyle() as never,
      center: first.center,
      zoom: first.zoom,
      attributionControl: { compact: true },
    });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      observer = new ResizeObserver(() => map.resize());
      observer.observe(container);
      map.on("load", () => {
        map.resize();
        addUnitLayers(map, first.units, draw ? undefined : (id) => onUnitRef.current?.(id));
        applySources(map, first, !draw);
        fitFeatures(map, first);
        placeLabels(map, first, labelMarkers.current);
        void attachBasemap(map, bootCfg, first)
          .then(() => {
            try {
              addPlaceNames(map);
            } catch {
              return;
            }
          })
          .catch(() => undefined);
      });
      if (draw) {
        map.on("click", (event: maplibregl.MapMouseEvent) => {
          points.current.push([event.lngLat.lng, event.lngLat.lat]);
          const ring = [...points.current];
          if (ring.length > 2) {
            ring.push(ring[0]);
            const geojson = { type: "Polygon", coordinates: [ring] };
            onPolygonRef.current?.(geojson);
            if (map.getSource("draft")) {
              (map.getSource("draft") as maplibregl.GeoJSONSource).setData({
                type: "Feature",
                geometry: geojson,
                properties: {},
              } as never);
            } else if (map.isStyleLoaded()) {
              map.addSource("draft", {
                type: "geojson",
                data: { type: "Feature", geometry: geojson, properties: {} } as never,
              });
              map.addLayer({
                id: "draft-fill",
                type: "fill",
                source: "draft",
                paint: { "fill-color": "#4dabf7", "fill-opacity": 0.2 },
              });
            }
          }
        });
      }

    return () => {
      observer?.disconnect();
    };
  }, [Boolean(payload), draw]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !payload) return;
    if (map.isStyleLoaded()) {
      applySources(map, payload, !draw);
      placeLabels(map, payload, labelMarkers.current);
    }
  }, [payload, draw]);

  useEffect(() => {
    return () => {
      while (labelMarkers.current.length) {
        labelMarkers.current.pop()?.remove();
      }
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={ref} className="live-map" role="img" aria-label="Map of villages" />;
}
