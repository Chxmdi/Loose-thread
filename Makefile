API_DIR := services/api

.PHONY: backend-install backend-dev backend-test backend-lint backend-typecheck backend-check scripts-check mobile-check check eval hosted-worker demo-seed demo-reset demo-failure-retain demo-failure-recover demo-smoke

backend-install:
	uv sync --directory $(API_DIR) --extra dev

backend-dev:
	uv run --directory $(API_DIR) python -m uvicorn loose_thread_api.main:app --reload --port $(or $(PORT),8000)

backend-test:
	uv run --directory $(API_DIR) python -m pytest -q

backend-lint:
	uv run --directory $(API_DIR) python -m ruff check src tests

backend-typecheck:
	uv run --directory $(API_DIR) python -m mypy src

backend-check: backend-lint backend-typecheck backend-test

scripts-check:
	uv run --directory $(API_DIR) python -m ruff check ../../scripts ../../evals
	uv run --directory $(API_DIR) python -m ruff format --check ../../scripts ../../evals

mobile-check:
	npm --prefix apps/mobile run typecheck
	npm --prefix apps/mobile test

check: backend-check scripts-check mobile-check
	@echo "Repository checks passed."

eval: backend-check
	uv run --directory $(API_DIR) python ../../evals/run.py

hosted-worker:
	uv run --directory $(API_DIR) python -m loose_thread_api.orchestration

demo-smoke:
	uv run --directory $(API_DIR) python ../../scripts/e2e_demo.py

demo-seed:
	uv run --directory $(API_DIR) python ../../scripts/demo_data.py seed

demo-reset:
	uv run --directory $(API_DIR) python ../../scripts/demo_data.py reset

demo-failure-retain:
	uv run --directory $(API_DIR) python ../../scripts/failure_demo.py retain

demo-failure-recover:
	uv run --directory $(API_DIR) python ../../scripts/failure_demo.py recover
