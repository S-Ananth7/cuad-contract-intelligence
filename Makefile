.PHONY: help setup lint test check db-up db-down db-shell pipeline load-run worker live

help:  ## List the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /  /'

setup:  ## Install the package with the development tools
	pip install -e ".[dev,api]"

lint:  ## Check code style and unused names
	ruff check .

test:  ## Run the tests (database tests skip when no database is reachable)
	python -m pytest -q

check: lint test  ## What CI runs

db-up:  ## Start the Postgres + pgvector container
	docker compose up -d db

db-down:  ## Stop it (data stays in the volume)
	docker compose down

db-shell:  ## Open psql inside the container
	docker compose exec db psql -U cuad -d cuad

pipeline:  ## Run extract, route, review and decide (see README for the settings)
	python -m cuad_ai pipeline

worker:  ## Run the live-review worker (processes uploaded contracts)
	python -m cuad_ai worker

live:  ## Open the live-review page (needs the worker running)
	streamlit run app/live_app.py

load-run:  ## Store the committed final test run in Postgres (python scripts/load_run.py <folder> for another)
	python scripts/load_run.py
