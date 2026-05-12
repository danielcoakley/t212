PYTHON ?= python

.PHONY: install lint test smoke api format migrate check-openbb discovery top10 portfolio-review

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q

smoke:
	$(PYTHON) scripts/smoke_test.py

api:
	$(PYTHON) scripts/run_api.py

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

migrate:
	$(PYTHON) -m alembic upgrade head

check-openbb:
	$(PYTHON) scripts/check_openbb.py

discovery:
	$(PYTHON) scripts/run_discovery.py

top10:
	$(PYTHON) scripts/run_top10_research.py

portfolio-review:
	$(PYTHON) scripts/run_portfolio_review.py
