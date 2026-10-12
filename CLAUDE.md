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

Core requirements 1-5 of the brief + one stretch goal (backend unit tests) + one addition the
author chose: job names are unique. Nothing else is built.

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
- **Every test has a docstring:** at least one line saying what behaviour it checks (plus `:param:`
  for parametrized arguments).
- **Deferred work** gets a `TODO` in code and a one-line spoken reason (what, why deferred, fix).
- **Teaching:** The author's production stack is Flask + MySQL + Elasticsearch, with DevOps owning
  Docker/Make. Explain Django, Postgres, Dockerfile, Compose and Makefile concepts by analogy to
  that stack, with the reason and the industry practice behind each choice.
- **Frontend:** React + TypeScript + AntD. Keep the UI sparse; accessibility by default.
- Update this file at the end of each phase when anything in it stops being true.
- **`.gitignore` is project-specific** (the generic Python template ignored `lib/`, `dist/`, `build/`
  at any depth). Add only anchored or unambiguous patterns; after adding a folder, check
  `git status` shows it.
- **Migrations** are generated in the container, never hand-written, then reviewed:
  `docker compose -p job-dashboard-backend-test -f docker-compose.yml -f docker-compose.backend-test.yml
  run --rm --user "$(id -u):$(id -g)" -v "$PWD/backend:/app" backend-test python manage.py
  makemigrations jobs`. `test_migrations_match_the_models` fails if one is missing.
- **Python pins:** resolve new ones inside `python:3.13-slim-bookworm` (`pip install`, `pip freeze`),
  never from a host environment.
- **Lockfiles:** regenerate with `docker run --rm -v "$PWD/frontend":/w -w /w node:22-bookworm-slim
  npm install --package-lock-only` (same for `e2e`), never from a host `node_modules`.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Current status | Denormalized `Job.current_status`, written in the same transaction as the `JobStatus` insert | List is one indexed query with no join; `JobStatus` stays an append-only log. |
