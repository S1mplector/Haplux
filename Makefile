.PHONY: run test

run:
	PYTHONPATH=src python3 -m pancontext

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
