# Simple Job Management Dashboard

Django + PostgreSQL backend, React + TypeScript (AntD) frontend, Playwright E2E, Docker Compose,
Makefile. 

## The bar

**Hard gate.** On a machine with only `make`, `docker`, `docker compose v2`, `bash` and Docker Hub
access, a fresh clone must pass `make test`. If it fails, nothing else is evaluated. Keep it green
in every phase.

**Evaluation criteria** (check work against these before closing any phase):
- [ ] **Correctness:** meets all core requirements and works as expected.
- [ ] **Code quality: readability** — easy to understand and follow.
- [ ] **Code quality: maintainability** — well organised and structured.
- [ ] **Code quality: modularity** — components / functions well defined and reusable.
- [ ] **Code quality: error handling** — potential errors handled gracefully.
- [ ] **Code quality: type safety** — effective use of TypeScript (`strict`, no `any`).
- [ ] **Testing:** E2E tests well written, reliable, cover critical functionality.
- [ ] **Setup & deployment:** easy to run with the Makefile and Docker setup.
- [ ] **Problem solving:** approach visible in code structure and README.
- [ ] **Attention to detail:** small touches that show care.

**Deliverables:** source, both Dockerfiles, `docker-compose.yml`, `Makefile`, and a `README.md`
with setup/build/run/test instructions, performance notes, time spent, and a prompt-engineering
writeup + AI transcript link. Be able to walk through and extend every line.

## Scope

Core requirements 1-5 of the brief + one stretch goal: backend unit tests. Nothing else is built.

Not built now (design notes at the bottom): status history view, filter/sort, job details page,
frontend unit tests, auth, job rename, page-size selector, perf benchmark harness.

**Priority if something must give:** 1) gate  2) core correctness  3) million-job performance
4) code quality / type safety  5) README + AI writeup  6) UI polish / a11y extras.
The 4 hours is a guideline; the author decides any cuts.

## Conventions

- **Claude does not commit.** The author commits at each phase boundary. Stop for review at the end of
  every phase.
- **TDD on the backend:** failing test first, then the code, then refactor.
- **Python docstrings: reST style** (`:param name:`, `:returns:`, `:raises Exc:`). Types live in the
  function signature, so no `:type:` / `:rtype:` fields when the signature is annotated, e.g.
  `def health(request: HttpRequest) -> JsonResponse:`. Every function is fully annotated.
- **Deferred work** gets a `TODO` in code and a one-line spoken reason (what, why deferred, fix).
- **Teaching:** The author's production stack is Flask + MySQL + Elasticsearch, with DevOps owning
  Docker/Make. Explain Django, Postgres, Dockerfile, Compose and Makefile concepts by analogy to
  that stack, with the reason and the industry practice behind each choice.
- **Frontend:** React + TypeScript + AntD. Keep the UI sparse; accessibility by default.
- Update this file at the end of each phase when anything in it stops being true.
- **`.gitignore` is project-specific** (the generic Python template ignored `lib/`, `dist/`, `build/`
  at any depth). Add only anchored or unambiguous patterns; after adding a folder, check
  `git status` shows it.
- **Lockfiles:** regenerate with `docker run --rm -v "$PWD/frontend":/w -w /w node:22-bookworm-slim
  npm install --package-lock-only` (same for `e2e`), never from a host `node_modules`.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Current status | Denormalized `Job.current_status`, written in the same transaction as the `JobStatus` insert | List is one indexed query with no join; `JobStatus` stays an append-only log. |
