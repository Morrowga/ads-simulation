# ADVAR frontend

Next.js 15 (App Router, React 19, TypeScript strict) web app for the ADVAR virtual ad testing
platform: Business Profiles, the test wizard, confirm page, checkout (free trial, Stripe, Myanmar
manual transfer), the live simulation screen (Server-Sent Events), the reasons report and the admin
panel. It talks to the FastAPI backend in `../backend` through `NEXT_PUBLIC_API_URL`.

## Quick start (local, outside Docker)

```bash
cd frontend
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
npm ci
npm run gen:api                   # regenerate src/lib/api-types.ts from the running backend (optional)
npm run dev                       # http://localhost:3000 → redirects to /en
```

The backend must be running (see `../backend/README.md`; `docker compose up -d` in the project
root starts Postgres, Redis, Mailpit, the API and the worker). CORS on the API already allows
`http://localhost:3000`.

Seeded admin (from the backend seed): `admin@advar.local` / `admin12345` → `/en/admin`.

## Scripts

| Script | What it does |
| --- | --- |
| `npm run dev` | Next dev server with hot reload on port 3000 |
| `npm run build` / `npm start` | Production build (`output: standalone`) |
| `npm run gen:api` | `openapi-typescript $OPENAPI_URL -o src/lib/api-types.ts` (default `http://localhost:8000/openapi.json`). A generated copy is checked in so the build never depends on a running API. Re-run after backend changes; `src/lib/types.ts` aliases the schemas the UI uses. |
| `npm run lint` / `npm run typecheck` / `npm run format` | ESLint, `tsc --noEmit`, Prettier |
| `npm test` | Vitest + Testing Library unit tests (`tests/`) |
| `npm run e2e` | Playwright end-to-end tests (`e2e/`) against a running stack |
| `npm run ci` | lint + typecheck + unit tests + build |

## Environment variables

| Variable | Local | Production | Notes |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | `https://api.example.com/api/v1` | Baked into the client bundle at build time |
| `NEXT_PUBLIC_STRIPE_MODE` | `test` | `live` | Display only; no Stripe keys in the browser |
| `NEXT_PUBLIC_DEFAULT_LOCALE` | `en` | `en` | Locale prefix is always in the URL (`/en`, `/th`) |
| `NEXT_PUBLIC_SENTRY_DSN` | empty | DSN | Optional |
| `OPENAPI_URL` | `http://localhost:8000/openapi.json` | – | Only for `npm run gen:api` |

## Docker

`Dockerfile` has four targets: `deps`, `dev` (hot reload, used by compose), `build` and `runner`
(standalone Node image, non-root user, same UID/GID build args as the backend image).

### Adding the `web` service to the root `docker-compose.yml`

The backend compose file is left untouched by this delivery. Either use the overlay file:

```bash
docker compose -f docker-compose.yml -f frontend/docker-compose.web.yml up -d
```

or merge this into the root `docker-compose.yml` (diff against the current file):

```diff
 services:
+  web:
+    build:
+      context: ./frontend
+      target: dev
+    command: npm run dev
+    environment:
+      NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000/api/v1}
+      NEXT_PUBLIC_STRIPE_MODE: ${NEXT_PUBLIC_STRIPE_MODE:-test}
+      NEXT_PUBLIC_DEFAULT_LOCALE: ${NEXT_PUBLIC_DEFAULT_LOCALE:-en}
+      OPENAPI_URL: http://api:8000/openapi.json
+      WATCHPACK_POLLING: "true"
+      NEXT_TELEMETRY_DISABLED: "1"
+    ports:
+      - "3000:3000"
+    volumes:
+      - ./frontend:/app
+      - frontend_node_modules:/app/node_modules
+      - frontend_next:/app/.next
+    depends_on:
+      - api

 volumes:
   pgdata:
   venv:
   pipcache:
+  frontend_node_modules:
+  frontend_next:
```

