import { useState, type FormEvent, type CSSProperties } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputAdornment,
  MenuItem,
  Select,
  TextField,
  ThemeProvider,
  createTheme,
} from "@mui/material";
import {
  FiActivity,
  FiArrowRight,
  FiCheckCircle,
  FiCloud,
  FiCompass,
  FiMapPin,
  FiNavigation,
  FiShield,
  FiTruck,
  FiZap,
  FiClock,
  FiTrendingUp,
} from "react-icons/fi";
import "./App.css";
import RouteMap from "./components/RouteMap";
import CheckpointTimeline from "./components/CheckpointTimeline";
import SpotlightCard from "./components/reactbits/SpotlightCard";
import BlurText from "./components/reactbits/BlurText";

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
  origin?: { name?: string };
  destination?: { name?: string };
  routes: Route[];
  route_count: number;
  recommended_route_id: string | null;
  weather_assessed: boolean;
  all_requested_routes_available: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#61b7ff" },
    background: { default: "#080e19", paper: "#121f30" },
    text: { primary: "#eef6ff", secondary: "#9bb0c8" },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"DM Sans", sans-serif',
    button: { textTransform: "none", fontWeight: 700 },
  },
  components: {
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: "#121f30",
          "& fieldset": { borderColor: "#2a3b50" },
          "&:hover fieldset": { borderColor: "#568cb9" },
        },
      },
    },
    MuiInputLabel: { styleOverrides: { root: { color: "#91a7c0" } } },
  },
});
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
  const [selectedCheckpointIndex, setSelectedCheckpointIndex] = useState<
    number | null
  >(null);

  const selected =
    result?.routes.find((route) => route.id === selectedId) ??
    result?.routes[0];

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    setSelectedId(null);
    setSelectedCheckpointIndex(null);
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
    <ThemeProvider theme={theme}>
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            <span className="brand-icon">
              <FiNavigation />
            </span>
            <span>
              spotter<span className="brand-accent">.</span>
              <span className="brand-light">ai</span>
            </span>
            <span className="brand-divider" />
            <span className="brand-subtitle">ROUTE INTELLIGENCE</span>
          </div>
          <div className="header-right">
            <span className="header-caption">
              WEATHER-AWARE ROUTING PLATFORM
            </span>
            <span className="status-pill">
              <span className="status-dot" /> Weather intelligence
            </span>
            <span className="avatar">
              <FiTruck />
            </span>
          </div>
        </header>

        <div className="workspace">
          <aside className="planning-panel">
            <div className="section-eyebrow">
              <span className="eyebrow-line" /> COMMAND CENTER{" "}
              <span className="eyebrow-index">01 / PLAN</span>
            </div>
            <h1 className="animated-headline">
              <BlurText text="Every mile." delay={110} trigger="load" />
              <BlurText
                text="More certain."
                delay={110}
                trigger="load"
                className="headline-accent"
              />
            </h1>
            <p className="intro">
              Plan smarter journeys with real-time forecast intelligence and
              load-aware risk analysis.
            </p>

            <form
              onSubmit={analyze}
              className="planning-form mui-planning-form"
            >
              <div className="form-heading">
                <span>JOURNEY DETAILS</span>
                <span className="form-heading-line" />
              </div>
              <TextField
                fullWidth
                required
                label="Origin"
                value={origin}
                onChange={(event) => setOrigin(event.target.value)}
                inputProps={{ minLength: 3 }}
                placeholder="Enter starting location"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <FiMapPin color="#61b7ff" />
                    </InputAdornment>
                  ),
                }}
              />
              <Box className="journey-connector">
                <FiArrowRight />
              </Box>
              <TextField
                fullWidth
                required
                label="Destination"
                value={destination}
                onChange={(event) => setDestination(event.target.value)}
                inputProps={{ minLength: 3 }}
                placeholder="Enter destination"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <FiNavigation color="#f5ad67" />
                    </InputAdornment>
                  ),
                }}
              />
              <TextField
                fullWidth
                required
                label="Departure · your local time"
                type="datetime-local"
                value={departure}
                onChange={(event) => setDeparture(event.target.value)}
                InputLabelProps={{ shrink: true }}
              />
              <div className="form-columns">
                <TextField
                  fullWidth
                  required
                  label="Load weight (lb)"
                  type="number"
                  value={weight}
                  onChange={(event) => setWeight(event.target.value)}
                  inputProps={{ min: 0, step: 1 }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <FiTruck />
                      </InputAdornment>
                    ),
                  }}
                />
                <FormControl fullWidth>
                  <Select
                    aria-label="Checkpoint interval"
                    value={interval}
                    onChange={(event) => setIntervalMiles(event.target.value)}
                  >
                    <MenuItem value="10">Every 10 mi</MenuItem>
                    <MenuItem value="25">Every 25 mi</MenuItem>
                    <MenuItem value="50">Every 50 mi</MenuItem>
                  </Select>
                  <span className="checkpoint-select-label">
                    CHECKPOINT INTERVAL
                  </span>
                </FormControl>
              </div>
              <Button
                variant="contained"
                size="large"
                fullWidth
                disabled={loading}
                type="submit"
                startIcon={
                  loading ? (
                    <CircularProgress size={17} color="inherit" />
                  ) : (
                    <FiZap />
                  )
                }
                endIcon={!loading ? <FiArrowRight /> : undefined}
                className="mui-analyze-button"
              >
                {loading ? "Analyzing routes…" : "Analyze safest routes"}
              </Button>
              <div className="form-footnote">
                <FiCloud /> Forecasts evaluated at checkpoint arrival times
              </div>
            </form>

            {error && (
              <Alert severity="error" variant="outlined">
                <strong>Analysis unavailable</strong>
                <p>{error}</p>
              </Alert>
            )}

            <div className="results-heading">
              <div>
                <div className="form-heading">ROUTE ANALYSIS</div>
                <h2>{result ? "Your alternatives" : "Awaiting a journey"}</h2>
              </div>
              {result && (
                <span className="result-count">
                  {result.route_count} ROUTES
                </span>
              )}
            </div>
            {!result && !loading && (
              <div className="empty-results">
                <span className="empty-symbol">
                  <FiCompass />
                </span>
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
                        } as CSSProperties
                      }
                    >
                      <div className="route-card-top">
                        <span className="route-card-name">
                          <FiNavigation className="route-line-icon" /> Route{" "}
                          {route.safety_rank ?? index + 1}
                        </span>
                        {recommended && (
                          <Chip
                            icon={<FiCheckCircle />}
                            label="RECOMMENDED"
                            size="small"
                            color="success"
                            variant="outlined"
                            className="mui-recommended-chip"
                          />
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
                            No travel{" "}
                            <b>{risk.no_travel_miles.toFixed(1)} mi</b>
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
              <FiShield className="footer-diamond" /> BUILT FOR CONFIDENT
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
                <FiActivity className="live-dot-icon" />{" "}
                {result ? "LIVE ROUTING DATA" : "AWAITING ROUTE DATA"}
              </div>
            </div>
            <div
              className={`map-stage ${result ? "has-routes" : ""} ${loading ? "is-scanning" : ""}`}
            >
              {result && (
                <RouteMap
                  routes={result.routes}
                  selectedId={selected?.id ?? null}
                  selectedCheckpointIndex={selectedCheckpointIndex}
                  onCheckpointSelect={setSelectedCheckpointIndex}
                  onSelect={(id) => {
                    setSelectedId(id);
                    setSelectedCheckpointIndex(null);
                  }}
                />
              )}
              <div className="map-grid" />
              {loading && (
                <div className="map-scan-field" aria-hidden="true">
                  <span className="map-scan-field__beam" />
                  <span className="map-scan-field__pulse map-scan-field__pulse--one" />
                  <span className="map-scan-field__pulse map-scan-field__pulse--two" />
                  <span className="map-scan-field__track map-scan-field__track--one" />
                  <span className="map-scan-field__track map-scan-field__track--two" />
                </div>
              )}
              <div className="map-glow map-glow-one" />
              <div className="map-glow map-glow-two" />
              <div className="map-stage-top">
                <span className="stage-label">
                  <FiCompass /> GEOSPATIAL INTELLIGENCE
                </span>
                {!result && (
                  <span className="stage-coordinates">MAP READY</span>
                )}
              </div>
              {!result && !loading && (
                <div className="map-empty">
                  <div className="orbit">
                    <span className="orbit-ring orbit-ring-one" />
                    <span className="orbit-ring orbit-ring-two" />
                    <span className="orbit-center">
                      <FiNavigation />
                    </span>
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
                  <div
                    className="routing-radar"
                    role="img"
                    aria-label="Scanning route conditions"
                  >
                    <div className="routing-radar__scope">
                      <span className="routing-radar__sweep" />
                      <span className="routing-radar__ring routing-radar__ring--inner" />
                      <span className="routing-radar__ring routing-radar__ring--outer" />
                      <span className="routing-radar__axis routing-radar__axis--horizontal" />
                      <span className="routing-radar__axis routing-radar__axis--vertical" />
                      <span className="routing-radar__blip routing-radar__blip--one" />
                      <span className="routing-radar__blip routing-radar__blip--two" />
                      <span className="routing-radar__blip routing-radar__blip--three" />
                      <span className="routing-radar__center">
                        <FiNavigation />
                      </span>
                    </div>
                    <span className="routing-radar__status">
                      <span className="routing-radar__status-dot" /> SCANNING
                      ROUTE CONDITIONS
                    </span>
                  </div>
                  <h3>Mapping your safest path.</h3>
                  <p>
                    Gathering route geometry and assessing forecast conditions
                    at each checkpoint.
                  </p>
                </div>
              )}
              <div className="map-stage-bottom">
                <span>◈ &nbsp; SPOTTER ROUTE ENGINE</span>
                <span>WEATHER-AWARE · LOAD-SENSITIVE · DATA-DRIVEN</span>
              </div>
            </div>
            {result && selected && (
              <section
                className="risk-intelligence"
                aria-label="Selected route risk intelligence"
                key={selected.id}
              >
                <div className="risk-intelligence__header">
                  <div>
                    <span className="risk-intelligence__eyebrow">
                      <FiActivity /> LIVE ROUTE ANALYSIS
                    </span>
                    <h3>Weather risk intelligence</h3>
                    <p>
                      Exposure along your selected route, based on checkpoint
                      forecasts.
                    </p>
                  </div>
                  <span className="risk-intelligence__route">
                    <FiNavigation /> Route{" "}
                    {selected.safety_rank ??
                      result.routes.indexOf(selected) + 1}
                  </span>
                </div>
                <div className="risk-intelligence__metrics">
                  <div className="risk-intelligence__metric">
                    <FiNavigation />
                    <span>ROUTE DISTANCE</span>
                    <strong>
                      {selected.distance_miles.toFixed(1)} <small>mi</small>
                    </strong>
                  </div>
                  <div className="risk-intelligence__metric">
                    <FiClock />
                    <span>ESTIMATED DRIVE</span>
                    <strong>{formatDuration(selected.duration_minutes)}</strong>
                  </div>
                  <div className="risk-intelligence__metric">
                    <FiTrendingUp />
                    <span>AVERAGE RISK</span>
                    <strong>
                      {selected.risk_summary
                        ? selected.risk_summary.average_risk.toFixed(1)
                        : "—"}
                    </strong>
                  </div>
                </div>
                {selected.risk_summary ? (
                  <div className="risk-intelligence__exposure">
                    {(
                      [
                        {
                          label: "Severe weather",
                          value: selected.risk_summary.severe_miles,
                          tone: "severe",
                        },
                        {
                          label: "High risk",
                          value: selected.risk_summary.high_miles,
                          tone: "high",
                        },
                        {
                          label: "No-travel conditions",
                          value: selected.risk_summary.no_travel_miles,
                          tone: "danger",
                        },
                      ] as const
                    ).map(({ label, value, tone }) => (
                      <div
                        className="risk-intelligence__exposure-row"
                        key={tone}
                      >
                        <div className="risk-intelligence__exposure-label">
                          <span>{label}</span>
                          <strong>{value.toFixed(1)} mi</strong>
                        </div>
                        <div
                          className="risk-intelligence__track"
                          role="meter"
                          aria-label={label}
                          aria-valuemin={0}
                          aria-valuemax={Math.max(
                            selected.distance_miles,
                            value,
                            1,
                          )}
                          aria-valuenow={value}
                        >
                          <span
                            className={`risk-intelligence__fill risk-intelligence__fill--${tone}`}
                            style={{
                              width: `${Math.min(100, Math.max(0, (value / Math.max(selected.distance_miles, 1)) * 100))}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                    <p className="risk-intelligence__note">
                      <FiShield /> Exposure categories may overlap. Bars show
                      the proportion of route miles in each category, not a
                      combined total.
                    </p>
                  </div>
                ) : (
                  <p className="risk-intelligence__note">
                    Detailed weather-risk metrics are not available for this
                    route.
                  </p>
                )}
              </section>
            )}
            {result && selected && (
              <CheckpointTimeline
                key={selected.id}
                checkpoints={selected.checkpoints ?? []}
                selectedCheckpointIndex={selectedCheckpointIndex}
                onCheckpointSelect={setSelectedCheckpointIndex}
                routeLabel={`Route ${selected.safety_rank ?? result.routes.indexOf(selected) + 1}`}
                originName={result.origin?.name}
                destinationName={result.destination?.name}
              />
            )}
            <div className="bottom-info">
              <SpotlightCard
                className="info-card"
                spotlightColor="#61b7ff"
                intensity={0.18}
                spotlightSize={190}
                borderGlow={0.3}
                flare={false}
              >
                <span className="info-icon blue">
                  <FiNavigation />
                </span>
                <div>
                  <strong>Real route alternatives</strong>
                  <p>Road-network routing, not straight-line estimates.</p>
                </div>
              </SpotlightCard>
              <SpotlightCard
                className="info-card"
                spotlightColor="#61b7ff"
                intensity={0.18}
                spotlightSize={190}
                borderGlow={0.3}
                flare={false}
              >
                <span className="info-icon amber">
                  <FiCloud />
                </span>
                <div>
                  <strong>Forecast at arrival</strong>
                  <p>Conditions evaluated at each checkpoint ETA.</p>
                </div>
              </SpotlightCard>
              <SpotlightCard
                className="info-card"
                spotlightColor="#61b7ff"
                intensity={0.18}
                spotlightSize={190}
                borderGlow={0.3}
                flare={false}
              >
                <span className="info-icon green">
                  <FiShield />
                </span>
                <div>
                  <strong>Safety-first decisions</strong>
                  <p>Weather exposure ranked before travel time.</p>
                </div>
              </SpotlightCard>
            </div>
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
}

export default App;
