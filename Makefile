PYTHON ?= python3

.PHONY: bootstrap format format-check lint typecheck test compile build package-check smoke verify clean

bootstrap:
	$(PYTHON) -m pip install -e '.[dev]'

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

format-check:
	$(PYTHON) -m ruff format --check .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -m compileall -q src tests dedektif.py

build:
	$(PYTHON) -m build --no-isolation

package-check:
	$(PYTHON) tools/verify_artifacts.py

smoke:
	PYTHONPATH=src $(PYTHON) -m dedektif_osint --version
	PYTHONPATH=src $(PYTHON) -m dedektif_osint self-test

verify: format-check lint typecheck test compile build package-check smoke

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
