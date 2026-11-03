import { useState, type FormEvent } from "react";
import "./App.css";
import RouteMap from "./components/RouteMap";

type RiskSummary = {
  severe_miles: number;
  high_miles: number;
  average_risk: number;
  no_travel_miles: number;
};

type Checkpoint = {
  latitude: number;
  longitude: number;
  eta: string;
  distance_miles?: number;
  risk?: { level?: string; score?: number };
  weather?: Record<string, unknown>;
};

type Route = {
  id: string;
  distance_miles: number;
  duration_minutes: number;
  geometry: { type: string; coordinates: number[][] };
  checkpoints: Checkpoint[];
  risk_summary?: RiskSummary;
  safety_rank?: number;
};

type PlanResponse = {
  routes: Route[];
  route_count: number;
  recommended_route_id: string | null;
  weather_assessed: boolean;
  all_requested_routes_available: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const routeColors = ["#4c9bff", "#f7b75e", "#a99df7"];

function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return hours ? `${hours}h ${mins}m` : `${mins}m`;
}

function defaultDeparture() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function toLocalIso(value: string) {
  return new Date(value).toISOString();
}

function App() {
  const [origin, setOrigin] = useState("Denver, Colorado, USA");
  const [destination, setDestination] = useState(
    "Colorado Springs, Colorado, USA",
  );
  const [departure, setDeparture] = useState(defaultDeparture);
  const [weight, setWeight] = useState("25000");
  const [interval, setIntervalMiles] = useState("25");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  

  const selected =
    result?.routes.find((route) => route.id === selectedId) ??
    result?.routes[0];

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    setSelectedId(null);
    try {
      const response = await fetch(`${API_BASE}/api/routes/plan/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin: origin.trim(),
          destination: destination.trim(),
          departure_time: toLocalIso(departure),
          load_weight_lb: Number(weight),
          checkpoint_interval_miles: Number(interval),
          assess_weather: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        const message =
          typeof data?.error === "string"
            ? data.error
            : typeof data?.detail === "string"
              ? data.detail
              : "Unable to analyze this journey. Check your locations and try again.";
        throw new Error(message);
      }
      if (!Array.isArray(data.routes))
        throw new Error("The routing service returned an unexpected response.");
      setResult(data as PlanResponse);
      setSelectedId(data.recommended_route_id ?? data.routes[0]?.id ?? null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-icon">◈</span>
          <span>
            spotter<span className="brand-accent">.</span>
            <span className="brand-light">ai</span>
          </span>
          <span className="brand-divider" />
          <span className="brand-subtitle">ROUTE INTELLIGENCE</span>
        </div>
        <div className="header-right">
          <span className="header-caption">WEATHER-AWARE ROUTING PLATFORM</span>
          <span className="status-pill">
            <span className="status-dot" /> Intelligence online
          </span>
          <span className="avatar">S</span>
        </div>
      </header>

      <div className="workspace">
        <aside className="planning-panel">
          <div className="section-eyebrow">
            <span className="eyebrow-line" /> COMMAND CENTER{" "}
            <span className="eyebrow-index">01 / PLAN</span>
          </div>
          <h1>
            Every mile.
            <br />
            <span>More certain.</span>
          </h1>
          <p className="intro">
            Plan smarter journeys with real-time forecast intelligence and
            load-aware risk analysis.
          </p>

          <form onSubmit={analyze} className="planning-form">
            <div className="form-heading">
              <span>JOURNEY DETAILS</span>
              <span className="form-heading-line" />
            </div>
            <label className="input-group">
              <span className="field-label">ORIGIN</span>
              <span className="field-wrap">
                <span className="point-marker origin-marker" />
                <input
                  required
                  minLength={3}
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  placeholder="Enter starting location"
                />
              </span>
            </label>
            <div className="connection-line">
              <span>↓</span>
            </div>
            <label className="input-group">
              <span className="field-label">DESTINATION</span>
              <span className="field-wrap">
                <span className="point-marker destination-marker" />
                <input
                  required
                  minLength={3}
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder="Enter destination"
                />
              </span>
            </label>
            <label className="input-group departure-group">
              <span className="field-label">DEPARTURE · YOUR LOCAL TIME</span>
              <span className="field-wrap">
                <span className="field-symbol">◷</span>
                <input
                  required
                  type="datetime-local"
                  value={departure}
                  onChange={(e) => setDeparture(e.target.value)}
                />
              </span>
            </label>
            <div className="form-columns">
              <label className="input-group">
                <span className="field-label">LOAD WEIGHT (LB)</span>
                <span className="field-wrap">
                  <span className="field-symbol">▤</span>
                  <input
                    required
                    min={0}
                    step={1}
                    type="number"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                  />
                </span>
              </label>
              <label className="input-group">
                <span className="field-label">CHECKPOINTS</span>
                <span className="field-wrap select-wrap">
                  <select
                    value={interval}
                    onChange={(e) => setIntervalMiles(e.target.value)}
                  >
                    <option value="10">Every 10 mi</option>
                    <option value="25">Every 25 mi</option>
                    <option value="50">Every 50 mi</option>
                  </select>
                </span>
              </label>
            </div>
            <button className="analyze-button" disabled={loading} type="submit">
              <span className="button-spark">✦</span>
              <span>
                {loading
                  ? "Analyzing weather & routes…"
                  : "Analyze safest routes"}
              </span>
              <span className="button-arrow">↗</span>
            </button>
            <div className="form-footnote">
              <span className="footnote-dot" /> Powered by live routing and
              weather forecasts
            </div>
          </form>

          {error && (
            <div className="error-panel" role="alert">
              <strong>Analysis unavailable</strong>
              <p>{error}</p>
            </div>
          )}

          <div className="results-heading">
            <div>
              <div className="form-heading">ROUTE ANALYSIS</div>
              <h2>{result ? "Your alternatives" : "Awaiting a journey"}</h2>
            </div>
            {result && (
              <span className="result-count">{result.route_count} ROUTES</span>
            )}
          </div>
          {!result && !loading && (
            <div className="empty-results">
              <span className="empty-symbol">⌁</span>
              <p>
                Your route comparisons will appear here once you analyze a
                journey.
              </p>
            </div>
          )}
          {loading && (
            <div className="loading-results">
              <div className="loading-bar" />
              <div className="loading-bar short" />
              <div className="loading-bar" />
              <p>Comparing routes against forecast conditions…</p>
            </div>
          )}
          {result && (
            <div className="route-list">
              {result.routes.map((route, index) => {
                const active = route.id === selected?.id;
                const recommended = route.id === result.recommended_route_id;
                const risk = route.risk_summary;
                return (
                  <button
                    type="button"
                    key={route.id}
                    onClick={() => {
                      setSelectedId(route.id);
                                      }}
                    className={`route-card ${active ? "selected" : ""}`}
                    style={
                      {
                        "--route-color":
                          routeColors[index % routeColors.length],
                      } as React.CSSProperties
                    }
                  >
                    <div className="route-card-top">
                      <span className="route-card-name">
                        <span className="route-line-icon" /> Route{" "}
                        {route.safety_rank ?? index + 1}
                      </span>
                      {recommended && (
                        <span className="recommended-badge">✦ RECOMMENDED</span>
                      )}
                    </div>
                    <div className="route-card-metrics">
                      <span>
                        <strong>
                          {formatDuration(route.duration_minutes)}
                        </strong>
                        <small>{route.distance_miles.toFixed(1)} miles</small>
                      </span>
                      <span
                        className={`risk-badge ${risk?.no_travel_miles ? "danger" : risk?.severe_miles ? "warning" : "safe"}`}
                      >
                        {risk?.no_travel_miles
                          ? "NO-TRAVEL EXPOSURE"
                          : risk?.severe_miles
                            ? "SEVERE EXPOSURE"
                            : risk?.high_miles
                              ? "HIGH EXPOSURE"
                              : "NO HIGH-RISK MILES"}
                      </span>
                    </div>
                    {risk && (
                      <div className="route-risk-metrics">
                        <span>
                          Severe <b>{risk.severe_miles.toFixed(1)} mi</b>
                        </span>
                        <span>
                          High <b>{risk.high_miles.toFixed(1)} mi</b>
                        </span>
                        <span>
                          No travel <b>{risk.no_travel_miles.toFixed(1)} mi</b>
                        </span>
                      </div>
                    )}
                  </button>
                );
              })}
              {!result.all_requested_routes_available && (
                <p className="notice">
                  The routing provider returned fewer than three alternatives
                  for this journey.
                </p>
              )}
            </div>
          )}
          <div className="sidebar-footer">
            <span className="footer-diamond">◇</span> BUILT FOR CONFIDENT
            DECISIONS <span>V 1.0</span>
          </div>
        </aside>

        <main className="main-panel">
          <div className="main-topline">
            <div>
              <div className="section-eyebrow">THE INTELLIGENCE VIEW</div>
              <h2>
                Route overview <span className="title-slash">/</span>{" "}
                <span className="main-title-muted">
                  {result ? "Analysis ready" : "Ready to explore"}
                </span>
              </h2>
            </div>
            <div className="map-meta">
              <span className="live-dot" />{" "}
              {result ? "LIVE ROUTING DATA" : "AWAITING ROUTE DATA"}
            </div>
          </div>
          <div className={`map-stage ${result ? "has-routes" : ""}`}>
            {result && <RouteMap routes={result.routes} selectedId={selected?.id ?? null} onSelect={(id) => { setSelectedId(id);  }} />}
            <div className="map-grid" />
            <div className="map-glow map-glow-one" />
            <div className="map-glow map-glow-two" />
            <div className="map-stage-top">
              <span className="stage-label">GEOSPATIAL INTELLIGENCE</span>
              {!result && <span className="stage-coordinates">MAP READY</span>}
            </div>
            {!result && (
              <div className="map-empty">
                <div className="orbit">
                  <span className="orbit-ring orbit-ring-one" />
                  <span className="orbit-ring orbit-ring-two" />
                  <span className="orbit-center">⌖</span>
                </div>
                <div className="map-empty-eyebrow">
                  YOUR JOURNEY STARTS HERE
                </div>
                <h3>See the road ahead.</h3>
                <p>
                  Enter your journey details to compare alternative routes and
                  understand weather risks before you depart.
                </p>
                <div className="map-empty-steps">
                  <span>01 &nbsp; PLAN</span>
                  <span className="step-separator">→</span>
                  <span>02 &nbsp; ANALYZE</span>
                  <span className="step-separator">→</span>
                  <span>03 &nbsp; DECIDE</span>
                </div>
              </div>
            )}
            {loading && (
              <div className="map-empty">
                <div className="orbit orbit-loading">
                  <span className="orbit-ring orbit-ring-one" />
                  <span className="orbit-ring orbit-ring-two" />
                  <span className="orbit-center">⌖</span>
                </div>
                <h3>Mapping your safest path.</h3>
                <p>
                  Gathering route geometry and assessing forecast conditions at
                  each checkpoint.
                </p>
              </div>
            )}
            <div className="map-stage-bottom">
              <span>◈ &nbsp; SPOTTER ROUTE ENGINE</span>
              <span>WEATHER-AWARE · LOAD-SENSITIVE · DATA-DRIVEN</span>
            </div>
          </div>
          <div className="bottom-info">
            <div className="info-card">
              <span className="info-icon blue">↗</span>
              <div>
                <strong>Real route alternatives</strong>
                <p>Road-network routing, not straight-line estimates.</p>
              </div>
            </div>
            <div className="info-card">
              <span className="info-icon amber">☁</span>
              <div>
                <strong>Forecast at arrival</strong>
                <p>Conditions evaluated at each checkpoint ETA.</p>
              </div>
            </div>
            <div className="info-card">
              <span className="info-icon green">◇</span>
              <div>
                <strong>Safety-first decisions</strong>
                <p>Weather exposure ranked before travel time.</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
