# Backend code review


## You  <sub>2026-10-11 22:32</sub>

manual verification look good, now can you do a code review in the backend  folder, and see if there is any gaps or performance issues, or correctness issues?


## Claude  <sub>2026-10-11 22:32</sub>

> *Tool:* `Bash` — List tracked backend files with line counts
> *Tool:* `Bash` — Print all backend source files with line numbers
> *Tool:* `Bash` — Print compose files, nginx config, and backend test target
> *Tool:* `Read` — /Users/REDACTED_USER/.claude/projects/-Users-REDACTED_USER-dev-simple-job-management-dashboard/9bd559a2-4684-4810-b68b-41369291f463/tool-results/bq06gctcv.txt
> *Tool:* `Bash` — Print compose files, nginx config, and backend test target
> *Tool:* `Bash` — List backend test names and check Docker is running
> *Tool:* `Bash` — Run throwaway probe requests against the API in an isolated test container

Finished reading the backend; now running a few throwaway probe requests in an isolated container to confirm the suspected issues before reporting (zsh quoting broke the first attempt, retrying).

> *Tool:* `Bash` — Run throwaway probe requests against the API in an isolated test container

Review done. Nothing in the repo was changed; I ran throwaway probes in a separate compose project and removed it afterwards.

**Performance: nothing to fix in what is built.** Measured statements per request:

| Request | Statements | Notes |
|---|---|---|
| List | 1 | `WHERE id < x ORDER BY id DESC LIMIT 21` on the primary key, no `COUNT` |
| POST | 2 | job insert, status insert |
| PATCH | 3 | `SELECT … FOR UPDATE`, insert, update |
| DELETE | 3 | lock, then two set-based deletes; status rows are never loaded into Python |

A hand-crafted cursor can add `OFFSET`, but DRF caps it at 1000.

## Findings, most severe first

**1. Security: `ALLOWED_HOSTS=*` leaves the app open to DNS rebinding** ([docker-compose.yml:40](docker-compose.yml:40))
- **Mechanism:** a web page on `attacker.com` re-points its DNS to `127.0.0.1`. The browser then treats `attacker.com:8080` as same-origin with the app, so a JSON `fetch` needs no preflight, and Django accepts the foreign Host.
- **Symptom:** while `make up` is running, any site the user visits can list, create and delete jobs. The JSON-only parser ([settings.py:64](backend/config/settings.py:64)) closes the form-POST route but not this one.
- **Confirmed:** `Host: evil.example:8080` gets 200 under `*` and 400 under the `settings.py` default.
- **Closes it:** default that line to `localhost,127.0.0.1,[::1],frontend`; remote-VM users set `DJANGO_ALLOWED_HOSTS`. This reverses a recorded decision, so it is your call.

