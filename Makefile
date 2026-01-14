poetry_version = 2.2.1
python_image = python:3.14-slim
app_dir = /app
result_image = poetry:$(poetry_version)
home = /tmp
uid = $(shell id -u)
port = 8000
poetry = docker run -it --rm \
	-v $(PWD):$(app_dir) \
	-v ~/.cache/pypoetry:$(home)/.cache/pypoetry \
	-e HOME=$(home) \
	-w $(app_dir) \
	-p $(port):$(port) \
	-u $(uid) \
	$(result_image) \
	sh -c "poetry $(1)"

.PHONY: poetry-image tests run-dev poetry-lock poetry-install import-csv

poetry-image:
	docker build --build-arg poetry_version=$(poetry_version) --build-arg python_image=$(python_image) -t $(result_image) .

tests: poetry-image
	$(call poetry,run python -m pytest)

run-dev: poetry-image
	$(call poetry,run fastapi dev --host 0.0.0.0 lucky/main.py)

poetry-lock: poetry-image
	$(call poetry,lock)

poetry-install: poetry-image
	$(call poetry,install)

import-csv: poetry-image
	$(call poetry,run python -m scripts.import_data $(CSV_FILE))
