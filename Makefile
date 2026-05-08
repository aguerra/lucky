.PHONY: tests run-dev import-csv

tests:
	uv run python -m pytest

run-dev:
	uv run fastapi dev lucky/main.py

import-csv:
	uv run python -m scripts.import_data $(CSV_FILE)
