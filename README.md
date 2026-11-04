# Spotter Weather Routing

A full-stack **weather-aware truck route planner** built for the Spotter Full Stack Developer assessment. It compares available driving routes using estimated arrival-time weather, load-sensitive risk rules, and travel duration, then visualizes the results on an interactive map.

**Live application:** https://spotter-weather-routing-beige.vercel.app/  
**Backend API:** https://spotter-weather-routing-api-62yl.onrender.com  
**Repository:** https://github.com/ayushman774/spotter-weather-routing

> This is an assessment/demo application, not a certified commercial truck-navigation or road-closure system. Do not use its risk scores as the sole basis for real-world safety decisions.

## Assessment coverage

| Requirement | Implementation |
| --- | --- |
| React + Django | React 19, TypeScript, Vite; Django 6 + Django REST Framework |
| Trip inputs | Origin, destination, departure date/time, load weight (lb) |
| Three route options | Requests alternatives from OpenRouteService; displays actual number returned |
| Weather sampling | Selectable 10, 25, or 50-mile checkpoint spacing; destination included |
| Time-aware forecasts | Weather evaluated for each checkpoint's estimated arrival time |
| Wind/rain/snow thresholds | Five levels: Low, Moderate, High, Severe, No Travel |
| Load-sensitive wind risk | Overrides for loads above 30,000 and 40,000 lb |
| Route recommendation | Risk-first ranking, with duration as a tie-breaker |
| Interactive map | Route alternatives, selection, checkpoint markers and risk information |
| Weather corridor | Road-aligned risk heatmap with a 0–48-hour forecast slider |

**Availability caveat:** The routing provider does not always return three distinct alternatives for every origin–destination pair. The API reports `route_count`, `requested_route_count`, and `all_requested_routes_available` rather than inventing alternatives.

## Technology

- **Frontend:** React, TypeScript, Vite, Material UI, MapLibre GL, Motion, React Icons
- **Backend:** Python 3.13, Django, Django REST Framework, httpx
- **Routing/geocoding:** OpenRouteService
- **Weather:** Open-Meteo hourly forecast
- **Hosting:** Vercel (frontend), Render/Gunicorn (backend)
- **Tests:** pytest/pytest-django backend suite; ESLint and TypeScript/Vite build for frontend

## Architecture

```text
Driver / Browser
    |
    v
React + TypeScript UI (Vercel)
    |-- Trip form and route selection
    |-- MapLibre route and checkpoint layers
    |-- Weather corridor overlay and 0–48 h slider
    |
    | POST /api/routes/plan/
    | POST /api/weather/corridor/
    v
Django REST API (Render)
    |-- Request validation
    |-- OpenRouteService geocoding and route alternatives
    |-- Distance-based checkpoints + ETA calculation
    |-- Open-Meteo forecast retrieval
    |-- Wind/rain/snow risk classification
    |-- Distance-weighted route scoring and ranking
    '-- Corridor hourly risk series
```

**Route planning and heatmap are separate operations.** Planning evaluates weather at each checkpoint's *ETA* and chooses the safest available route. The corridor endpoint provides an *exploratory* hourly weather visualization for the selected route, from departure +0 to +48 hours. Moving the slider changes the heatmap but does not recompute the route recommendation.

## Run locally

### Prerequisites

- Python 3.13 (the deployed backend uses Python 3.13.7)
- Node.js and npm compatible with Vite 8
- An OpenRouteService API key
- Internet access for routing/geocoding and weather APIs

### 1. Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and replace `ORS_API_KEY` with your own OpenRouteService key. Keep this file private; never commit real API keys.

```powershell
python manage.py migrate
python manage.py runserver
```

The backend runs at `http://127.0.0.1:8000`. Verify it at `http://127.0.0.1:8000/api/health/`.

On macOS/Linux, activate the virtual environment with `source .venv/bin/activate` and copy the example environment file with `cp .env.example .env`.

### 2. Frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. The example `VITE_API_BASE_URL` points to `http://127.0.0.1:8000`. Vite also proxies `/api` requests to the local Django server during development.

## Configuration

### Backend environment (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `ORS_API_KEY` | OpenRouteService API credential (required for real routing) |
| `DJANGO_SECRET_KEY` | Django signing secret; use a strong unique value in production |
| `DJANGO_DEBUG` | `true` locally, `false` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated permitted backend hostnames |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend origins |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins where applicable |