**2. Correctness: deeply nested JSON gives a 500** ([views.py:39](backend/jobs/views.py:39))
- **Mechanism:** `request.data` calls `json.load`, which raises `RecursionError` on a body like `[[[[…`. DRF only converts `ValueError` to a 400.
- **Symptom:** a body of about 400 KB (under nginx's 1 MB cap) returns an HTML 500 and a full traceback in the log on every request. Nothing is written. Depth 5,000 is fine; 200,000 fails.
- **Closes it:** a `JSONParser` subclass that turns `RecursionError` into `ParseError`, registered at [settings.py:64](backend/config/settings.py:64).

**3. Validation: invisible characters pass "not blank" and "unique"** ([services.py:111](backend/jobs/services.py:111), [models.py:48](backend/jobs/models.py:48))
- **Mechanism:** `strip()` and the `\S` constraint both treat U+200B (zero-width space) as a visible character, and names are compared without Unicode normalisation.
- **Symptom:** `"\u200b"` is stored as a job that looks blank. `"job"` and `"job\u200b"` both get 201, as do the composed and decomposed forms of `café`. A right-to-left override character is also accepted.
- **Closes it:** in `_clean_name`, NFC-normalise and refuse format/control characters, with a matching serializer validator. Alternatively, a `TODO` beside the existing case-insensitive one.

**4. Failure handling: no lock or statement timeout** ([services.py:92](backend/jobs/services.py:92), [settings.py:86](backend/config/settings.py:86))
- **Mechanism:** `select_for_update()` waits indefinitely, and `DATABASES` sets no `OPTIONS`.
- **Symptom:** if any session holds a job's row lock (an open `psql` transaction, say), each PATCH or DELETE on that job occupies a worker until gunicorn kills it at 30 s. Three such requests take all three workers, the health check fails, and the whole API returns 502. This is from reading the code, not reproduced, and unlikely today because every transaction is short.
- **Closes it:** `"OPTIONS": {"options": "-c lock_timeout=5s -c statement_timeout=15s"}`, with the lock timeout mapped to 503. Or a `TODO`.

**5. Gap: `OPTIONS /api/jobs/` answers 200 with a wrong schema**
- **Mechanism:** DRF's default metadata class is still on.
- **Symptom:** the response contains the viewset docstring and describes POST with `JobSerializer`'s read-only fields instead of `name`.
- **Closes it:** `"DEFAULT_METADATA_CLASS": None` in `REST_FRAMEWORK`, which gives 405, plus a case in the 405 test.

**6. Error mapping is wider than its docstring says** ([views.py:86](backend/jobs/views.py:86))
- **Mechanism:** `except ValueError` catches any `ValueError` raised inside the service, including one from the ORM or driver.
- **Symptom:** such a bug would be returned as a 400 with `str(exc)` in the body.
- **Closes it:** an `InvalidInput(ValueError)` class raised by `_clean_name` and `_clean_status`, and catch only that.

**7. Small things**
- **Stale TODO:** [services.py:12](backend/jobs/services.py:12) says "no logging setup exists yet", but [settings.py:108](backend/config/settings.py:108) has one.
- **Test code in the runtime image:** `COPY . .` ([Dockerfile:36](backend/Dockerfile:36)) ships `jobs/tests/`, `pytest.ini` and `requirements-dev.txt`. Three `.dockerignore` lines would not work, because the `test` stage needs them; the fix is to delete them in the `runtime` stage.
- **Unused tables:** `auth` and `contenttypes` are installed only for DRF's anonymous user, so `migrate` creates their tables. `"UNAUTHENTICATED_USER": None` would let both apps go.
- **Id alias:** `/api/jobs/007/` reaches job 7. Harmless.

Already recorded as deferred and not repeated above: HTML 500/404 bodies, no rate limit, the trailing-slash 301, case-sensitive names, non-idempotent PATCH.

## Your call

Per your working agreement I have not touched code. What priority order do you want? My suggestion is 1, 2, 5 as fixes (each is a few lines plus a test), 3 and 4 as `TODO`s with a spoken reason, and 6 and 7 as cleanup if time allows.


## You  <sub>2026-10-11 22:37</sub>

@"/Users/REDACTED_USER/Downloads/Job Management Dashboard.pdf"
are those still true with this spec, if so, what are some plan to fix them


## Claude  <sub>2026-10-11 22:37</sub>

> *Tool:* `Read` — /Users/REDACTED_USER/Downloads/Job Management Dashboard.pdf
> *Tool:* `ToolSearch` — select:ExitPlanMode
> *Tool:* `Bash` — Extract the text of the spec PDF (read-only)
> *Tool:* `Bash` — Extract the spec PDF's text with macOS PDFKit (read-only)

> **Claude asked:** Which priority order and scope should the plan use?
> - Fix 1, 2, 5; TODO 3, 4 (Recommended): Fix the security and error-handling items in that order, then the stale TODO from 7. Items 3 and 4 get a TODO in code with a spoken reason. Item 6 only if time allows.
> - Fix 1, 2, 5, 6, 7; TODO 3, 4: Same as above, plus the narrower exception class, removing test code from the runtime image, and dropping the unused auth tables.
> - Fix all seven: Also implements name normalisation with invisible-character rejection, and database lock/statement timeouts with a 503 mapping. Largest change; goes beyond the spec.
> - Fix 2 and 5 only: Only the two small spec-facing error-handling items. Everything else becomes a TODO, including the ALLOWED_HOSTS decision.
> **Claude asked:** For finding 1, how should the compose default for DJANGO_ALLOWED_HOSTS change?
> - Strict default (Recommended): Default to localhost, 127.0.0.1, [::1] and frontend. Opening the app by IP or hostname on a remote VM then needs DJANGO_ALLOWED_HOSTS set, documented in the README. Reverses your recorded decision.
> - Keep * and document: Leave the default as it is. Correct the rationale in CLAUDE.md and the compose comment to name DNS rebinding as the accepted risk, and keep the TODO.


## You  <sub>2026-10-11 22:39</sub>

*Answer:* Your questions have been answered: "Which priority order and scope should the plan use?"="Fix 1, 2, 5, 6, 7; TODO 3, 4", "For finding 1, how should the compose default for DJANGO_ALLOWED_HOSTS change?"="Strict default (Recommended)". You can now continue with these answers in mind.


## Claude  <sub>2026-10-11 22:39</sub>

> *Tool:* `Bash` — Check README presence, ALLOWED_HOSTS mentions, and the related existing tests
> *Tool:* `Write` — /Users/REDACTED_USER/.claude/plans/users-REDACTED_USER-downloads-job-management-das-crystalline-wirth.md
> *Tool:* `ExitPlanMode`
> *Tool:* `Bash` — Read test helpers, README top, and Makefile variables
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/backend/jobs/tests/test_api.py
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/backend/jobs/tests/test_api.py
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/backend/jobs/tests/test_api.py
> *Tool:* `Bash` — Add remaining tests and run the backend suite expecting red
> *Tool:* `Bash` — Add the InvalidJobInput class and rerun the suite expecting the new tests red
> *Tool:* `Write` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/backend/jobs/parsers.py
> *Tool:* `Bash` — Apply the planned code changes and rerun the backend suite
> *Tool:* `Bash` — Apply the remaining edits and rerun the backend suite
> *Tool:* `Bash` — Run the E2E gate, then check the new behaviours on a throwaway stack with no host ports
> *Tool:* `Bash` — Update README and CLAUDE.md to match the changes
> *Tool:* `Edit` — /Users/REDACTED_USER/dev/simple-job-management-dashboard/CLAUDE.md

The plan is implemented and verified: `make test-backend` passes (157 tests, the five new ones seen red first) and `make test` exits 0. Nothing is committed.

I checked the behaviours on a throwaway stack with no host ports instead of `make up` + `make clean`, so your dev database volume was not touched.

| # | Change | Result on the live stack |
|---|---|---|
| 1 | [docker-compose.yml:35](docker-compose.yml:35) no longer defaults `DJANGO_ALLOWED_HOSTS` to `*`; the one default is in [settings.py](backend/config/settings.py) | `Host: evil.example:8080` gets 400; `localhost:8080` and `frontend` get 200 |
| 2 | New [parsers.py](backend/jobs/parsers.py) turns `RecursionError` into a `ParseError` | 200,000-deep JSON gets 400 `parse_error`, no traceback |
| 5 | `DEFAULT_METADATA_CLASS: None` | `OPTIONS /api/jobs/` gets 405 |
| 6 | `InvalidJobInput(ValueError)` in [services.py](backend/jobs/services.py); [views.py](backend/jobs/views.py) catches only that | a plain `ValueError` from a service is now a 500 |
| 7 | Stale `TODO` reworded; runtime image drops `jobs/tests`, `pytest.ini`, `requirements-dev.txt`; `auth` and `contenttypes` apps removed | image has no tests; a fresh database has only `django_migrations`, `jobs_job`, `jobs_jobstatus` |

Deferred, each with a `TODO` in code:
- **Invisible characters in names** ([services.py](backend/jobs/services.py), `_clean_name`): a zero-width space counts as text and names are not Unicode-normalised, so look-alike names can coexist. Deferred because the brief asks only for a non-empty string. The fix is to NFC-normalise and refuse format/control characters.
- **No lock or statement timeout** ([settings.py](backend/config/settings.py), at `DATABASES`): a held row lock parks a worker until gunicorn kills it. Deferred because every transaction here is short and nothing else writes. The fix is `lock_timeout` and `statement_timeout`, plus a 503 mapping.

Things you should know:
- **Existing `make up` volume:** it still holds the old, now unused `auth_*` and `django_content_type` tables. They are harmless; `make clean` removes them along with your data.
- **Remote access now needs a variable:** opening the app by IP or hostname loads the page but every API call gets 400 unless you run `DJANGO_ALLOWED_HOSTS=<host> make up`. The README security section says so.
- **New log noise:** a refused Host makes Django log a full `DisallowedHost` traceback. I left it; silencing it is one `LOGGING` entry for `django.security.DisallowedHost` if you want it.
- **Docs:** `CLAUDE.md` is updated (decision rows, layout, 3b audit result, and a Phase 8 README item explaining that PATCH requires `status_type` and does not rename).

Phase 3b is ready for your review.


## You  <sub>2026-10-11 22:49</sub>

For case 1, the README security section already explains the variable, but someone hitting a broken-looking page may not read that far. The cheap mitigation is to have make up print a hint next to the “App running at…” line saying remote access needs DJANGO_ALLOWED_HOSTS=<host>. I can’t edit from this side chat, so raise it in the main session if you want it.


how to make this as easy as possible for the reviewers


## Claude  <sub>2026-10-11 22:49</sub>

> *Tool:* `Bash` — Add the remote-access hint to make up and dry-run the target

I added the hint: `make up` now prints two lines under "App running at…" saying the API answers 400 from another machine until you run `DJANGO_ALLOWED_HOSTS=<IP or hostname you browse to> make up`. Dry-run only (`make -n up`); it touches the `up` target alone, so the gate is unaffected.

The hint only helps someone who reads terminal output. Three further steps, in order of how much they help a reviewer:

1. **Accept any IP-address Host automatically (my recommendation).** A reviewer on a remote VM almost always browses to `http://<ip>:8080`. Allowing IP literals is still safe against DNS rebinding, because the rebinding page sends its own domain name as Host, never an IP. Django's `ALLOWED_HOSTS` cannot express "any IP", so this needs a small middleware (about 15 lines using `ipaddress.ip_address`) plus tests. The catch is that it is hand-written host validation, which is security-sensitive code you would have to walk through. Browsing by a DNS name (for example an EC2 hostname) would still need the variable.
2. **Make the broken state explain itself in the UI (Phase 6).** A refused Host comes back as an HTML 400 on every call. The frontend's load-error `Alert` can show "If you opened this by IP or hostname, see `DJANGO_ALLOWED_HOSTS` in the README" for that case. This is cheap once the error handling exists.
3. **Put the variable in the README quick start (Phase 8).** One line directly under `make up`, not only in the security section.

A reviewer running `make test`, or `make up` on their own laptop at `localhost:8080`, never hits this at all; only remote-VM use does.

Do you want option 1 built now, or left as a `TODO` with options 2 and 3 added to the Phase 6 and Phase 8 lists in `CLAUDE.md`?


## You  <sub>2026-10-11 22:52</sub>

<!-- reply 1 -->
> Accept any IP-address Host automatically (my recommendation). A reviewer on a remote VM almost always browses to http://<ip>:8080. Allowing IP literals is still safe against DNS rebinding, because the rebinding page sends its own domain name as Host, never an IP. Django’s ALLOWED_HOSTS cannot express “any IP”, so this needs a small middleware (about 15 lines using ipaddress.ip_address) plus tests. The catch is that it is hand-written host validation, which is security-sensitive code you would have to walk through. Browsing by a DNS name (for example an EC2 hostname) would still need the variable.

ok we are going in loops, isn't this what we already reverted?how big of a security. hole it is, and should we revert his? or?


## Claude  <sub>2026-10-11 22:52</sub>

No, it is not the same thing, but you are right that we are circling, and the middleware is not worth it.

- **`*` (what we removed):** accepts any Host, including an attacker's domain name, which is what a rebinding page sends.
- **IP-only (option 1):** accepts only IP literals, which a rebinding page cannot send. It is safe, but it is custom security code added to solve a problem that the strict default created.

**How big the hole is with `*`: small.** I ranked it first because it is security-flavoured, and that overstated it for this project.

- **What an attack needs:** the app running under `make up`, and you visiting a malicious page built to target port 8080 and this API's paths at the same moment.
- **What it gets:** creating, changing or deleting jobs in a demo database with nothing sensitive in it.
- **What strict hosts does not stop:** `make up` publishes 8080 on all interfaces with no login, so anyone on the same network can already do all of that with `curl`, and can set `Host: localhost` to pass the check. The Host check only blocks the browser-mediated route.

**What strict costs:** a reviewer who runs it on a remote VM and browses by IP sees a page where every API call fails. "Setup & deployment: how easy is it to get running" is an explicit evaluation criterion, and that failure is far more likely than the attack.

**My recommendation: revert the compose default to `*` and stop there.**

- **Revert:** `DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS:-*}` in `docker-compose.yml`, and remove the `make up` hint I just added.
- **Keep:** the strict default in `settings.py` and `test_host_header_is_checked`, which pins it, so anything not started through compose stays strict.
- **Correct the docs:** the README and `CLAUDE.md` name DNS rebinding as the accepted risk (the old text said the check "protects nothing here", which was wrong) and show how to tighten it: `DJANGO_ALLOWED_HOSTS=localhost make up`.
- **No middleware.**

This is the "Keep `*` and document" option from earlier. You still show that you saw the risk and chose deliberately, and the app works wherever a reviewer opens it. All the other fixes (nested JSON, `OPTIONS`, `InvalidJobInput`, image cleanup, auth tables) are unaffected.

Shall I make that revert?


## You  <sub>2026-10-11 22:53</sub>

yea


## Claude  <sub>2026-10-11 22:53</sub>

> *Tool:* `Bash` — Revert the compose host default to *, drop the make hint, fix docs, rerun both test suites

Reverted: the compose default is `*` again, and both suites pass (`make test-backend` 157 passed, `make test` exit 0). Nothing is committed.

- **`docker-compose.yml`:** `DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS:-*}` is back. The comment now names DNS rebinding as the accepted risk and shows how to tighten it (`DJANGO_ALLOWED_HOSTS=localhost make up`).
- **`Makefile`:** the two hint lines are removed, so it is back to its committed state.
- **`settings.py`:** the strict default is unchanged and still pinned by `test_host_header_is_checked`; only the comment was updated to say compose relaxes it.
- **`README.md`:** the security note says the check is relaxed and names the risk, replacing the old claim that the check "protects nothing here".
- **`CLAUDE.md`:** the `ALLOWED_HOSTS` decision row records `*`, the accepted risk, and that strict was tried and reverted. The 3b audit paragraph no longer lists DNS rebinding as closed.

The other review fixes are untouched: nested JSON gives 400, `OPTIONS` gives 405, `InvalidJobInput`, tests out of the runtime image, and no auth tables.
