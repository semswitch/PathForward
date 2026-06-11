# PathForward task runner (macOS/Linux). Windows: use ./tasks.ps1
PY ?= python

.PHONY: help test data mirror all azure
help:
	@echo "make test|data|mirror|all|azure"

test:
	$(PY) -m unittest discover -s tests -t .

data:
	$(PY) scripts/generate_data.py

mirror:
	$(PY) scripts/build_mirror.py

all: data mirror test

azure:
	pip install -e .[azure]
