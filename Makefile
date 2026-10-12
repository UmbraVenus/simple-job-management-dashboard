# Requires only: make, bash, docker, docker compose v2.
SHELL := bash
.DEFAULT_GOAL := help

FRONTEND_PORT ?= 8080
export FRONTEND_PORT
# Number of jobs `make seed` creates.
N ?= 1000000

COMPOSE := docker compose
# The test stack is a separate compose project (own containers, network and
# volume) built from the base file only, so it publishes no host ports and
# never touches the data of a running `make up` stack.
TEST_COMPOSE := docker compose -p job-dashboard-test -f docker-compose.yml --profile e2e
# Backend unit tests get a third project: own database container and volume,
# so they can run next to `make up` or `make test` without sharing any state.
BACKEND_TEST_COMPOSE := docker compose -p job-dashboard-backend-test -f docker-compose.yml -f docker-compose.backend-test.yml

.PHONY: help build up seed test test-backend stop clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-13s %s\n", $$1, $$2}'

build: ## Build the Docker images
	$(COMPOSE) build

up: ## Start the app at http://localhost:8080 (override: FRONTEND_PORT=3000 make up)
	$(COMPOSE) up -d --build --wait
	@echo "App running at http://localhost:$(FRONTEND_PORT)"

# Runs inside the backend container of the `make up` stack (`exec`, not `run`),
# so it writes to the database the app is showing. The test stacks are separate
# projects and never see these rows.
seed: ## Add N jobs to the running app (default 1000000; needs `make up` first): make seed N=5000
	@$(COMPOSE) exec -T backend python manage.py seed_jobs "$(N)" || \
	{ echo "make seed needs the app running (make up) and N between 1 and 10000000."; exit 1; }

# One shell invocation so the trap always tears the stack down and the recipe
# exits with the Playwright exit code. A leftover stack from an interrupted run
# is removed first, so every run starts from an empty database. If startup or a
# test fails, the service logs are printed before the stack is removed.
test: ## Run the Playwright E2E tests against a fresh, isolated stack
	@trap '$(TEST_COMPOSE) down -v --remove-orphans' EXIT; \
	dump_logs() { echo "--- service logs (last 200 lines each) ---"; $(TEST_COMPOSE) logs --no-color --tail 200 db backend frontend; }; \
	$(TEST_COMPOSE) down -v --remove-orphans && \
	$(TEST_COMPOSE) build && \
	{ $(TEST_COMPOSE) up -d --wait db backend frontend || { dump_logs; exit 1; }; } && \
	{ $(TEST_COMPOSE) run --rm -T e2e || { status=$$?; dump_logs; exit $$status; }; }

# Same shape as `test`: clean leftovers, build, run, always tear down, exit with
# the pytest exit code. `run` starts db (and waits for its healthcheck) through
# depends_on; the backend and frontend services are never started.
test-backend: ## Run the backend unit tests (pytest) against a throwaway Postgres
	@trap '$(BACKEND_TEST_COMPOSE) down -v --remove-orphans' EXIT; \
	$(BACKEND_TEST_COMPOSE) down -v --remove-orphans && \
	$(BACKEND_TEST_COMPOSE) build backend-test && \
	$(BACKEND_TEST_COMPOSE) run --rm -T backend-test

stop: ## Stop the running containers (data is kept)
	$(COMPOSE) stop

clean: ## Remove containers, networks and volumes of the app and test stacks
	$(COMPOSE) down -v --remove-orphans
	$(TEST_COMPOSE) down -v --remove-orphans
	$(BACKEND_TEST_COMPOSE) down -v --remove-orphans
