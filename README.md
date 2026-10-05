# ADVAR backend

ADVAR tests an ad, a boosted post or an organic post on a virtual audience of AI agents inside
simulated social feeds (Facebook, Instagram, TikTok) before the real campaign is paid for. This
repository is the backend: FastAPI API, Arq worker, the NumPy simulation engine, PostgreSQL,
Redis, MinIO and Mailpit for local development. The frontend is built later against this API.

## Quick start (3 commands)

```bash
unzip advar.zip && cd advar
make up          # creates .env (with your UID/GID), builds and starts everything
make smoke       # end-to-end flow with the mock LLM and mock payments, prints PASS
```

`make up` starts Postgres, Redis, MinIO (+ a one-shot bucket creator), Mailpit, the API and
the worker. On every start the `api` container installs the requirements, waits for the
database, runs `alembic upgrade head` and the idempotent seed. No sudo is needed at any point.

| Service | URL |
|---|---|
| API docs (Swagger) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/api/v1/health |
| Mailpit (e-mails) | http://localhost:8025 |
| MinIO console | http://localhost:9001 (minioadmin / minioadmin) |
| Postgres | localhost:5432 (advar / advar / advar) |
| Redis | localhost:6379 |

Seeded admin: `admin@advar.local` / `admin12345` (change `SEED_ADMIN_*` in `.env`).

The seed creates tiers (quick, standard, full), USD prices, countries TH / MM / US with
published version 1, placeholder exchange rates (THB, MMK), scenarios, weight set v1,
platforms (facebook, instagram = full, tiktok = beta), six category templates and the
default settings (score weights, limits, Myanmar payment accounts with obviously fake values,
social links, banned words). Every numeric behaviour value in `backend/data/*.yaml` is labelled
`source: estimate_calibrate` until calibrated; ad-spec values are `official_spec` and must be
verified against the platforms' current official ad specs.

## Everyday commands (`make`)

| Target | What it does |
|---|---|
| `make env` | create `.env` from `.env.example` if missing and write your `UID`/`GID` into it |
| `make up` / `make down` | start / stop the stack |
| `make logs` | follow api + worker logs |
| `make restart` | restart api + worker (re-runs the requirements install) |
| `make ps` / `make shell` / `make dbshell` | status, bash in the api container, psql |
| `make migrate` | `alembic upgrade head` |
| `make migration m="add x"` | autogenerate a migration **as your host user** (editable without sudo) |
| `make seed` | run the idempotent seed |
| `make test` | pytest inside the container (`APP_ENV=test`, mock LLM, mock payments, memory storage/mail) |
| `make lint` / `make format` | ruff |
| `make smoke` | end-to-end smoke test (section below) |
| `make openapi` | write `backend/openapi.json` for the frontend type generator |
| `make engine` | run the engine from the CLI on `samples/sample_test.json` |
| `make reset-db` | drop the data volumes (asks for confirmation) |

## Configuration

All settings come from `.env` (documented in `.env.example`) and are validated by
`backend/app/config.py`. Important switches:

* `APP_ENV=local | test | production`. Production refuses `PAYMENT_MODE=mock`,
  `LLM_PROVIDER=mock`, memory/inline backends and the default `JWT_SECRET`.
* `LLM_PROVIDER=mock | openai`. The mock provider produces deterministic, realistic structured
  outputs so the whole pipeline runs without an API key (used by tests and the smoke test).
* `PAYMENT_MODE=mock | stripe_test | stripe_live` (see Payments).
* `ENGINE_VERSION` is part of the duplicate fingerprint; bump it when the engine changes.

### Adding the OpenAI key

1. Put `OPENAI_API_KEY=sk-...` and `LLM_PROVIDER=openai` in `.env`.
2. Check the model ids (`LLM_MODEL_AGENT`, `LLM_MODEL_SMART`, `LLM_MODEL_TRANSCRIBE`) against your
   OpenAI dashboard; prices per 1M tokens live in `LLM_PRICE_JSON` and drive the cost log.
3. `docker compose restart api worker`.

If `LLM_PROVIDER=openai` and the key is empty, the API still starts; a test fails at the
`analyze_ad` stage with the error code `llm_not_configured` and gets a free re-run.
Every call is logged to `llm_usage` (stage, model, input/cached/output tokens, cost, latency,
prompt version). `LLM_TEST_TOKEN_BUDGET` caps one test; `DAILY_LLM_SPEND_CAP_USD` pauses new
tests with `llm_daily_cap_reached` (admins are e-mailed at 80 %).

### Payments