| Pagination | Keyset (cursor) in the API, Prev/Next in the UI, fixed page size of 20 | Constant cost at any depth, no `COUNT(*)` over millions of rows. |
| AntD table | `<Table pagination={false} />` + a small `CursorPager` (two `Button`s) | AntD's built-in pagination needs a `total`; a cursor API never counts. Same idea as ES `search_after` vs `from/size`. |
| `make test` | Playwright E2E only (spec-literal) | Backend tests run via `make test-backend`. |
| API layer | Django REST Framework | Industry default: serializers, viewsets, cursor pagination. |
| Frontend serving | Multi-stage build; nginx serves static files and proxies `/api` to gunicorn | Production-shaped, single origin, no CORS config. |
| Data fetching | TanStack Query | Invalidate-after-mutation makes "UI updates dynamically" correct and small. |
| Ordering | `-id` (newest first) | Primary-key index, unique (cursor pagination requires it), no extra index. |
| PATCH contract | Body `{"status_type": "<STATE>"}`, required. Any state to any state, including the current one; every PATCH appends a `JobStatus` row. | Spec-literal. Not idempotent by design; note in README. |
| Auth | None | Not in spec. `TODO` in `settings.py` + README "Security notes" (fix: DRF permission classes + owner FK). |
| `ALLOWED_HOSTS` | `*` in `docker-compose.yml`, strict default in `settings.py` | Opening the app by IP on a remote VM otherwise loads the page but every API call gets a 400. Safe only while there is no auth, email or cache; tighten when auth lands. Flagged in README. |
| Base images | Docker Hub only | Official Playwright image is on `mcr.microsoft.com`, which the brief does not promise. e2e image = `node:*-bookworm` + `npx playwright install --with-deps chromium`. |
| Test stack isolation | Own compose project (`job-dashboard-test`), no published host ports. Host ports live only in `docker-compose.override.yml`, which `make up` auto-loads and `make test` skips (`-f docker-compose.yml`). | Busy ports on the evaluator's machine cannot fail the gate; works on any compose v2 (no `!reset`). |
| nginx to backend | `proxy_pass` through a variable + Docker DNS `resolver`; `Host $http_host` | nginx starts and recovers when the backend is down or restarts; the forwarded Host keeps its port so DRF pagination links are correct. |
| Pinned versions | Python 3.13, Django 5.2 LTS, Postgres 17, Node 22, nginx 1.28, Vite 8, React 19, TypeScript 7, Playwright 1.64 | Exact pins in `requirements.txt` and both `package-lock.json` files (generated inside the Node image so all platforms' native binaries are locked). |

## Target layout

```
Makefile                      # build, up, test, stop, clean (+ test-backend, seed, help)
docker-compose.yml            # db, backend, frontend (+ e2e under a profile); no host ports
docker-compose.override.yml   # host port for `make up` only (FRONTEND_PORT, default 8080)
backend/
  Dockerfile  requirements.txt  manage.py  pytest.ini
  config/                     # settings.py, urls.py, wsgi.py, views.py (health endpoint)
  jobs/
    models.py  services.py  serializers.py  views.py  urls.py  pagination.py
    migrations/
    management/commands/seed_jobs.py
    tests/                    # test_models, test_services, test_api, test_scale
frontend/
  Dockerfile  nginx.conf  vite.config.ts  tsconfig.json
  src/
    api/client.ts  api/jobs.ts
    types/job.ts
    features/jobs/            # JobsPage, JobsTable, CreateJobForm, StatusSelect,
                              # StatusTag, DeleteJobButton, CursorPager, hooks.ts
e2e/
  Dockerfile  playwright.config.ts  tests/smoke.spec.ts (becomes jobs.spec.ts in Phase 7)
```

## Plan

Status: `[ ]` not started, `[~]` in progress, `[x]` done and reviewed.

### [x] Phase 0 — This file

### [~] Phase 1 — Walking skeleton (the gate) — built and verified, awaiting author review
Goal: every container exists and talks to the next one; `make test` is green with no features.
1. `backend/`: Django project `config`, single app `jobs`, `GET /api/health/` that runs
   `SELECT 1`. Settings from env vars with working defaults (no `.env` needed on a clone).
2. `backend/Dockerfile`: pinned `python:3.x-slim`; copy `requirements.txt` and install before
   copying source; non-root user; gunicorn. Start command runs `migrate` then the server.
3. `frontend/`: Vite React-TS app showing a title and the health result. Multi-stage `Dockerfile`:
   `node` builds, `nginx` serves `dist/` and proxies `/api/`.
4. `docker-compose.yml`: `db` (pinned `postgres`, named volume, `pg_isready` healthcheck),
   `backend` (healthcheck on `/api/health/`, `depends_on: db: condition: service_healthy`),
   `frontend`, and `e2e` behind `profiles: [e2e]`.
5. `e2e/`: one Playwright smoke test: page loads through nginx and shows the backend as healthy.
6. `Makefile`: `make test` tears down any leftover test stack, builds, brings up an isolated
   project, waits for health, runs `e2e`, propagates its exit code, always tears down (`down -v`).

Gate risks to close here:
- `ALLOWED_HOSTS`: in the test stack the browser calls `http://frontend`, so Django sees
  `Host: frontend` and returns 400 unless configured. The smoke test goes through nginx to catch it.
  (Compose now defaults to `*`; the strict `settings.py` default still lists `frontend`.)
- Lockfiles committed and used (`npm ci`, pinned `requirements.txt`).
- `make test` works with no prior `make build`, and after a previously failed run.
- No executable-bit or line-ending dependence: start commands inline in the Dockerfile.
- Frontend calls relative `/api/...`; no URL baked in at build time.
- All images multi-arch (Apple Silicon and x86 Linux).
- `.dockerignore` keeps host `node_modules` / `__pycache__` out of the build context.

**Manual check (author):** after committing, `git clone` into a temp dir and run `make test`
(exit 0). `make up`, open http://localhost:8080, expect "Backend: healthy"; `docker compose stop
backend`, reload, expect "Backend: unreachable". `make clean`, then `docker ps -a` shows nothing
named `job-dashboard`. Read the Makefile `test` target and `docker-compose.yml`.

**Exit:** `make clean && make test` passes twice in a row from a fresh `git clone` into a temp dir;
`make up` shows the page in a browser.

### [ ] Phase 2 — Data model (TDD)
Tests first (`pytest-django`, real Postgres in the container, `make test-backend`):
- creating a job sets `created_at` / `updated_at`; saving moves `updated_at`;
- new job defaults to `current_status = PENDING`;
- an invalid status is rejected by the database on both tables;
- deleting a job deletes its `JobStatus` rows and leaves other jobs' rows alone.

Build:
- `Job`: `name` (`CharField(max_length=255)`), `created_at` (`auto_now_add`), `updated_at`
  (`auto_now`), `current_status` (`TextChoices`, default `PENDING`).
- `JobStatus`: `job` (FK, `on_delete=CASCADE`, `related_name="statuses"`), `status_type`
  (PENDING, RUNNING, COMPLETED, FAILED), `timestamp` (`default=timezone.now`).
- `CheckConstraint` on `Job.current_status` and `JobStatus.status_type` (Django `choices` are
  not enforced by `save()`).
- `TODO` on `JobStatus.Meta`: `(job, -timestamp)` index — history view not specced.
- `TODO` on `Job.Meta`: `(current_status, -id)` index — no filter yet; every index taxes writes.

**Manual check (author):** read the migration file. In `psql`, `\d jobs_job` and `\d jobs_jobstatus`:
confirm the check constraints and the FK `ON DELETE` behaviour exist in the database itself.

**Exit:** model tests green; the author has reviewed the migration file.

### [ ] Phase 3 — Services and REST API (TDD)
**3a. Services** (`services.py`): `create_job(name)`, `change_status(job_id, status)`, each in
`transaction.atomic()`. `change_status` locks the job row with `select_for_update()`, inserts the
`JobStatus`, then saves `current_status` and `updated_at`.

Sync tests. Invariant: `job.current_status` equals the `status_type` of that job's newest
`JobStatus` (newest = highest `id`). One shared `assert_in_sync(job)` helper, used in:
- after `create_job`: exactly one status row, `PENDING`, in sync;
- after a sequence of changes: row count is 1 + N, in sync after each step;
- rollback: force the `Job` save to raise after the `JobStatus` insert; no new status row exists
  and `current_status` is unchanged;
- concurrency: several threads call `change_status` on one job with different states
  (`django_db(transaction=True)`); row count is 1 + threads and in sync;
- `updated_at` moves after `change_status` (`save(update_fields=[...])` skips `auto_now` fields
  unless listed);
- `change_status` on a missing or just-deleted job raises not-found and writes nothing;
- POST/PATCH bodies containing `current_status` do not change it;
- `seed_jobs` output is in sync (Phase 4).

**3b. API** (`serializers.py`, `views.py`, `pagination.py`, `urls.py`); viewset limited to
list / create / partial_update / destroy; no authentication classes.
- `GET /api/jobs/`: `{next, previous, results}`; fields `id`, `name`, `current_status`,
  `created_at`, `updated_at`; newest first; page of 20; walking `next` to the end returns every
  job exactly once; a garbage `cursor` gives a 4xx, not a 500; empty table gives empty results.
- `POST /api/jobs/`: 201 + one `PENDING` row; blank, whitespace-only, missing, over-255 and
  NUL-containing names give 400 with a field error; surrounding whitespace trimmed; duplicate
  names allowed.
- `PATCH /api/jobs/<id>/`: 200 + appended row; missing / unknown / wrong-case `status_type` gives
  400 and writes nothing; unknown id gives 404; same status as current still appends.
- `DELETE /api/jobs/<id>/`: 204 with empty body; statuses gone; second delete gives 404.
- A non-numeric id, or one larger than a bigint, gives 404, not 500.
- PUT and `GET /api/jobs/<id>/` give 405 (not in the brief).

Audit pass before leaving the phase: validation, auth (deferred, TODO), idempotency (PATCH appends
by design; no idempotency key on POST, TODO), atomicity, failure handling, limits, concurrency,
observability (gunicorn access log to stdout), tests.

**Manual check (author):** `curl` all four endpoints through nginx (`make up`), plus bad inputs: blank
name, unknown status, garbage cursor, unknown id. Watch `docker compose logs backend` while doing it.

**Exit:** `make test-backend` green; `curl` walkthrough of all four endpoints via `make up`.

### [ ] Phase 4 — Scale guards (small; first to cut)
1. `seed_jobs` management command: N jobs + initial statuses via
   `INSERT ... SELECT generate_series(...)`. `make seed N=1000000`.
2. `test_scale.py`:
   - list endpoint runs the same number of queries for 1 job and for a full page (no N+1);
   - seed ~20k rows, `ANALYZE`, `EXPLAIN` the list query: uses the primary-key index, no
     `Seq Scan`, no `Sort`.
3. Manual: seed 1M, open the UI, page forward; note the result for the README.

**Manual check (author):** automated tests are not enough here. Seed 1M rows, page through the UI,
and read the `EXPLAIN` output of the list query yourself (index scan, no `Seq Scan`, no `Sort`).

**Exit:** tests green; UI responsive against 1M rows.

### [ ] Phase 5 — Frontend design (no code)
1. Interactive mockup of the single page in AntD's visual language, showing: populated, empty,
   loading, load error, create validation error, delete confirmation.
2. Starting point, deliberately sparse:
   - Page title, then a one-line create form (name input + "Create job" button).
   - Table: Name | Status | Actions. Status is a coloured `Tag` with text (never colour alone).
     Actions: a status control and a Delete button behind a `Popconfirm`.
   - `CursorPager` under the table: Previous / Next.
   - Errors: inline `Alert` with Retry for load failures; toast `message` for mutation results.
3. Open questions for the author: status control as `Select` vs a small button menu (AntD `Select` is
   not a native `<select>`, fiddlier for Playwright and screen readers); show a "Created" column?
4. Iterate until sign-off.

**Manual check (author):** the sign-off itself; check every listed state is in the mockup.

**Exit:** design approved by the author.

### [ ] Phase 6 — Frontend implementation
1. `types/job.ts`: `JOB_STATUSES` as a `const` tuple, `JobStatusType` derived from it, `Job`,
   `Page<T>`.
2. `api/client.ts`: one `fetch` wrapper throwing a typed `ApiError`. Must handle 204 with no body
   (DELETE), non-JSON error bodies (nginx 502 when the backend is down), and network failure.
   `api/jobs.ts`: `listJobs`, `createJob`, `updateJobStatus`, `deleteJob`.
3. `features/jobs/hooks.ts`: `useJobs(cursor)` and three mutations that invalidate the list.
   - After create: return to the first page so the new job is visible.
   - After a delete empties a non-first page, or the API rejects a stale cursor: reset to first.
   - Submit / row controls disabled while their request is in flight (prevents double-create).
   - Status control driven by server data, so a failed PATCH shows the old value.
4. Components per the approved design. AntD `Form` rules mirror the server rules (required,
   trimmed, max 255).
5. Remove the Phase 1 health placeholder.

**Manual check (author):** automated tests are not enough here. Click through create / update /
delete; stop the backend mid-session; use the keyboard only (Tab / Enter / Esc); double-click Create
quickly and confirm one job; page Next / Previous.

**Exit:** manual walkthrough of create / update / delete and each error state against `make up`
(including stopping the backend container); `tsc --noEmit` clean in the image build.

### [ ] Phase 7 — E2E tests
1. Replace the smoke test with two tests:
   - create a job, see it listed as `PENDING`; change its status, see the new status, still there
     after a reload;
   - create a job, delete it, it is gone.
2. Reliability rules: unique job name per test, assertions scoped to that job's row; role/label
   locators; web-first assertions, no fixed sleeps; trace kept on failure; fresh DB per run.

**Manual check (author):** tests are the check, with one addition: break a feature on purpose and
confirm the matching test goes red and `make test` exits non-zero.

**Exit:** `make test` green 3 times in a row from a clean clone.

### [ ] Phase 8 — README and final verification
1. README: prerequisites; Makefile commands; short endpoint table; performance section
   (denormalized status, keyset pagination, no `COUNT`, what the index test proves, what would
   come next); decisions and trade-offs; deferred items; time spent; prompt-engineering writeup +
   transcript link.
2. Final audit against the criteria checklist at the top of this file.
3. Fresh-clone rehearsal on macOS; on Linux too if available.
4. Export the AI session transcripts before submitting.

**Manual check (author), Phase 8:** follow the README word for word on a fresh clone, on Linux if
possible; nothing may rely on knowledge that is not written down.

## Final verification
- `make clean && make test` from a fresh clone in a temp directory: exits 0, twice in a row.
- `make test-backend`: all pytest tests pass.
- `make up`, then in the browser: create, change status, delete; stop the backend container and
  confirm the error message and Retry work.
- `make seed N=1000000`, reload, page forward several times: still responsive.
- `make stop` and `make clean` leave no containers, networks or volumes behind.

## Later (not built; design notes only)
- Status history: `GET /api/jobs/<id>/statuses/` + the deferred `(job, -timestamp)` index.
- Filter / sort: `?status=` + the deferred `(current_status, -id)` index.
- Details page: `react-router` + a `JobDetailPage` reusing `StatusTag`.
- Frontend unit tests: components are small and take data via props/hooks.
