# PathForward task runner (macOS/Linux). Windows: use ./tasks.ps1
PY ?= python

.PHONY: help test data mirror fixture demo all azure
help:
	@echo "make test|data|mirror|fixture|demo|all|azure"

test:
	$(PY) -m unittest discover -s tests -t .

data:
	$(PY) scripts/generate_data.py

mirror:
	$(PY) scripts/build_mirror.py

fixture:
	$(PY) scripts/export_web_fixture.py

demo:
	$(PY) scripts/run_demo.py

all: data mirror fixture test demo

azure:
	pip install -e .[azure]
