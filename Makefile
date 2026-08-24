PYTHON ?= .venv/bin/python

.PHONY: run test check analyze-example

run:
	PYTHONPATH=src $(PYTHON) -m pancontext

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m pip check

analyze-example:
	PYTHONPATH=src $(PYTHON) -m pancontext analyze \
		--source-type linear_reference \
		--source-name GRCh38 \
		--sequence-id chr1 \
		--window-start 100 \
		--sequence AACCGG \
		--position 103 \
		--ref C \
		--alt T \
		--pretty