| Pagination | Keyset (cursor) in the API, Prev/Next in the UI, fixed page size of 20 | Constant cost at any depth, no `COUNT(*)` over millions of rows. |
| AntD table | `<Table pagination={false} />` + a small `CursorPager` (two `Button`s) | AntD's built-in pagination needs a `total`; a cursor API never counts. Same idea as ES `search_after` vs `from/size`. |
| `make test` | Playwright E2E only (spec-literal) | Backend tests run via `make test-backend`. |
| Backend tests | pytest + pytest-django against real Postgres, in the Dockerfile's `test` stage (`requirements-dev.txt`). Own compose project (`job-dashboard-backend-test`) and own file (`docker-compose.backend-test.yml`). Migrations stay on. | Runtime image carries no test tooling; the gate never parses the test file; tests exercise the schema that ships. |
| Delete cascade | `on_delete=CASCADE`, carried out by Django. The FK has no `ON DELETE` clause (Django 5.2 cannot declare one). | Spec is met through the API; a raw SQL delete of a job with statuses fails loudly instead of orphaning rows. `TODO` on the FK. |
| DB check constraints | `job_current_status_valid`, `jobstatus_status_type_valid`, `job_name_not_blank` (at least one non-whitespace character) | `choices` and `blank=False` are not enforced by `save()` or raw SQL (the Phase 4 seed). Serializers still give the friendly 400. |
| "Latest" status | Newest `JobStatus` = highest `id`, not latest `timestamp` | `timestamp` is a writable column; ids are assigned in insert order and `change_status` serializes inserts per job with a row lock. |
| Service validation | `services.py` validates its own input: `InvalidJobInput` (a `ValueError` subclass) for a bad name or status, `Job.DoesNotExist` for an unknown id. Serializers repeat the rules. | Services stay correct for any caller (shell, management command), not only behind the API; bad input never reaches the database as an `IntegrityError`. |
| API layer | Django REST Framework 3.18. JSON in and out only (`jobs/parsers.py` `JSONParser`, `JSONRenderer`), no browsable API. `OPTIONS` answers 405 (`DEFAULT_METADATA_CLASS: None`). `django.contrib.auth` is not installed (`UNAUTHENTICATED_USER: None`). | Industry default: serializers, viewsets, cursor pagination. JSON-only input is a security choice: a form or `text/plain` POST crosses origins without a CORS preflight, so with no auth any web page could create jobs; it now gets a 415. |
| Error bodies | Every error carries a stable `code` and an English `message` (`jobs/exceptions.py`): `{"name": [{"message", "code"}]}` for a field, `{"detail": {"message", "code"}}` for the request. Duplicate name is 409 `{"name": [{..., "code": "duplicate"}]}`. | API text and display text stay separate: the frontend maps `code` to its own copy from a JSON file (Phase 6) and never shows `message`. The tests pin the codes. |
| Error mapping | `service_errors()` context manager in `views.py`, wrapped around the service call only: `InvalidJobInput` 400, `Job.DoesNotExist` 404, `DuplicateJobName` 409. A plain `ValueError` stays a 500. | Catching every `ValueError`, globally or inside the service call, would report bugs as client mistakes. |
| Ids from URLs | `jobs/ids.py` `parse_job_id`: plain ASCII digits within bigint, else 404. Used for the path id and for the cursor position. | DRF does not check the cursor position: `?cursor=` + base64(`p=abc`) reached the query and raised `ValueError` (a 500). `int()` alone also accepts `1_0`, signs and non-ASCII digits. |
| Numeric name | `{"name": 123}` is accepted and stored as `"123"` (DRF `CharField` default), pinned by a test. | Author's choice; the service itself still refuses non-strings. |
| Seed data | `seed_jobs` command: raw SQL, one statement, names from the row's own id; the one writer outside `services.py`. Ships in the runtime image; `make seed` runs it in the `make up` stack only. | A million ORM inserts take minutes; one `INSERT ... SELECT generate_series` takes about 30 s. One statement is atomic, so jobs and status rows stay in sync. `TODO` in the command: no guard against running it on a real database. |
| Frontend serving | Multi-stage build; nginx serves static files and proxies `/api` to gunicorn | Production-shaped, single origin, no CORS config. |
| Data fetching | TanStack Query | Invalidate-after-mutation makes "UI updates dynamically" correct and small. |
| Ordering | `-id` (newest first) | Primary-key index, unique (cursor pagination requires it), no extra index. |
| PATCH contract | Body `{"status_type": "<STATE>"}`, required. Any state to any state, including the current one; every PATCH appends a `JobStatus` row. | Spec-literal. Not idempotent by design; note in README. |
| Unique job name | `UniqueConstraint` `job_name_unique` on `Job.name`; `create_job` raises `DuplicateJobName`, the API answers 409. Exact match after trimming (`Job` and `job` are two names). No new column, no idempotency key. | A POST that commits but whose response is lost gets retried; a unique name makes the retry a 409 instead of a second job, and the database settles two concurrent creates. Duplicate-safe, not replay-identical (the retry does not get the original 201). Trade-off: two jobs can never share a name; deleting a job frees its name. Costs one more index on `jobs_job`. `TODO` on the constraint: case-insensitive match (fix: unique index on `Lower("name")`). |
| Auth | None | Not in spec. `TODO` in `settings.py` + README "Security notes" (fix: DRF permission classes + owner FK, with `django.contrib.auth` and `contenttypes` back in `INSTALLED_APPS`). |
| `ALLOWED_HOSTS` | `*` in `docker-compose.yml`, strict default in `settings.py` (pinned by `test_host_header_is_checked`) | Opening the app by IP on a remote VM otherwise loads the page but every API call gets a 400, which costs more with a reviewer than the risk it removes. Accepted risk: DNS rebinding (a web page re-pointing its DNS at this machine and calling the API same-origin); small for a demo database on a port already open to the network. Strict was tried after the backend review and reverted by the author. Tighten when auth lands. In README. |
| Base images | Docker Hub only | Official Playwright image is on `mcr.microsoft.com`, which the brief does not promise. e2e image = `node:*-bookworm` + `npx playwright install --with-deps chromium`. |
| Test stack isolation | Own compose project (`job-dashboard-test`), no published host ports. Host ports live only in `docker-compose.override.yml`, which `make up` auto-loads and `make test` skips (`-f docker-compose.yml`). | Busy ports on the evaluator's machine cannot fail the gate; works on any compose v2 (no `!reset`). |
| nginx to backend | `proxy_pass` through a variable + Docker DNS `resolver`; `Host $http_host` | nginx starts and recovers when the backend is down or restarts; the forwarded Host keeps its port so DRF pagination links are correct. |
| Pinned versions | Python 3.13, Django 5.2 LTS, Postgres 17, Node 22, nginx 1.28, Vite 8, React 19, TypeScript 7, Playwright 1.64 | Exact pins in `requirements.txt` and both `package-lock.json` files (generated inside the Node image so all platforms' native binaries are locked). |

## Target layout

```
Makefile                      # build, up, test, stop, clean (+ test-backend, seed, help)
docker-compose.yml            # db, backend, frontend (+ e2e under a profile); no host ports
docker-compose.override.yml   # host port for `make up` only (FRONTEND_PORT, default 8080)
docker-compose.backend-test.yml  # pytest runner, loaded only by `make test-backend`
backend/
  Dockerfile                  # stages: base, test (pytest), runtime (default, last)
  requirements.txt  requirements-dev.txt  manage.py  pytest.ini
  gunicorn.conf.py            # drops healthy health checks from the access log; no control socket
  config/                     # settings.py, urls.py, wsgi.py, views.py (health endpoint)
  jobs/
    models.py  services.py  serializers.py  views.py  urls.py  pagination.py
    exceptions.py  ids.py     # error bodies with codes + Conflict (409); parse_job_id
    parsers.py                # JSONParser: 400 for JSON nested too deeply
    migrations/
    management/commands/seed_jobs.py  # dev tool: N jobs + status rows in one SQL statement
    tests/                    # conftest (fixtures incl. api_client), helpers (assert_in_sync,
                              # status_log, MISSING_JOB_ID),
                              # test_models, test_services, test_api, test_scale
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

### [x] Phase 1 — Walking skeleton (the gate)
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

### [x] Phase 2 — Data model (TDD)
Tests first (`pytest-django`, real Postgres in the container, `make test-backend`):
- creating a job sets `created_at` / `updated_at`; saving moves `updated_at`;
- new job defaults to `current_status = PENDING`;
- an invalid status (unknown, wrong case, empty) is rejected by the database on both tables;
- a blank or whitespace-only name is rejected by the database; 255 characters fit, 256 do not;
- deleting a job deletes its `JobStatus` rows and leaves other jobs' rows alone;
- the migration files match the models (`makemigrations --check --dry-run`).

Harness (built here): `requirements-dev.txt`, Dockerfile `test` stage, `pytest.ini`,
`docker-compose.backend-test.yml`, `make test-backend`.

Build:
- `Job`: `name` (`CharField(max_length=255)`), `created_at` (`auto_now_add`), `updated_at`
  (`auto_now`), `current_status` (`TextChoices`, default `PENDING`).
- `JobStatus`: `job` (FK, `on_delete=CASCADE`, `related_name="statuses"`), `status_type`
  (PENDING, RUNNING, COMPLETED, FAILED), `timestamp` (`default=timezone.now`).
- One `StatusType` enum shared by both models.
- `CheckConstraint` on `Job.current_status`, `JobStatus.status_type` and `Job.name` (Django
  `choices` and `blank=False` are not enforced by `save()`).
- `TODO` on the FK: cascade is ORM-side. `TODO` on `Job.current_status`: not database-enforced
  against the log; the invariant lives in `services.py` (Phase 3).
- `TODO` on `JobStatus.Meta`: `(job, -timestamp)` index — history view not specced.
- `TODO` on `Job.Meta`: `(current_status, -id)` index — no filter yet; every index taxes writes.

**Manual check (author):** read the migration file. In `psql`, `\d jobs_job` and `\d jobs_jobstatus`:
confirm the three check constraints, the FK and the index on `job_id` exist in the database itself.
No `ON DELETE` clause is expected: the cascade is Django's.

**Exit:** model tests green; the author has reviewed the migration file.

### [x] Phase 3 — Services and REST API (TDD)
**[x] 3a. Services** (`services.py`): `create_job(name)`, `change_status(job_id, status)`,
`delete_job(job_id)`, each in `transaction.atomic()`. `change_status` locks the job row with
`select_for_update()`, inserts the `JobStatus`, then saves `current_status` and `updated_at`.
`delete_job` takes the same row lock before deleting: Django's cascade is two statements (delete
the statuses, then the job), and a status change committing between them would make the second
fail on the foreign key (a 500 instead of a 204).

Model change (new migration, generated in the container): `UniqueConstraint(fields=["name"],
name="job_name_unique")` in `Job.Meta`. A named constraint rather than `unique=True`, which on a
`CharField` makes Postgres build a second (`LIKE`) index that nothing here uses.

`create_job(name)` returns the `Job`. It inserts the job and its `PENDING` row in one transaction;
if the insert violates `job_name_unique` it raises `DuplicateJobName` (defined in `services.py`)
and writes nothing. There is no "does it exist?" query first: check-then-insert is a race, the
constraint is not.

Service contract (the services are safe to call without a serializer in front of them):
- Bad input raises `InvalidJobInput` (a `ValueError`) before any query runs. `create_job` trims the name, then refuses
  blank, over-255, NUL-containing, lone-surrogate and non-string names. `change_status` refuses anything outside
  `StatusType`, and checks the status before it looks up the job.
- An unknown or deleted job id raises `Job.DoesNotExist`.
- The serializers (3b) repeat the same rules for the friendly 400; the views map `Job.DoesNotExist`
  to 404 and `DuplicateJobName` to 409. The database check constraints stay as the last line for raw SQL writers.

Sync tests. Invariant: `job.current_status` equals the `status_type` of that job's newest
`JobStatus` (newest = highest `id`). Services never accept a caller-supplied `timestamp`, so id
order and timestamp order agree. Model-level `Job.objects.create()` writes no `JobStatus`; only
`create_job` does. One shared `assert_in_sync(job)` helper, used in:
- after `create_job`: exactly one status row, `PENDING`, in sync;
- duplicate name: a second `create_job` raises `DuplicateJobName` and writes nothing (also when
  only surrounding whitespace differs); a different case is a different name; a deleted job
  releases its name; several threads creating one name make one job and one status row;
- model test: the database refuses a second job with the same name;
- `create_job` with an invalid name raises `ValueError` and writes nothing; whitespace is trimmed;
  255 characters after trimming fit;
- `change_status` with an invalid status raises `ValueError` and writes nothing, even when the job
  id is also unknown;
- after a sequence of changes: row count is 1 + N, in sync after each step;
- rollback: force the `Job` save to raise after the `JobStatus` insert; no new status row exists
  and `current_status` is unchanged;
- concurrency: several threads call `change_status` on one job with different states
  (`django_db(transaction=True)`); row count is 1 + threads and in sync;
- `updated_at` moves after `change_status` (`save(update_fields=[...])` skips `auto_now` fields
  unless listed);
- `change_status` on a missing or just-deleted job raises not-found and writes nothing;
- `delete_job` removes the job and its log only; a missing id raises not-found; a delete racing a
  status change never ends in a foreign key error or an orphan row;
- `seed_jobs` output is in sync (Phase 4).

**Verify 3a (author), before 3b starts:** `make test-backend` green with nothing skipped in
`test_services.py`. In a Django shell in the backend container (`python manage.py shell`), call
`create_job` (twice with the same name: the second raises `DuplicateJobName`) and `change_status`
a few times, then in `psql` check `\d jobs_job` shows `job_name_unique`, and compare `jobs_job.current_status` with
the newest `jobs_jobstatus` row for that job. Remove `transaction.atomic()` from `change_status` on
purpose and confirm the rollback test goes red; remove `select_for_update()` and confirm the lock
test goes red; restore both.

**Exit 3a:** service tests green; both break-it checks went red; the author has read `services.py`.

**[x] 3b. API.** skeleton tests, then the plan, then code. Reuse from 3a: the `job`, `other_job` and `run_in_threads` fixtures
(`tests/conftest.py`) and `assert_in_sync` (`tests/helpers.py`). Views call the three services and
never write models directly; they map `InvalidJobInput` to 400, `Job.DoesNotExist` to 404 and
`DuplicateJobName` to 409.

Files: (`serializers.py`, `views.py`, `pagination.py`, `urls.py`, `exceptions.py`, `ids.py`, `parsers.py`); viewset limited to
list / create / partial_update / destroy; no authentication classes.
- POST/PATCH bodies containing `current_status` do not change it.
- `GET /api/jobs/`: `{next, previous, results}`; fields `id`, `name`, `current_status`,
  `created_at`, `updated_at`; newest first; page of 20; walking `next` to the end returns every
  job exactly once; a garbage `cursor` gives a 4xx, not a 500; empty table gives empty results.
- `POST /api/jobs/`: 201 + one `PENDING` row; blank, whitespace-only, missing, over-255 and
  NUL-containing names give 400 with a field error; surrounding whitespace trimmed; a name that
  already exists gives 409 and writes nothing. A number as the name is stored as its text.
  A body that is not a JSON object gives 400; malformed or too deeply nested JSON 400; a
  non-JSON content type 415.
- `PATCH /api/jobs/<id>/`: 200 + appended row; missing / unknown / wrong-case `status_type` gives
  400 and writes nothing; unknown id gives 404; same status as current still appends.
- `DELETE /api/jobs/<id>/`: 204 with empty body; statuses gone; second delete gives 404.
- A non-numeric id, or one larger than a bigint, gives 404, not 500.
- Every error body has a `code` (see Decisions, "Error bodies").
- PUT, OPTIONS and `GET /api/jobs/<id>/` give 405 (not in the brief).
- A `Host` header outside the allowed list gives 400 under the `settings.py` default (compose allows any).

Audit pass before leaving the phase: validation, auth (deferred, TODO), idempotency (POST is
duplicate-safe through the unique name; PATCH appends by design), atomicity, failure handling, limits, concurrency,
observability (gunicorn access log to stdout), tests.

Audit result (3b): cursor position unchecked by DRF, closed in `pagination.py`; cross-site form
POST closed by JSON-only parsers; lone surrogate in a name closed in `_clean_name`. Closed after
the backend code review: deeply nested JSON giving a 500
(`parsers.py`), `OPTIONS` describing the wrong schema (405), any `ValueError` in a service mapped
to 400 (`InvalidJobInput`), tests shipped in the runtime image (`Dockerfile`). Deferred with
a `TODO` in code: no body-size or rate limit of the API's own (`settings.py`; nginx's 1 MB default
is the only cap); no `lock_timeout` / `statement_timeout` (`settings.py`, at `DATABASES`);
invisible characters and un-normalised Unicode in names (`services._clean_name`); unexpected exceptions and unrouted URLs (`/api/jobs/2.5/`, `/api/nope/`) answer
with Django's HTML page, not JSON (`exceptions.py`). Known and left: a request without the trailing
slash (`PATCH /api/jobs/2`) gets Django's 301 to the slashed URL, which clients may replay as GET.

**Verify 3b (author):** `make test-backend` green. `curl` all four endpoints through nginx
(`make up`), plus bad inputs: blank name, unknown status, garbage cursor, unknown id. Watch
`docker compose logs backend` while doing it: every request shows one access-log line and no
traceback.

**Exit 3b (closes the phase):** API tests green; `curl` walkthrough done; audit pass done; `make test`
still green.

### [~] Phase 4 — Scale guards (small; first to cut) — built, awaiting author review
1. `seed_jobs` management command: N jobs + initial statuses via
   `INSERT ... SELECT generate_series(...)`. `make seed N=1000000`. The raw SQL must supply
   every column (`created_at`, `updated_at`, `current_status`, `timestamp`): Django's `default`,
   `auto_now_add` and `auto_now` are applied in Python, the columns have no database default.
   Names must be unique and must not collide on a second `make seed`: derive each from the
   row's own id.
   Built as one statement (two CTEs): ids are drawn from the table's sequence first, the name
   is `Seeded job <id>`, a name already taken is skipped (`ON CONFLICT (name) DO NOTHING`) and
   only inserted jobs get a status row. Count must be 1 to 10,000,000 per run. `make seed`
   runs it with `exec` in the `make up` stack, so the app must be running; the test stacks
   never see seeded rows.
2. `test_scale.py`:
   - list endpoint runs the same number of queries for 1 job and for a full page (no N+1);
   - seed ~20k rows, `ANALYZE`, `EXPLAIN` the list query: uses the primary-key index, no
     `Seq Scan`, no `Sort`.
3. Manual: seed 1M, open the UI, page forward; note the result for the README.
   Measured on the API (throwaway stack, Apple Silicon laptop, 2026-10-11): seeding 1M jobs
   took 29 s; 200 consecutive pages median 1.4 ms, max 20 ms; a page at id < 500,000 took
   4 ms; plan is `Index Scan Backward using jobs_job_pkey`, 0.03 ms execution; tables are
   170 MB (`jobs_job`) and 100 MB (`jobs_jobstatus`). The UI half of this check waits for
   Phase 6, when the page has a list.

**Manual check (author):** automated tests are not enough here. Seed 1M rows, page through the UI,
and read the `EXPLAIN` output of the list query yourself (index scan, no `Seq Scan`, no `Sort`).

**Exit:** tests green; API responsive against 1M rows (UI check moves to Phase 6).

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
   - Error text comes from a JSON file in the frontend keyed by the API's error `code`
     (`duplicate`, `blank`, `max_length`, `required`, ...), with a generic fallback for unknown
     codes; the API's `message` is never shown. A 409 `duplicate` is shown on the name field.
   - Take the `cursor` value out of the API's `next` / `previous` links and call the relative
     `/api/jobs/?cursor=...`; do not follow the absolute URL (its scheme is the one Django sees).
   - Always send the trailing slash (`/api/jobs/<id>/`); without it Django answers 301.
   - Status control driven by server data, so a failed PATCH shows the old value.
4. Components per the approved design. AntD `Form` rules mirror the server rules (required,
   trimmed, max 255).
5. Remove the Phase 1 health placeholder.

**Manual check (author):** automated tests are not enough here. Click through create / update /
delete; stop the backend mid-session; use the keyboard only (Tab / Enter / Esc); double-click Create
quickly and confirm one job; page Next / Previous. `make seed`, then page forward through the 1M
rows (carried over from Phase 4).

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
   come next; the unique index on `name` is one more index checked on every insert); decisions and
   trade-offs (including: PATCH requires `status_type` and does not rename, read from the
   brief's "Update a job... should involve creating a new JobStatus entry"); deferred items; time spent; prompt-engineering writeup +
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
