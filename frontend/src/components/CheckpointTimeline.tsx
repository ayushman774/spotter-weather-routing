import { FiClock, FiCloud, FiMapPin, FiShield } from "react-icons/fi";

type Checkpoint = {
  latitude: number;
  longitude: number;
  eta: string;
  distance_miles?: number;
  risk?: { level?: string; score?: number };
  weather?: Record<string, unknown>;
};

type Props = {
  checkpoints: Checkpoint[];
  routeLabel: string;
};

function numeric(weather: Record<string, unknown> | undefined, keys: string[]) {
  for (const key of keys) {
    const value = weather?.[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function timestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "ETA unavailable"
    : date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
      });
}

function riskTone(level?: string) {
  const normalized = (level ?? "").toLowerCase().replace(/[_-]/g, " ");
  if (normalized.includes("no travel") || normalized.includes("extreme"))
    return "danger";
  if (normalized.includes("severe") || normalized.includes("high"))
    return "warning";
  if (normalized.includes("moderate") || normalized.includes("medium"))
    return "moderate";
  return normalized.includes("low") || normalized.includes("safe")
    ? "safe"
    : "unknown";
}

export default function CheckpointTimeline({ checkpoints, routeLabel }: Props) {
  return (
    <section className="checkpoint-timeline" aria-label="Checkpoint weather timeline">
      <div className="checkpoint-timeline__heading">
        <div>
          <span className="checkpoint-timeline__eyebrow">
            <FiCloud /> FORECAST ALONG THE JOURNEY
          </span>
          <h3>Checkpoint weather timeline</h3>
          <p>Arrival estimates and available forecast readings for {routeLabel}.</p>
        </div>
        <span className="checkpoint-timeline__count">
          {checkpoints.length} CHECKPOINTS
        </span>
      </div>
      {checkpoints.length === 0 ? (
        <div className="checkpoint-timeline__empty">
          <FiMapPin /> No checkpoint forecasts were returned for this route.
        </div>
      ) : (
        <ol className="checkpoint-timeline__list">
          {checkpoints.map((checkpoint, index) => {
            const temperature = numeric(checkpoint.weather, [
              "temperature_2m",
              "temperature_c",
              "temperature",
            ]);
            const wind = numeric(checkpoint.weather, [
              "wind_speed_10m",
              "wind_speed_kmh",
              "wind_speed",
            ]);
            const precipitation = numeric(checkpoint.weather, [
              "precipitation",
              "precipitation_mm",
            ]);
            const tone = riskTone(checkpoint.risk?.level);
            return (
              <li
                className="checkpoint-timeline__item"
                key={`${index}-${checkpoint.latitude}-${checkpoint.longitude}`}
              >
                <span className={`checkpoint-timeline__node checkpoint-timeline__node--${tone}`} aria-hidden="true" />
                <div className="checkpoint-timeline__card">
                  <div className="checkpoint-timeline__top">
                    <strong>Checkpoint {index + 1}</strong>
                    <span className={`checkpoint-timeline__risk checkpoint-timeline__risk--${tone}`}>
                      <FiShield /> {checkpoint.risk?.level?.replace(/[_-]/g, " ") || "Risk unavailable"}
                    </span>
                  </div>
                  <div className="checkpoint-timeline__details">
                    <span><FiClock /> {timestamp(checkpoint.eta)}</span>
                    {typeof checkpoint.distance_miles === "number" && (
                      <span><FiMapPin /> {checkpoint.distance_miles.toFixed(1)} mi along route</span>
                    )}
                  </div>
                  <div className="checkpoint-timeline__weather">
                    <span>Temperature <strong>{temperature === null ? "—" : `${temperature.toFixed(1)}°C`}</strong></span>
                    <span>Wind <strong>{wind === null ? "—" : `${wind.toFixed(1)} km/h`}</strong></span>
                    <span>Precipitation <strong>{precipitation === null ? "—" : `${precipitation.toFixed(1)} mm`}</strong></span>
                  </div>
                  <span className="checkpoint-timeline__coords">
                    {checkpoint.latitude.toFixed(4)}, {checkpoint.longitude.toFixed(4)}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <p className="checkpoint-timeline__disclaimer">
        Weather readings appear only when the routing API supplies compatible values.
        Missing readings are shown as —. Times are displayed in your device time zone.
      </p>
    </section>
  );
}