| `PAYMENT_MODE` | Behaviour |
|---|---|
| `mock` (default) | `POST /tests/{id}/pay/card` succeeds immediately, no Stripe keys, response has `mode: mock`. `GET /tests/{id}/checkout` returns `payment_mode` and `test_mode_banner: true` for a "TEST MODE" banner. |
| `stripe_test` | Real Stripe Checkout with test keys. Put `STRIPE_SECRET_KEY=sk_test_...` in `.env`, start with `docker compose --profile stripe up -d`, copy the `whsec_...` printed by the `stripe-cli` container into `STRIPE_WEBHOOK_SECRET` and restart the api. Only the verified webhook marks a payment as paid. |
| `stripe_live` | Same code with live keys; allowed only when `APP_ENV=production`. |

Myanmar manual orders work in every mode: the app returns our payment accounts (admin
settings), the exact MMK amount fixed from the current exchange rate and a payment code
(`ADV-XXXX-XXXX`); the customer sends proof to our social media page; an admin searches the
code (`GET /admin/payments?code=`) and approves or cancels. Orders expire after
`MANUAL_ORDER_EXPIRY_HOURS`. With `PAYMENT_MODE=mock` and `MANUAL_AUTO_APPROVE_IN_MOCK=true`
orders are approved automatically. Card payments are always charged in USD; local amounts are
display-only. Prices are read from the database only:
total = tier price + (platforms − 1) × extra platform price.

## Permissions (no sudo, ever)

* The image creates a user `app` with the build args `UID`/`GID`; `make env` writes your ids
  into `.env` and the containers run as that user, so files written to the bind mount are yours.
* `/opt/venv` and the pip cache are named volumes owned by `app`; nothing is installed into the
  project folder. Postgres, Redis and MinIO use named volumes only. Uploads and PDFs go to MinIO.
* `PYTHONDONTWRITEBYTECODE=1` prevents `__pycache__` in the bind mount.
* `make migration m="..."` runs Alembic autogenerate as your host user.
* After running the stack and the tests, `find . -not -user $(id -u)` inside `advar/` prints nothing.
* Old root-owned files from a previous attempt can be fixed with one line:
  `docker run --rm -v "$PWD":/w alpine chown -R $(id -u):$(id -g) /w`

## Auto-reload

* `api`: `uvicorn --reload --reload-dir app --reload-dir engine`.
* `worker`: `arq ... --watch /app` (watchfiles; the whole backend folder, i.e. `app` and `engine`).
* Editing anything under `backend/app` or `backend/engine` reloads both. On Docker Desktop
  (Windows/macOS) set `WATCHFILES_FORCE_POLLING=true` in `.env` if changes are not detected.
* Changing `requirements.txt` / `requirements-dev.txt`: `docker compose restart api worker`
  (the entrypoint re-installs; a no-op when nothing changed).

## Migrations

```bash
make migration m="add consultant tables"   # autogenerate as the host user
# review backend/migrations/versions/<rev>_add_consultant_tables.py
make migrate
```

The initial schema (`backend/migrations/versions/0001_initial.py`) is hand-maintained and creates
the `pgcrypto` and `citext` extensions, all tables, the partial unique indexes (one succeeded
payment per test, unique payment codes, fingerprint index on completed tests) and CHECK
constraints for the enumerations.

## The engine from the command line

```bash
make engine                                    # runs samples/sample_test.json with heuristic reactions
docker compose exec api python -m engine.cli run samples/sample_test.json --runs 30 --json out.json
docker compose exec api python -m engine.cli bench   # times single 72-tick runs over 20,000 agents
```

The engine (`backend/engine/`) is a pure package: settings resolver (global → country →
platform × country → category (+ country overrides) → scenarios → profile), structure-of-arrays
population, profile-driven traits (taste, dietary needs, familiarity, brand relationship from the
reputation formula, language groups), seeded k-means archetypes, logistic crowd brain with
weights from `data/behavior_weights.yaml`, hourly virtual time with pacing, frequency cap and
fatigue, shares through a small-world friend graph, five scenarios, reproducible seeds (test id +
run number), goal-based score, evidence table and the reason validation (evidence references,
banned words, number check). One 72-tick run over 20,000 agents takes about 60 ms.

## Smoke test

`make smoke` (with `LLM_PROVIDER=mock`, `PAYMENT_MODE=mock`) runs the full flow against the
running stack and prints `PASS`: register → verification e-mail read from the Mailpit API →
verify → login → restaurant profile → test → post type `paid` + goal `messages` → upload the sample
image → facebook 60 % / tiktok 40 % → confirm → pay by card (mock) → SSE stream with `stage`,
`run_batch` and `completed` events → report with reasons and evidence → PDF URL → duplicate is
reported as duplicate → duplicate as `organic` (no budget), run, `GET /tests/compare` → Myanmar
test: card not offered, manual offered, manual order, admin approval by payment code → completed.

