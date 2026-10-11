# Requires only: make, bash, docker, docker compose v2.
SHELL := bash
.DEFAULT_GOAL := help

FRONTEND_PORT ?= 8080
export FRONTEND_PORT

COMPOSE := docker compose
# The test stack is a separate compose project (own containers, network and
# volume) built from the base file only, so it publishes no host ports and
# never touches the data of a running `make up` stack.
TEST_COMPOSE := docker compose -p job-dashboard-test -f docker-compose.yml --profile e2e

.PHONY: help build up test stop clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

build: ## Build the Docker images
	$(COMPOSE) build

up: ## Start the app at http://localhost:8080 (override: FRONTEND_PORT=3000 make up)
	$(COMPOSE) up -d --build --wait
	@echo "App running at http://localhost:$(FRONTEND_PORT)"

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

stop: ## Stop the running containers (data is kept)
	$(COMPOSE) stop

clean: ## Remove containers, networks and volumes of the app and test stacks
	$(COMPOSE) down -v --remove-orphans
	$(TEST_COMPOSE) down -v --remove-orphans
