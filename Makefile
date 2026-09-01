SHELL := /bin/bash
API_DIR := services/api

.PHONY: backend-install backend-dev backend-test backend-lint backend-typecheck backend-check check demo-smoke

backend-install:
	cd $(API_DIR) && python -m pip install -e '.[dev]'

backend-dev:
	cd $(API_DIR) && python -m uvicorn loose_thread_api.main:app --reload --port $${PORT:-8000}

backend-test:
	cd $(API_DIR) && python -m pytest -q

backend-lint:
	cd $(API_DIR) && python -m ruff check src tests

backend-typecheck:
	cd $(API_DIR) && python -m mypy src

backend-check: backend-lint backend-typecheck backend-test

check: backend-check
	@echo "Repository checks passed."

demo-smoke:
	bash scripts/demo_smoke.sh
