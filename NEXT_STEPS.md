# Next steps

What is not built, in the order I would do it. Smaller items are `TODO` comments in the code,
each with its reason and fix.

## 1. Before real users

- **Authentication and per-user access:** DRF permission classes and an `owner` on `Job`.
- **Strict hosts, real secret, TLS:** set `DJANGO_ALLOWED_HOSTS` and `DJANGO_SECRET_KEY`; HTTPS in front of nginx.
- **Limits:** request size and rate limits; database lock and statement timeouts.

## 2. Stretch goals from the brief

The data model already supports these.

| Goal | What it takes |
|---|---|
| Status history view | One endpoint over the `JobStatus` log, plus an index on `(job, -timestamp)`. |
| Filter / sort | `?status=` on the list, plus an index on `(current_status, -id)`. |
| Job details page | `react-router` and a detail page reusing `StatusTag`. |
| Frontend unit tests | Start with `api/decode.ts`. |

## 3. Hardening

- **Case-insensitive unique names:** unique index on `Lower("name")`.
- **JSON for every error:** unexpected errors and unknown URLs still return Django's HTML page.
- **Migrations as a release step:** running them on start is safe with one backend replica only.
- **E2E traces on failure:** copy the trace folder out of the test container.
- **Page position in the URL:** a reload returns to the first page today.

## 4. At larger scale

- **Total count:** an estimate from Postgres statistics, not `COUNT(*)`.
- **Search by name:** a trigram index.
- **Status log growth:** partition `jobs_jobstatus` by time.
