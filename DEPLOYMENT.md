# Deployment checklist

## Proposed hosting

- Frontend: Vercel (Vite static build)
- Backend: Render (Django WSGI application)

This is a preparation guide, not a record of a completed deployment. Verify the backend dependency manifest, Python version, and service commands before creating a hosted service.

## Backend environment

Set these values in the hosting provider's **secret environment settings**, not in committed files:

- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY=<long unique random secret>`
- `DJANGO_ALLOWED_HOSTS=<backend-hostname-without-scheme>`
- `DJANGO_CORS_ALLOWED_ORIGINS=https://<frontend-hostname>`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://<frontend-hostname>`
- `ORS_API_KEY=<your OpenRouteService API key>`

Never commit real credentials. Ensure the hosting provider runs the app from the `backend` directory and uses the correct dependency manifest. Django WSGI entry point: `config.wsgi:application`. A production WSGI server such as Gunicorn must be installed in the backend environment.

The API health endpoint is exposed by `routing.urls`; verify its final path from that file before configuring provider health checks.

The backend currently uses SQLite. For an API that only calculates routes and forecasts, confirm whether any persistent database state is required before choosing persistent storage. A free ephemeral filesystem is not suitable for durable database records.

## Frontend environment

Set `VITE_API_BASE_URL=https://<backend-hostname>` in Vercel's build environment. This is a public browser-facing URL, not a secret.

- Root directory: `frontend`
- Install: `npm ci`
- Build: `npm run build`
- Output: `dist`

Rebuild and redeploy the frontend whenever its `VITE_API_BASE_URL` changes. The local Vite proxy is development-only.

## Verification before publishing

1. `cd frontend && npm run lint && npm run build`
2. `cd backend && python manage.py check --deploy` with production environment variables configured.
3. Run backend unit and API tests using the repository's established test command.
4. Verify the backend health endpoint over HTTPS.
5. Submit a route plan from the deployed frontend and confirm the request reaches the backend.
6. Check CORS, invalid locations, provider errors, weather failures, and mobile layouts.
7. Verify the API key is never sent to the browser and that deployed logs do not expose secrets.

## Pending before live deployment

- Confirm the backend dependency manifest and compatible Python version.
- Confirm production startup and static-file handling requirements.
- Select and connect hosting accounts.
- Configure environment secrets in the hosting dashboard.
- Deploy both services and perform end-to-end smoke tests.