### Frontend environment (`frontend/.env`)

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Backend base URL, e.g. `http://127.0.0.1:8000` |

`VITE_*` variables are bundled into browser code: never put API secrets in them. The OpenRouteService key belongs on the backend only.

## How route planning works

1. The driver enters origin, destination, departure time, load weight, and checkpoint interval.
2. Django validates the request and geocodes both locations with OpenRouteService.
3. The backend requests route alternatives and converts route geometry, distance, and duration into checkpoints.
4. Checkpoints are sampled along each route at the requested interval (10, 25, or 50 miles), with estimated arrival times derived from the route's travel duration.
5. Open-Meteo weather is retrieved for the checkpoint coordinates and arrival times.
6. Each checkpoint receives wind, rain, snow, and overall risk classifications.
7. A checkpoint represents the distance between the midpoints to its neighbors; these spans are used to compute severe/high/no-travel mileage and distance-weighted average risk.
8. The backend ranks routes and returns the recommended route ID, route summaries, and weather-enriched checkpoints.
9. The frontend renders route cards and interactive MapLibre geometry. Selecting a different route updates its blue navigation highlight and weather corridor.

### Weather risk thresholds

| Risk | Wind (mph) | Rain (in/hour) | Snow (in/hour) |
| --- | --- | --- | --- |
| Low | <25 | <0.10 | <0.5 |
| Moderate | 25–<35 | 0.10–<0.25 | 0.5–<1.0 |
| High | 35–<45 | 0.25–<0.50 | 1.0–<2.0 |
| Severe | 45–<55 | 0.50–1.00 | 2.0–3.0 |
| No Travel | ≥55 | >1.00 | >3.0 |

The overall checkpoint risk is the highest applicable hazard level, **after** applying the load-based wind overrides:

- **Any load:** wind ≥55 mph → **No Travel**
- **Load >30,000 lb:** wind 45–54 mph → **No Travel**
- **Load >40,000 lb:** wind 35–44 mph → **at least Severe**

The implementation rejects non-finite or negative weather measurements instead of treating missing/invalid measurements as safe.

### Route recommendation order

The backend sorts available routes using the following lexicographic criteria:

1. Prefer routes with **no No Travel exposure**.
2. Among those, prefer **fewer No Travel miles**.
3. Prefer **fewer Severe-or-worse miles** (this includes No Travel mileage).
4. Prefer **fewer High miles**.
5. Prefer **lower distance-weighted average risk**.
6. Prefer **shorter travel duration**.
7. Use the route ID as a deterministic final tie-breaker.

The explicit No Travel priority is a safety-oriented extension of the assessment's severe/high/average/time ordering.

## Weather corridor heatmap

After route planning, the frontend samples positions along the selected route and calls `POST /api/weather/corridor/`. The backend returns risk and weather readings for 49 hourly offsets (0 through 48 inclusive). MapLibre draws the corresponding risk-colored corridor along the road geometry, with an option to show/hide the overlay.

The forecast slider explores conditions at different offsets from the supplied departure time. It is **not** a live vehicle tracker, a traffic-aware forecast, or an instruction to depart at a different time. The main route recommendation continues to use each checkpoint's estimated arrival time.

## API reference

