import { useEffect, useRef } from "react";
import maplibregl, { type Map as MapInstance } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./RouteMap.css";

type Checkpoint = {
  latitude: number;
  longitude: number;
  eta: string;
  distance_miles?: number;
  risk?: { level?: string };
  weather?: Record<string, unknown>;
};
type Route = {
  id: string;
  geometry: { type: string; coordinates: number[][] };
  checkpoints: Checkpoint[];
  safety_rank?: number;
};
export type CorridorPoint = {
  latitude: number;
  longitude: number;
  hours: {
    score: number;
    risk: string;
    wind_mph?: number;
    rain_in_per_hr?: number;
    snow_in_per_hr?: number;
  }[];
};
type Props = {
  corridorPoints?: CorridorPoint[];
  forecastHour?: number;
  showHeatmap?: boolean;
  routes: Route[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  selectedCheckpointIndex: number | null;
  onCheckpointSelect: (index: number) => void;
};

const colors = ["#4c9bff", "#f7b75e", "#a99df7"];
const styleUrl =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function validCoordinates(route: Route) {
  return (
    route.geometry?.coordinates?.filter(
      (point) =>
        point.length >= 2 &&
        Number.isFinite(point[0]) &&
        Number.isFinite(point[1]) &&
        Math.abs(point[0]) <= 180 &&
        Math.abs(point[1]) <= 90,
    ) ?? []
  );
}

// Render contiguous road segments with risk category and within-category weather intensity.
// Intensity varies with actual hourly wind/rain/snow measurements, even if risk stays Low.
function corridorGeoJSON(
  route: Route | undefined,
  points: CorridorPoint[],
  hour: number,
  visible: boolean,
) {
  const coordinates = route ? validCoordinates(route) : [];
  const features: {
    type: "Feature";
    geometry: { type: "LineString"; coordinates: number[][] };
    properties: { score: number; intensity: number };
  }[] = [];
  if (!visible || coordinates.length < 2 || !points.length) {
    return { type: "FeatureCollection" as const, features };
  }
  const nearestWeather = (coordinate: number[]) => {
    let best = Infinity;
    let weather: CorridorPoint["hours"][number] | undefined;
    for (const point of points) {
      const dx =
        (coordinate[0] - point.longitude) *
        Math.cos((coordinate[1] * Math.PI) / 180);
      const dy = coordinate[1] - point.latitude;
      const distance = dx * dx + dy * dy;
      if (distance < best) {
        best = distance;
        weather = point.hours[hour];
      }
    }
    const score = Math.max(0, Math.min(4, Math.round(weather?.score ?? 0)));
    // Relative to the first risk thresholds. These ratios affect only the
    // intensity of the visualization, never the safety classification.
    const wind = Math.max(0, weather?.wind_mph ?? 0) / 25;
    const rain = Math.max(0, weather?.rain_in_per_hr ?? 0) / 0.1;
    const snow = Math.max(0, weather?.snow_in_per_hr ?? 0) / 0.5;
    const intensity = Math.max(0.12, Math.min(1, Math.max(wind, rain, snow)));
    return { score, intensity };
  };
  const stride = Math.max(1, Math.ceil((coordinates.length - 1) / 1800));
  for (let i = 0; i < coordinates.length - 1; i += stride) {
    const segment = coordinates.slice(
      i,
      Math.min(i + stride + 1, coordinates.length),
    );
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: segment },
      properties: nearestWeather(segment[Math.floor(segment.length / 2)]),
    });
  }
  return { type: "FeatureCollection" as const, features };
}

