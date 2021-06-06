# load makefilet
include ./makefilet-download-ondemand.mk

BLACK_TARGETS = pipedput tests setup.py
BLACK_ARGS = --target-version py37
BLACK_BIN = $(PYTHON_BIN) -m black
PYRIGHT_BIN = pyright
COVERAGE_BIN ?= $(PYTHON_BIN) -m coverage

.PHONY: default-target
default-target: help

include ./make.d/ci.mk

.PHONY: lint-python-black
lint-python-black:
	$(BLACK_BIN) $(BLACK_ARGS) --check $(BLACK_TARGETS)

.PHONY: lint-python-pyright
lint-python-pyright:
	$(PYRIGHT_BIN) --verbose pipedput

lint-python: lint-python-black lint-python-pyright

.PHONY: test-report
test-report:
	$(COVERAGE_BIN) report

.PHONY: test-report-short
test-report-short:
	$(MAKE) test-report | grep TOTAL | grep -oP '(\d+)%$$' | sed 's/^/Code Coverage: /'

.PHONY: style
style:
	$(BLACK_BIN) $(BLACK_ARGS) $(BLACK_TARGETS)