`SMOKE_TIER=standard make smoke` runs the full 150-run Standard pipeline instead of `quick`.

## OpenAPI for the frontend

`make openapi` writes `backend/openapi.json` (every endpoint of the API with request and response
schemas; the named schemas include `MeOut, TokenOut, CategoryTemplateOut, PlatformOut, CountryOut,
ScenarioOut, FxRateOut, SettingsVersionOut, SandboxResultOut, TierOut, ProfileOut,
ProfileVersionOut, TestOut, TestListItem, AssetOut, ConfirmOut, CheckoutOut, PaymentOut,
ProgressSnapshot, ReportOut, CompareOut, AdminPaymentOut, AdminTestOut, AdminMetricsOut`).
Errors always use `{"error": {"code", "message", "details"}}` with the stable codes from
`backend/app/errors.py`; lists use `{"items": [...], "next_cursor": ...}`.

## API notes

* Base path `/api/v1`. Access tokens are bearer JWTs (15 min); the refresh token is an httpOnly
  cookie scoped to `/api/v1/auth`, rotated on every refresh.
* Test flow: `POST /tests` → `PUT /tests/{id}/profile` → `POST /tests/{id}/assets` →
  `PUT /tests/{id}/post` → `PUT /tests/{id}/platforms` → `POST /tests/{id}/confirm` →
  `GET /tests/{id}/checkout` → `POST /tests/{id}/pay/{trial|card|manual}` → progress → report.
  Editing a confirmed (awaiting_payment) test returns it to `draft`; confirm again afterwards.
* Live progress: `POST /tests/{id}/progress/token` gives a 60-second stream token for
  `GET /tests/{id}/progress?st=` (EventSource cannot send headers). Events: `snapshot`, `stage`
  (with `cancel_window`), `run_batch` (every 5 runs), `comment` (max 2/s), `completed`, `failed`,
  `cancelled`; a heartbeat comment every 15 s. `GET /tests/{id}/progress/snapshot` for reconnects.
* Cancel: allowed while `queued` or `running` before the first run batch; one free restart
  (`POST /tests/{id}/restart`); a second cancel consumes the payment and needs a new one.
* Admin settings (countries, categories, platforms, scenarios, weights) are versioned:
  draft → `POST /admin/settings/{kind}/{id}/publish` → `.../rollback`. Only published versions
  are used by customer tests (recorded in `settings_versions`); drafts are used by
  `POST /admin/sandbox/run`. `POST /admin/categories/draft-ai` drafts a category template with the
  smart model (works with the mock provider too).

## Tests

`make test` runs pytest inside the api container against a `advar_test` database created from
the migration and seed, with the mock LLM, mock payments, in-memory storage and mail and an
inline job queue (jobs are executed in-process by the tests). Covered: state machine, pricing,
trial rules and e-mail normalisation, fingerprint stability and duplicate blocking, cancel window
open/closed and single free restart, profile version immutability and the save modes, platform
budget split and spec checks, post-type rules, goal-based score weights, Stripe webhook
idempotency and signature check, Myanmar manual orders, local price display, settings versions
(publish, rollback, layering, tests record versions, sandbox, AI draft), English-only comments
with language groups, reasons evidence and banned-word check, engine determinism and sanity
checks, the full API happy path, stuck-test recovery and resume without repeated LLM calls.

## Troubleshooting

* **`make up` fails on permissions** – run `make env` (writes `UID`/`GID`) and, for files from an
  older run, the `chown` one-liner in *Permissions*.
* **api restarts with "database not reachable"** – wait for the `postgres` healthcheck; check
  `docker compose logs postgres`.
* **Reload does not pick up changes** – set `WATCHFILES_FORCE_POLLING=true` (Docker Desktop).
* **`llm_not_configured`** – `LLM_PROVIDER=openai` without `OPENAI_API_KEY`; set the key or use `mock`.
* **`llm_daily_cap_reached`** – raise `DAILY_LLM_SPEND_CAP_USD` or wait until tomorrow.
* **Presigned URLs do not open in the browser** – `S3_PUBLIC_ENDPOINT` must be the address the
  browser can reach (`http://localhost:9000` locally).
* **Stripe webhooks never arrive** – start with `--profile stripe`, copy the `whsec_` secret into
  `.env`, restart the api; the success redirect never marks a test as paid.
* **A test is stuck in running** – the worker cron requeues it after 30 minutes without a
  heartbeat (once), then fails it with a free re-run; `POST /admin/tests/{id}/rerun` forces one.
* **Running outside Docker** – `STORAGE_BACKEND=local` and `STORAGE_LOCAL_DIR=...` replace MinIO
  for development on the host (not for production).