`NEXT_PUBLIC_API_URL` stays `http://localhost:8000/api/v1` even inside compose because the browser,
not the container, calls the API. The backend's `FRONTEND_URL` must point at the web app
(`http://localhost:3000` locally) so e-mail links and Stripe return URLs land on the right host.

### Production

```bash
docker build -f frontend/Dockerfile --target runner \
  --build-arg NEXT_PUBLIC_API_URL=https://api.example.com/api/v1 \
  --build-arg NEXT_PUBLIC_STRIPE_MODE=live \
  -t advar-web:latest frontend
docker run -p 3000:3000 advar-web:latest
```

Put Caddy (or any reverse proxy) in front; `/_next/static/*` files are immutable and can be cached
for a long time.

## Testing

Unit tests run anywhere: `npm test`.

End-to-end tests need the full stack (API on 8000, Mailpit on 8025, web on 3000):

```bash
docker compose -f docker-compose.yml -f frontend/docker-compose.web.yml up -d
cd frontend && npx playwright install chromium && npm run e2e
```

Environment overrides: `BASE_URL`, `API_URL`, `MAILPIT_URL`, `SEED_ADMIN_EMAIL`,
`SEED_ADMIN_PASSWORD`, `SAMPLE_IMAGE` (defaults to `../backend/samples/sample_ad.jpg`) and
`PLAYWRIGHT_CHROMIUM_PATH` (use a pre-installed Chromium instead of the Playwright download).

The suites cover: registration → e-mail verification → Business Profile → wizard → confirm → free
trial → live screen → report (`customer-journey`), the Myanmar manual order approved by a seeded
admin (`myanmar-manual`), the admin panel (`admin`) and phone-width layouts (`mobile`).

Note: the backend limits free trials per IP per day (`trial_ip_limit_per_day`, default 3); after
several E2E runs from one machine the checkout shows the paid methods instead of the trial banner,
which the suites handle. Raise the limit in `/admin/settings` for repeated local runs.

## Project layout

```
src/app/[locale]/(marketing)   home, pricing, how-it-works, legal      (public)
src/app/[locale]/(auth)        login, register, verify-email, forgot/reset password
src/app/[locale]/(app)         dashboard, profiles, tests/new (wizard), tests/[id] (+confirm,
                               checkout, live, report), tests/compare, payments, settings
src/app/[locale]/(admin)/admin overview, payments queue, tests, users, prices, settings,
                               countries, categories, platforms, scenarios, weights, fx-rates
src/components/ui              shadcn-style primitives on Radix
src/components/preview         PlatformPreview + Facebook/Instagram/TikTok-style mock-ups
src/components/{profile,wizard,checkout,live,report,admin,layout,tests}
src/lib/api.ts                 fetch wrapper: bearer token in memory, refresh once on 401, uploads
src/lib/sse.ts                 useTestProgress (snapshot + EventSource with stream token)
src/lib/queries.ts             TanStack Query hooks for every endpoint
src/lib/api-types.ts           generated from the backend OpenAPI schema
messages/en.json               all UI strings (add th.json etc. for more languages)
```

## Design notes

* One accent colour (`#0071b5`, dark `#3b93cf`); neutral greys; semantic success / warning /
  danger only carry meaning. Light and dark themes (`.dark` on `<html>`, remembered per device).
* Scores: 0–39 red, 40–69 amber, 70–100 green, always with the number and a text label.
* Previews are "Facebook-style" etc. with generic icons; no platform logos.
* Money is formatted from minor units and the currency code the API returns; the browser never
  computes prices.
* Copy states what happened and why; it never tells the owner what to change.
* WCAG 2.1 AA: focus rings, keyboard reachable actions, `aria-live` for stage changes,
  `prefers-reduced-motion` disables count-ups and chart transitions, 44 px touch targets.

## Backend changes this frontend expects

None are required for the delivered scope. `BACKEND_PATCHES.md` lists one optional endpoint
(`POST /auth/change-password`) that the Settings page uses when present and falls back gracefully
(e-mailed reset link) when it returns 404.
