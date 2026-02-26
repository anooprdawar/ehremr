# ──────────────────────────────────────────────────────────────────────────────
# Deepgram EHR/EMR Integration — Test Targets
# ──────────────────────────────────────────────────────────────────────────────
# Usage:
#   make test          Run offline tests only (unit + integration + quality)
#   make test-all      Run everything, including live tests
#   make test-live     Run only live tests (requires env vars)
#   make test-hapi     Run only the HAPI FHIR validator test (no key needed)
#   make coverage      Offline tests with HTML coverage report
#   make clean         Remove __pycache__ and coverage artifacts
# ──────────────────────────────────────────────────────────────────────────────

PYTHON     = python
PYTEST     = $(PYTHON) -m pytest
COV_FLAGS  = --cov=src --cov-report=term-missing --cov-report=html:htmlcov

.PHONY: test test-all test-live test-hapi coverage clean install

## install: Install all dependencies (use python -m pip to match active interpreter)
install:
	$(PYTHON) -m pip install -r requirements-dev.txt -q
	$(PYTHON) -m pip install -e . -q

## test: Run offline test suite (unit + integration + quality). No credentials needed.
test:
	$(PYTEST) tests/unit tests/integration tests/quality -v

## test-all: Run all tests including live tier. Set env vars first.
test-all:
	$(PYTEST) tests/ -v

## test-live: Run only the live tier. All live tests skip gracefully if env vars missing.
test-live:
	$(PYTEST) tests/live -v -m live

## test-hapi: Validate FHIR R4 output against the public HAPI server. No key needed.
test-hapi:
	$(PYTEST) tests/live/test_hapi_fhir_validator.py -v

## test-deepgram: Run live Deepgram tests. Requires DEEPGRAM_API_KEY.
test-deepgram:
	$(PYTEST) tests/live/test_deepgram_live.py -v

## test-epic: Run Epic sandbox tests. Requires EPIC_CLIENT_ID + EPIC_PRIVATE_KEY_PATH.
test-epic:
	$(PYTEST) tests/live/test_epic_sandbox.py -v

## test-cerner: Run Cerner sandbox tests. Requires CERNER_* env vars.
test-cerner:
	$(PYTEST) tests/live/test_cerner_sandbox.py -v

## coverage: Offline tests with terminal + HTML coverage report.
coverage:
	$(PYTEST) tests/unit tests/integration tests/quality $(COV_FLAGS)
	@echo ""
	@echo "HTML report: htmlcov/index.html"

## clean: Remove build artifacts.
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage .pytest_cache