export default function RouteMap({
  routes,
  selectedId,
  onSelect,
  selectedCheckpointIndex,
  onCheckpointSelect,
  corridorPoints = [],
  forecastHour = 0,
  showHeatmap = false,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapInstance | null>(null);
  const selectedRef = useRef(selectedId);
  const selectRef = useRef(onSelect);
  const markers = useRef<maplibregl.Marker[]>([]);
  const checkpointMarkers = useRef<maplibregl.Marker[]>([]);
  const checkpointSelectRef = useRef(onCheckpointSelect);
  const routesRef = useRef(routes);
  const heatmapRef = useRef({ corridorPoints, forecastHour, showHeatmap });

  useEffect(() => {
    heatmapRef.current = { corridorPoints, forecastHour, showHeatmap };
    checkpointSelectRef.current = onCheckpointSelect;
    selectedRef.current = selectedId;
    selectRef.current = onSelect;
    routesRef.current = routes;
  }, [
    onCheckpointSelect,
    selectedId,
    onSelect,
    routes,
    corridorPoints,
    forecastHour,
    showHeatmap,
  ]);

  useEffect(() => {
    if (!container.current) return;
    const instance = new maplibregl.Map({
      container: container.current,
      style: styleUrl,
      center: [-104.9903, 39.7392],
      zoom: 8,
      attributionControl: { compact: true },
    });
    map.current = instance;
    instance.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );

    function drawHeatmap() {
      const {
        corridorPoints: points,
        forecastHour: hour,
        showHeatmap: visible,
      } = heatmapRef.current;
      const selected =
        routesRef.current.find((route) => route.id === selectedRef.current) ??
        routesRef.current[0];
      const data = corridorGeoJSON(selected, points, hour, visible);
      const source = instance.getSource("corridor-weather") as
        | maplibregl.GeoJSONSource
        | undefined;
      if (source) source.setData(data);
      else {
        instance.addSource("corridor-weather", { type: "geojson", data });
        const riskColor: maplibregl.ExpressionSpecification = [
          "match",
          ["get", "score"],
          0,
          "#287a65",
          1,
          "#e0c052",
          2,
          "#f28a43",
          3,
          "#e84d50",
          4,
          "#ae1c65",
          "#287a65",
        ];
        const intensityOpacity: maplibregl.ExpressionSpecification = [
          "interpolate",
          ["linear"],
          ["get", "intensity"],
          0,
          0.18,
          0.5,
          0.45,
          1,
          0.85,
        ];
        // Diffuse outer band reads as a weather corridor, not a highlighted road.
        instance.addLayer({
          id: "corridor-weather-atmosphere",
          type: "line",
          source: "corridor-weather",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": riskColor,
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              5,
              32,
              8,
              55,
              11,
              90,
            ],
            "line-blur": 20,
            "line-opacity": intensityOpacity,
          },
        });
        instance.addLayer({
          id: "corridor-weather-halo",
          type: "line",
          source: "corridor-weather",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": riskColor,
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              5,
              20,
              8,
              38,
              11,
              65,
            ],
            "line-blur": 14,
            "line-opacity": intensityOpacity,
          },
        });
        instance.addLayer({
          id: "corridor-weather-core",
          type: "line",
          source: "corridor-weather",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": riskColor,
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              5,
              9,
              8,
              18,
              11,
              30,
            ],
            "line-blur": 5,
            "line-opacity": intensityOpacity,
          },
        });
        routesRef.current.forEach((_, index) => {
          if (instance.getLayer(`route-line-${index}`))
            instance.moveLayer(`route-line-${index}`);
        });
      }
    }

    function drawRoutes() {
      const currentRoutes = routesRef.current;
      currentRoutes.forEach((route, index) => {
        const coordinates = validCoordinates(route);
        if (coordinates.length < 2) return;
        const sourceId = `route-${index}`;
        if (instance.getSource(sourceId)) return;
        instance.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates },
          },
        });
        instance.addLayer({
          id: `route-halo-${index}`,
          type: "line",
          source: sourceId,
          paint: {
            "line-color": colors[index % colors.length],
            "line-width": 11,
            "line-opacity": 0.14,
            "line-blur": 5,
          },
        });
        instance.addLayer({
          id: `route-line-${index}`,
          type: "line",
          source: sourceId,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": colors[index % colors.length],
            "line-width": 3,
            "line-opacity": 0.6,
          },
        });
        instance.on("click", `route-line-${index}`, () =>
          selectRef.current(route.id),
        );
        instance.on("mouseenter", `route-line-${index}`, () => {
          instance.getCanvas().style.cursor = "pointer";
        });
        instance.on("mouseleave", `route-line-${index}`, () => {
          instance.getCanvas().style.cursor = "";
        });
      });
      drawHeatmap();
      highlight();
      const bounds = new maplibregl.LngLatBounds();
      currentRoutes.forEach((route) =>
        validCoordinates(route).forEach((point) =>
          bounds.extend([point[0], point[1]]),
        ),
      );
      if (!bounds.isEmpty())
        instance.fitBounds(bounds, { padding: 75, maxZoom: 11, duration: 900 });
    }

    function highlight() {
      const currentRoutes = routesRef.current;
      currentRoutes.forEach((route, index) => {
        if (!instance.getLayer(`route-line-${index}`)) return;
        const active = route.id === selectedRef.current;
        instance.setPaintProperty(
          `route-line-${index}`,
          "line-width",
          active ? 6 : 3,
        );
        instance.setPaintProperty(
          `route-line-${index}`,
          "line-opacity",
          active ? 1 : 0.35,
        );
        instance.setPaintProperty(
          `route-halo-${index}`,
          "line-opacity",
          active ? 0.35 : 0.08,
        );
      });
      markers.current.forEach((marker) => marker.remove());
      markers.current = [];
      checkpointMarkers.current = [];
      const selected =
        currentRoutes.find((route) => route.id === selectedRef.current) ??
        currentRoutes[0];
      if (!selected) return;
      const coords = validCoordinates(selected);
      if (coords.length < 2) return;
      const points = selected.checkpoints?.length
        ? selected.checkpoints.map(
            (checkpoint) =>
              [checkpoint.longitude, checkpoint.latitude] as [number, number],
          )
        : [];
      points.forEach((point, index) => {
        if (!Number.isFinite(point[0]) || !Number.isFinite(point[1])) return;
        const element = document.createElement("div");
        element.className = "route-checkpoint-marker";
        element.setAttribute("aria-label", `Checkpoint ${index + 1}`);
        const popup = new maplibregl.Popup({ offset: 15 }).setText(
          `Checkpoint ${index + 1} · ${new Date(selected.checkpoints[index].eta).toLocaleString()}`,
        );
        element.addEventListener("click", () =>
          checkpointSelectRef.current(index),
        );
        const marker = new maplibregl.Marker({ element })
          .setLngLat(point)
          .setPopup(popup)
          .addTo(instance);
        markers.current.push(marker);
        checkpointMarkers.current.push(marker);
      });
      [
        [coords[0], "START"],
        [coords[coords.length - 1], "FINISH"],
      ].forEach(([point, label]) => {
        const element = document.createElement("div");
        element.className = "route-endpoint-marker";
        element.textContent = label as string;
        markers.current.push(
          new maplibregl.Marker({ element })
            .setLngLat(point as number[] as [number, number])
            .addTo(instance),
        );
      });
    }

    instance.on("load", drawRoutes);
    return () => {
      markers.current.forEach((marker) => marker.remove());
      markers.current = [];
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const selected =
      routes.find((route) => route.id === selectedId) ?? routes[0];
    const data = corridorGeoJSON(
      selected,
      corridorPoints,
      forecastHour,
      showHeatmap,
    );
    // Forecast data can arrive before MapLibre finishes loading its style and
    // creating the corridor source. Retry on the map's load event rather than
    // requiring the user to move the slider to trigger another React effect.
    const update = () => {
      const source = instance.getSource("corridor-weather") as
        | maplibregl.GeoJSONSource
        | undefined;
      if (source) source.setData(data);
    };
    update();
    if (!instance.isStyleLoaded()) {
      instance.on("load", update);
      return () => {
        instance.off("load", update);
      };
    }
  }, [routes, selectedId, corridorPoints, forecastHour, showHeatmap]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !instance.isStyleLoaded()) return;
    routes.forEach((route, index) => {
      if (!instance.getLayer(`route-line-${index}`)) return;
      const active = route.id === selectedId;
      instance.setPaintProperty(
        `route-line-${index}`,
        "line-width",
        active ? 6 : 3,
      );
      instance.setPaintProperty(
        `route-line-${index}`,
        "line-opacity",
        active ? 1 : 0.12,
      );
      instance.setPaintProperty(
        `route-halo-${index}`,
        "line-opacity",
        active ? 0.35 : 0.035,
      );
    });
    // Keep the chosen navigation line above the corridor overlay and alternatives.
    const selectedIndex = routes.findIndex((route) => route.id === selectedId);
    if (selectedIndex >= 0 && instance.getLayer(`route-line-${selectedIndex}`)) {
      instance.moveLayer(`route-halo-${selectedIndex}`);
      instance.moveLayer(`route-line-${selectedIndex}`);
    }
    const selected =
      routes.find((route) => route.id === selectedId) ?? routes[0];
    markers.current.forEach((marker) => marker.remove());
    markers.current = [];
    checkpointMarkers.current = [];
    if (!selected) return;
    const coordinates = validCoordinates(selected);
    selected.checkpoints?.forEach((checkpoint, index) => {
      if (
        !Number.isFinite(checkpoint.longitude) ||
        !Number.isFinite(checkpoint.latitude)
      )
        return;
      const element = document.createElement("div");
      element.className = "route-checkpoint-marker";
      const popup = new maplibregl.Popup({ offset: 15 }).setText(
        `Checkpoint ${index + 1} · ${new Date(checkpoint.eta).toLocaleString()}`,
      );
      element.addEventListener("click", () =>
        checkpointSelectRef.current(index),
      );
      const marker = new maplibregl.Marker({ element })
        .setLngLat([checkpoint.longitude, checkpoint.latitude])
        .setPopup(popup)
        .addTo(instance);
      markers.current.push(marker);
      checkpointMarkers.current.push(marker);
    });
    if (coordinates.length >= 2) {
      [
        [coordinates[0], "START"],
        [coordinates[coordinates.length - 1], "FINISH"],
      ].forEach(([point, label]) => {
        const element = document.createElement("div");
        element.className = "route-endpoint-marker";
        element.textContent = label as string;
        markers.current.push(
          new maplibregl.Marker({ element })
            .setLngLat(point as number[] as [number, number])
            .addTo(instance),
        );
      });
    }
  }, [routes, selectedId]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || selectedCheckpointIndex === null) return;
    const route = routes.find((item) => item.id === selectedId) ?? routes[0];
    const checkpoint = route?.checkpoints?.[selectedCheckpointIndex];
    if (
      !checkpoint ||
      !Number.isFinite(checkpoint.longitude) ||
      !Number.isFinite(checkpoint.latitude)
    )
      return;
    checkpointMarkers.current.forEach((marker, index) => {
      marker
        .getElement()
        .classList.toggle(
          "route-checkpoint-marker--active",
          index === selectedCheckpointIndex,
        );
    });
    instance.flyTo({
      center: [checkpoint.longitude, checkpoint.latitude],
      zoom: Math.max(instance.getZoom(), 10),
      duration: 950,
      essential: true,
    });
    const popup = new maplibregl.Popup({ offset: 20, closeOnClick: false });
    const content = document.createElement("div");
    content.className = "checkpoint-map-popup";
    const heading = document.createElement("strong");
    heading.textContent = `Checkpoint ${selectedCheckpointIndex + 1}`;
    content.appendChild(heading);
    const risk = document.createElement("p");
    risk.textContent = `Risk: ${checkpoint.risk?.level?.replace(/[_-]/g, " ") ?? "Unavailable"}`;
    content.appendChild(risk);
    const weather = checkpoint.weather;
    for (const [label, key, unit] of [
      ["Wind", "wind_mph", "mph"],
      ["Rainfall", "rain_in_per_hr", "in/hr"],
      ["Snowfall", "snow_in_per_hr", "in/hr"],
    ]) {
      const value = weather?.[key];
      const line = document.createElement("p");
      line.textContent = `${label}: ${typeof value === "number" && Number.isFinite(value) ? value.toFixed(key === "wind_mph" ? 1 : 2) + " " + unit : "Unavailable"}`;
      content.appendChild(line);
    }
    popup
      .setLngLat([checkpoint.longitude, checkpoint.latitude])
      .setDOMContent(content)
      .addTo(instance);
    return () => {
      popup.remove();
      checkpointMarkers.current.forEach((marker) =>
        marker.getElement().classList.remove("route-checkpoint-marker--active"),
      );
    };
  }, [routes, selectedId, selectedCheckpointIndex]);

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
      <div
        className="route-map"
        ref={container}
        aria-label="Interactive route alternatives map"
      />
      {showHeatmap && corridorPoints.length > 0 && (
        <div
          aria-live="polite"
          style={{
            position: "absolute",
            top: 14,
            right: 58,
            zIndex: 2,
            padding: "7px 11px",
            borderRadius: 7,
            background: "rgba(8, 22, 37, 0.9)",
            color: "#b8dcff",
            fontSize: 12,
            fontWeight: 700,
            pointerEvents: "none",
          }}
        >
          WEATHER FORECAST · +{forecastHour}h
        </div>
      )}
    </div>
  );
}
