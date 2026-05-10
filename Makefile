PYTHON ?= python

.PHONY: install lint test smoke api dashboard format migrate

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
	$(PYTHON) -m isa_system.smoke_test

api:
	$(PYTHON) -m uvicorn isa_system.api.main:app --host 127.0.0.1 --port 8000

dashboard:
	$(PYTHON) -m streamlit run src/isa_system/dashboard/app.py

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

migrate:
	$(PYTHON) -m alembic upgrade head
