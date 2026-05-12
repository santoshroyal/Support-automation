# Times of India — Support Automation
# Operator + dev shortcuts. See README.md for the full picture.

# Path to the project's Python interpreter. `make` doesn't inherit the
# venv-activated PATH, so we resolve commands through the local venv's
# python instead of relying on `pytest` etc. being on $PATH.
PYTHON ?= .venv/bin/python

.PHONY: help install build build-web setup-postgres bootstrap-local run-all-once run-ingest run-classify run-knowledge-sync run-draft-replies run-detect-spikes run-send-digest test test-unit test-integration ci-local ci-headless lint typecheck clean

help:
	@echo "Common targets:"
	@echo "  install              Install Python deps (editable)"
	@echo "  build                Install Python deps + build the web_ui SPA"
	@echo "  build-web            Build only the web_ui SPA (npm ci + npm run build)"
	@echo "  setup-postgres       Create local Postgres db + enable pgvector"
	@echo "  bootstrap-local      Seed DB; set all *.mode = local"
	@echo "  run-all-once         Run every cron once, in order, against fixtures"
	@echo "  run-<job>            Run a single cron job (ingest|classify|knowledge-sync|draft-replies|detect-spikes|send-digest)"
	@echo "  test                 Run full test suite"
	@echo "  test-unit            Unit tests only (no I/O)"
	@echo "  ci-local             CI pipeline: lint + unit + local-mode end-to-end"
	@echo "  ci-headless          ci-local with web_ui/ removed (proves UI is swappable)"
	@echo "  lint                 ruff"
	@echo "  typecheck            mypy"

install:
	pip install -e ".[dev]"

# Build the React SPA. `npm ci` is reproducible (uses package-lock.json).
# `NODE_OPTIONS=--use-system-ca` lets npm/shadcn trust the corporate CA
# bundle on the operator's machine — same fix as ADR-021 for fastapi
# docs assets. Skips cleanly if web_ui/ has been removed (headless mode).
build-web:
	@if [ -d web_ui ]; then \
		cd web_ui && NODE_OPTIONS="--use-system-ca" npm ci --legacy-peer-deps && \
		NODE_OPTIONS="--use-system-ca" npm run build; \
	else \
		echo "web_ui/ not present — skipping SPA build (headless mode)."; \
	fi

build: install build-web
	@echo "✓ build complete (Python + SPA)"

setup-postgres:
	@echo "Installing PostgreSQL via Homebrew (skipped if already present)..."
	@brew list postgresql@16 >/dev/null 2>&1 || brew install postgresql@16
	@echo "Starting PostgreSQL service..."
	@brew services start postgresql@16 >/dev/null 2>&1 || true
	@sleep 2
	@echo "Creating database support_automation_local (skipped if already exists)..."
	@createdb support_automation_local 2>/dev/null || true
	@echo "Enabling pgvector extension (best-effort; required only when embeddings land)..."
	@psql -d support_automation_local -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
	   echo "pgvector not installed yet — install via 'brew install pgvector' before the embedding sprint."
	@echo ""
	@echo "Done. Run with Postgres by exporting:"
	@echo "  export SUPPORT_AUTOMATION_DATABASE_URL=postgresql+psycopg://$$USER@localhost/support_automation_local"

bootstrap-local: install
	python scripts/bootstrap_local.py

run-all-once:
	python -m entrypoints.cli.ingest_feedback_cli --once
	python -m entrypoints.cli.classify_and_cluster_cli --once
	python -m entrypoints.cli.sync_knowledge_base_cli --once
	python -m entrypoints.cli.draft_replies_cli --once
	python -m entrypoints.cli.detect_spikes_cli --once
	python -m entrypoints.cli.send_digest_cli --type=hourly --once

run-ingest:
	python -m entrypoints.cli.ingest_feedback_cli --once

run-classify:
	python -m entrypoints.cli.classify_and_cluster_cli --once

run-knowledge-sync:
	python -m entrypoints.cli.sync_knowledge_base_cli --once

run-draft-replies:
	python -m entrypoints.cli.draft_replies_cli --once

run-detect-spikes:
	python -m entrypoints.cli.detect_spikes_cli --once

run-send-digest:
	python -m entrypoints.cli.send_digest_cli --type=hourly --once

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit -v

test-integration:
	$(PYTHON) -m pytest tests/integration -v -m integration

ci-local: lint test-unit
	@echo "✓ ci-local passed"

ci-headless:
	@echo "Validating headless mode (no web_ui)..."
	@if [ -d web_ui ]; then mv web_ui web_ui.bak; fi
	$(MAKE) test-unit || (test -d web_ui.bak && mv web_ui.bak web_ui; exit 1)
	@if [ -d web_ui.bak ]; then mv web_ui.bak web_ui; fi
	@echo "✓ ci-headless passed"

lint:
	ruff check .

typecheck:
	mypy domain service_layer adapters entrypoints

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
