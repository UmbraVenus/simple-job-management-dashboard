# Job Management Dashboard take-home


## You  <sub>2026-10-11 14:48</sub>

@"/Users/REDACTED_USER/Downloads/Job Management Dashboard.pdf"
So I am tasked with this take home assignment, simple job management dashboard. It's approximately 4 hours of time, so it shouldn't be over the top complex and be mindful of the scope. For this plan, let's only focus on the core requirements for now, and the stretch goal of adding backend unit tests, we are using TDD to pair with AI (other stretch goals besides backend unit tests are out of scope, for now, but maybe think of extensibility of the core requirements to meet those later). and in terms of standard, keep evaluation criteria in mind. Let's make a claude md for those criteria, and put the plans there

The company I am interviewing for is the reviewer: [link removed], they offer HPC in a lot of different industries, take that into context on how you are planning this. 

I want to do this in short increment phases, so when you make the plan, try to divide them into small phases, the first thing that came to mind is bc there is a hard requirement of setup: 

<pasted_content id="70f0">
We will first attempt to build and run tests on a modern Linux or Mac OS installation. You may
only assume the following about the environment:
1. The system has the following software installed:
● make
● docker
● docker compose v2
● bash
2. The system can access DockerHub over the internet.
After extracting the source code archive, or cloning it from a Git repo, we will enter the top-level
project directory and execute make test The build and test should be fully repeatable and
should not require any software installed on the host system with the exception of what is
specified above.
If this step fails, we will not proceed any further with the evaluation
</pasted_content id="70f0">

that we should probably make a skeleton to make sure this step pass first, and then we can add a plan for backend, frontend, testing(this could be part of backend/frontend), deployment&verification, or if you have any suggestions of how we can plan this in phases.

There are something to keep in mind tho, in my current job, we use flask and mysql/elasicsearch for production, so django and postgresql is new to me in the professional sense, it would be great if you can keep that in mind, and if i have any questions regarding django/postgresql, try to make analogy to my current work stack so I ramp up faster. Same with dockerfile and makefile, I have learned them in school, and in my current job, most of that were handled by devOps, I use them, but not that familiar with them as much as i do flask and mysql etc. And bc some of these could be new to me, while we are making the plan, please also give me the reason why and what's some industry best practices and exmaples so I can also learn in the meantime.
and the requirements specifically call out millions of jobs being handled, so we need to keep that in mind in the design, performance is v important, I think we might need to add unit tests to stress test the system.

for frontend, react and typescript is what I used in a professional requirement so that's self explanatory, but I'd like you to style the application in ANTD, the styling library at my current work, but speed and also ease of adding accessibility. same thing here, in terms of UI/UX, simply look at the current scope, what's best practice and some examples? (try not to overcomplicate the UI, and try not to crowd the UI) in the frontend phase, I might want to see a design first and iterate before I implement anything, so please add a design step in ur frontend plan too.

This plan will be fairly long, so we might need to iterate a few steps, feel free to ask me more clarifying questions before u compose the plan.

For this take home assignment project, try not to commit for me.


## Claude  <sub>2026-10-11 14:48</sub>

> *Tool:* `Read` — /Users/REDACTED_USER/Downloads/Job Management Dashboard.pdf
> *Tool:* `Bash` — List tracked files and repo contents
> *Tool:* `Bash` — Check which PDF text extraction tools are available
> *Tool:* `Bash` — Extract the assignment PDF's text using macOS PDFKit

