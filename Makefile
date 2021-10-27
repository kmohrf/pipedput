include makefilet-download-ondemand.mk

PYRIGHT_BIN = pyright
COVERAGE_BIN ?= $(PYTHON_BIN) -m coverage

.PHONY: default-target
default-target: help

include ./make.d/ci.mk

.PHONY: lint-python-pyright
lint-python-pyright:
	$(PYRIGHT_BIN) --verbose pipedput

lint-python: lint-python-pyright

.PHONY: test-report
test-report:
	$(COVERAGE_BIN) report

.PHONY: test-report-short
test-report-short:
	$(MAKE) test-report | grep TOTAL | grep -oP '(\d+)%$$' | sed 's/^/Code Coverage: /'