All paths below are relative to the backend base URL.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health/` | Service health and version |
| POST | `/api/routes/plan/` | Geocode, request routes, sample checkpoint weather, score/rank |
| POST | `/api/weather/corridor/` | Fetch selected corridor's hourly forecast series |

### Example: plan a trip

```json
{
  "origin": "Denver, Colorado, USA",
  "destination": "Colorado Springs, Colorado, USA",
  "departure_time": "2026-11-05T14:00:00Z",
  "load_weight_lb": 25000,
  "checkpoint_interval_miles": 25,
  "assess_weather": true
}
```

Send this JSON to `POST /api/routes/plan/`. The response contains route geometry, checkpoints (with ETAs and weather/risk data), per-route risk summaries, `recommended_route_id`, and route-availability metadata. The departure timestamp is illustrative; choose a future time inside the supported forecast window when running the request.

### Example: corridor forecast

```json
{
  "departure_time": "2026-11-05T14:00:00Z",
  "load_weight_lb": 25000,
  "points": [
    { "latitude": 39.7392, "longitude": -104.9903 },
    { "latitude": 38.8339, "longitude": -104.8214 }
  ]
}
```

Send this JSON to `POST /api/weather/corridor/`. The endpoint accepts **2–40 points**, requires a timezone-aware departure timestamp, and returns an `hours` array of risk/weather values for each point. The frontend ordinarily supplies road-aligned sample points from the selected route.

Upstream provider errors are reported as API errors rather than silently fabricating route or weather values.

## Testing and validation

### Backend

Install the development test dependencies if needed:

```powershell
cd backend
pip install pytest pytest-django
python -m pytest routing/tests/ -v
```

The project has previously passed **88 backend tests and 21 subtests**, covering API validation, checkpoint intervals and ETAs, threshold boundaries, load-based overrides, route ranking, weather-provider failures, and forecast/corridor behavior. Run the suite again against the current branch before submission.

### Frontend

```powershell
cd frontend
npm run lint
npm run build
```

The frontend lint and TypeScript/Vite build were confirmed passing after the selected-navigation-line fix. Vite may report a non-blocking large-chunk warning; that is a performance optimization opportunity, not a build failure.

### Manual QA checklist

- [ ] Plan a valid trip and confirm returned route count
- [ ] Switch Route 1 → Route 2 → Route 3 (when available); confirm the **blue navigation line** moves with the selection
- [ ] Confirm route cards, checkpoint ETAs, and risk details match the selected route
- [ ] Show/hide the weather corridor
- [ ] Move the forecast slider from hour 0 to hour 48 and verify corridor changes
- [ ] Test 10-, 25-, and 50-mile checkpoint intervals
- [ ] Compare light and heavy load weights and check wind-risk behavior
- [ ] Verify helpful errors for invalid inputs and upstream API failures
- [ ] Repeat critical interactions on the deployed application

## Deployment

### Backend — Render

The repository includes `render.yaml`:

- Root directory: `backend`
- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- Health check: `/api/health/`

Set `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, and `ORS_API_KEY` in Render. Use a unique secret for `DJANGO_SECRET_KEY` (the blueprint can generate one). Do not commit real credentials.

### Frontend — Vercel

Deploy the `frontend` directory as a Vite application and configure `VITE_API_BASE_URL` with the public Render backend URL. Ensure the Django CORS allowlist includes the exact Vercel origin. Production frontend and backend should use HTTPS.

## Limitations and trade-offs

- **Three routes are not guaranteed:** OpenRouteService may return fewer distinct alternatives for some location pairs; the API exposes the actual count.
- **Weather is forecast data:** Accuracy, availability, and horizon depend on Open-Meteo and the selected departure time. Forecasts can change.
- **ETA approximation:** Checkpoint arrival times are derived from provider route duration; real traffic, mandatory breaks, road restrictions, and stops can change actual arrivals.
- **Risk model scope:** Wind, hourly rain, hourly snow, and load weight are assessed using the specified thresholds. The app is not a comprehensive road-safety, truck-clearance, or regulatory compliance engine.
- **Heatmap vs recommendation:** The 0–48-hour slider changes exploratory corridor visualization only; it does not rerank the routes.
- **Provider dependency:** Network errors, rate limits, or unavailable upstream services can prevent analysis.
- **Frontend bundle:** The production build may warn about a JavaScript chunk over 500 kB; code-splitting can be evaluated as future optimization.
- **Assessment scope:** No authentication or persistent trip history is required for the described workflow.

## Assessment deliverables

- [x] Source repository: https://github.com/ayushman774/spotter-weather-routing
- [x] Hosted application: https://spotter-weather-routing-beige.vercel.app/
- [x] Loom walkthrough recording (user-confirmed): **[Add Loom video URL before submission](https://www.loom.com/)**

### Walkthrough outline (recorded video; link pending)

1. **0:00–1:00:** Goal, stack, and architecture
2. **1:00–2:30:** Enter trip details; explain 10/25/50-mile sampling and checkpoint ETAs
3. **2:30–4:00:** Compare routes and demonstrate load-adjusted weather risk and safest-route recommendation
4. **4:00–5:30:** Select alternative routes; show map highlight and checkpoint details
5. **5:30–7:00:** Show/hide heatmap and move the 0–48-hour slider
6. **7:00–8:30:** Explain Django endpoints, risk ranking, tests, provider limitations, and deployment

---

Built as a technical assessment focused on **correctness, clarity, and practical route-weather decision support**.
