PYTHON ?= python3

.PHONY: check
check:
	$(PYTHON) scripts/validate.py