> **Claude asked:** How should the API get each job's current status when there are millions of jobs?
> - Denormalize (Recommended): Add an indexed current_status column on Job, written in the same DB transaction as the JobStatus insert. JobStatus stays the append-only history. List is one indexed query, and the filter-by-status stretch goal becomes trivial later. Cost: one field beyond the spec's Job field list, which we justify in the README.
> - Subquery on read: Keep Job exactly as the spec lists it and annotate the latest JobStatus per row using a (job_id, timestamp DESC) index. Fine for listing one page, but filtering or sorting by status across millions of rows later would be slow.
> **Claude asked:** How should the job list page through a huge dataset? This drives both the API and the UI design.
> - Cursor + Prev/Next (Recommended): Keyset (cursor) pagination in the API, AntD Table with Previous/Next and a page-size picker. Constant-time at any depth and no COUNT(*) over millions of rows. Trade-off: no 'jump to page 500' and no total count.
> - Cursor + infinite scroll: Same keyset API, but a virtualized list that loads more as you scroll. Feels modern, but is harder to make accessible and harder to test reliably in Playwright.
> - Numbered pages: Classic offset pagination with page numbers and a total. Most familiar UI, but OFFSET and COUNT(*) both degrade badly in Postgres at millions of rows.
> **Claude asked:** What should `make test` run, and how should we prove performance at scale? The evaluator stops if `make test` fails, so it must be fast and deterministic.
> - Unit + E2E, perf separate (Recommended): `make test` runs backend unit tests then Playwright. Unit tests include cheap perf guards (query-count assertions against N+1, EXPLAIN checks that the list uses the index). A separate `make seed` + `make perf` loads ~1M jobs and times the endpoints, with results quoted in the README.
> - Everything in make test: Also seed ~1M rows and run timing assertions inside `make test`. Strongest proof, but adds minutes and timing assertions can flake on a slow evaluator machine, risking the gate.
> - E2E only in make test: Follow the spec literally: `make test` is Playwright only, with `make test-backend` and `make perf` as separate targets. Safest gate, but the evaluator may never see the backend tests run.
> **Claude asked:** If the ~4 hours run short, what priority order should I use to decide what gets cut or deferred?
> - Gate > correctness > perf (Recommended): 1) `make test` passes on a clean machine, 2) all core requirements correct, 3) million-job performance, 4) code quality and type safety, 5) README and AI writeup, 6) UI polish and accessibility extras.
> - Gate > correctness > quality: Same top two, but code quality and type safety rank above performance work; performance is mostly addressed by design choices and README discussion.
> - Gate > correctness > UI: Same top two, then UI/UX polish and accessibility ahead of performance and backend test depth, since the role emphasises frontend.


## You  <sub>2026-10-11 14:59</sub>

*Answer:* The user answered: "How should the API get each job's current status when there are millions of jobs?"="Denormalize (Recommended)", "How should the job list page through a huge dataset? This drives both the API and the UI design."="ok, so i believe cursor and for millions of jobs, it's better UI/UX practice to use prev/next instead of infinite scroll, however, if we are using antd, and antd already has its own pagination etc, how would that come into play, can you explain more on this? I thought antd table needs to have a total count, was i mistaken", "What should `make test` run, and how should we prove performance at scale? The evaluator stops if `make test` fails, so it must be fast and deterministic."="ok, since the unit tests are stretch goals, and only E2E is specced as core requirement in testing, let's only add E2E in make test for now, espeically since the requirement also said make test: Runs your Playwright E2E tests.", "If the ~4 hours run short, what priority order should I use to decide what gets cut or deferred?"="4 hours is a suggested time, real life happens, and i might do 2 hours one day and 2 hours the next, let;s not think of it as hard requirement for now, if there is things to be prioritized, i will determine later. But yes, first option looks right". Read the answers carefully — they may request clarification, changes, or that you not proceed — and follow what they actually say.


## Claude  <sub>2026-10-11 15:01</sub>

> *Tool:* `Write` — /Users/REDACTED_USER/.claude/plans/users-REDACTED_USER-downloads-job-management-das-prancy-eich.md
> *Tool:* `ToolSearch` — select:ExitPlanMode
> *Tool:* `ExitPlanMode`
> *Tool:* `Write` — /Users/REDACTED_USER/.claude/plans/users-REDACTED_USER-downloads-job-management-das-prancy-eich.md
> *Tool:* `ExitPlanMode`
> *Tool:* `Write` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md

The plan now lives in [CLAUDE.md](CLAUDE.md) at the repo root, uncommitted. I chose that over an artifact because it's what you first asked for, it loads automatically in every session, and the phase checkboxes can be ticked as we go. It will ship with the repo you submit; if you'd rather the evaluators not see it, say so and I'll move the plan part elsewhere.

It is the revised plan, with the evaluation criteria as a checklist at the top and the working conventions (no commits from me, TDD, Flask/MySQL analogies) added. The "Learn" notes are left out of the file since it loads every session; I'll give them in chat as each phase starts.

Your review questions, answered in the revision:

- **Two-table sync:** Phase 3 has a dedicated set of sync tests around one invariant: `current_status` equals the newest `JobStatus` row. They cover create, a sequence of changes, a forced mid-transaction failure (rollback), concurrent updates from several threads, and the API being unable to write `current_status` directly.
- **History index:** you were right; it is now a `TODO`. Only the history stretch goal would use it.
- **`make perf`:** it was over-design, so it's cut. The brief asks you to consider and describe performance, not benchmark it. What remains is a small seed command and two tests (no N+1; the list query uses the index), marked first to cut.
- **Scope:** I checked every core bullet in the brief against a phase. Also cut: the page-size selector, the validation E2E test, `make logs`, and the "Created" column (a design-step question now).

The critique turned up these likely bugs, each now with a test or a handling rule in the plan:

