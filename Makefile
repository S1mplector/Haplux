PYTHON ?= .venv/bin/python

.PHONY: run test check analyze-example experiment-example real-data-example public-lesson

run:
	PYTHONPATH=src $(PYTHON) -m pancontext

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests scripts
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

experiment-example:
	PYTHONPATH=src $(PYTHON) -m pancontext experiment \
		--input tests/fixtures/experiment_request.json \
		--pretty

real-data-example:
	@fixture_dir="$$(mktemp -d)"; \
	trap 'rm -rf "$$fixture_dir"' EXIT; \
	$(PYTHON) -c 'import pysam; pysam.tabix_compress("tests/fixtures/cohort.vcf", "'"$$fixture_dir"'/cohort.vcf.gz", force=True); pysam.tabix_index("'"$$fixture_dir"'/cohort.vcf.gz", preset="vcf", force=True)'; \
	PYTHONPATH=src $(PYTHON) -m pancontext vcf-experiment \
		--fasta tests/fixtures/mini.fa \
		--vcf "$$fixture_dir/cohort.vcf.gz" \
		--assembly mini-v1 \
		--contig chr1 \
		--position 21 \
		--ref C \
		--alt T \
		--left-flank 10 \
		--right-flank 10 \
		--sample HG_REF \
		--sample HG_MIX \
		--pretty

public-lesson:
	$(PYTHON) scripts/prepare_1000g_lesson.py