- **Status choices not enforced:** Django `choices` are not checked on `save()`, so a bad status could be stored. Fix: database check constraints.
- **`updated_at` not moving:** a partial save skips auto-updated fields unless they are listed.
- **Host header in the test stack:** the browser calls `http://frontend`, which Django rejects with 400 unless `ALLOWED_HOSTS` allows it. This would have broken the gate.
- **Index test on a tiny table:** Postgres picks a full scan when the table is small, so the test seeds about 20k rows first.
- **Bad ids and cursors:** a non-numeric or oversized id, or a garbage cursor, must give a 4xx rather than a 500.
- **Frontend client:** DELETE returns no body, and nginx returns non-JSON when the backend is down; both crash a naive `response.json()`.
- **Paging edge cases:** deleting the last row on a page, or a stale cursor, resets to the first page.
- **Double-create:** the submit button is disabled while the request is in flight.

On `EXPLAIN`, since you asked for more:

- **What it does:** `EXPLAIN <query>` prints the plan Postgres would use without running it. `EXPLAIN ANALYZE` actually runs the query and adds real timings and row counts, so wrap writes in a transaction you roll back.
- **How to read it:** it is a tree, read from the innermost line outward. Each line is a step, with an estimated cost and row count.
- **MySQL equivalents:** `Seq Scan` is `type: ALL` (full table scan), `Index Scan` is `ref`/`range`, `Index Only Scan` is "Using index", and a `Sort` step is "Using filesort".
- **What we want for the job list:** a `Limit` over an `Index Scan Backward` on the primary key, touching about 21 rows. An offset query has the same shape but shows the scan reading and discarding every skipped row, which is why deep pages get slow.
- **Estimates vs actuals:** if estimated and actual row counts differ wildly, the table statistics are stale; `ANALYZE <table>` refreshes them.
- **From Django:** `queryset.explain(analyze=True)` returns the same output.

Phase 1 (the skeleton that gets `make test` green) is next; I haven't started it.


## You  <sub>2026-10-11 15:33</sub>

hahaha, can you leave my name (Sage) and the reviewer out of the claude md? since this will be a public repo


## Claude  <sub>2026-10-11 15:33</sub>

> *Tool:* `Bash` — Find mentions of the name and company in the docs
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md

Done. All six mentions of your name in [CLAUDE.md](CLAUDE.md) now read "the author". "the reviewer" was already gone from the file when I checked, so there was nothing to change there, and `README.md` has neither.

Two things still identify you or the context that you may want to decide on:

- **The teaching line** still says the author's production stack is Flask + MySQL + Elasticsearch. It's anonymous now, but it is a personal detail in a public repo.
- **Git history** carries your name as commit author, which editing files won't change.

I'll keep both names out of the code, README and any other files I write from here on.


## You  <sub>2026-10-11 15:35</sub>

i normally use pytest, is pytest-django anything special? and why are we using it over pytest


## Claude  <sub>2026-10-11 15:35</sub>

`pytest-django` isn't a replacement for pytest; it's a pytest plugin, so you're still writing plain pytest tests (functions, fixtures, `assert`, parametrize). It's the equivalent of `pytest-flask` in your current stack.

Plain pytest alone doesn't work well with Django, because Django needs setup before any model can be imported. The plugin does three things you'd otherwise hand-write in `conftest.py`:

- **Boots Django:** it reads `DJANGO_SETTINGS_MODULE` from `pytest.ini` and calls `django.setup()` before collection. Without it, importing `jobs.models` fails with "apps aren't loaded yet".
- **Manages the test database:** it creates a separate `test_<dbname>` database, runs migrations once per session, and wraps each test in a transaction that is rolled back, so tests don't leak rows into each other. In Flask you'd have written this yourself as a session-scoped fixture with `create_all()` and a rollback per test.
- **Provides fixtures:** `client` (like Flask's `app.test_client()`), `django_assert_num_queries` (which the no-N+1 test in Phase 4 uses), and `settings` for per-test overrides.

Database access is opt-in per test via `@pytest.mark.django_db`, and a test that touches the DB without the mark fails loudly. The concurrency test in Phase 3 needs `@pytest.mark.django_db(transaction=True)`: the default rollback-per-test wrapper keeps everything in one uncommitted transaction, so other threads would never see the rows. That mode really commits and then truncates the tables afterwards, which is slower, so we use it for that one test only.

The real alternative isn't plain pytest but Django's built-in runner (`manage.py test`, `unittest`-style `TestCase` classes). That works fine and saves one dependency. I picked `pytest-django` because you already know pytest, so you only have to learn the Django parts, and because DRF's own test client (`APIClient`) works with it unchanged.
