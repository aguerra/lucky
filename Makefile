poetry_version = 2.2.1
python_image = python:3.14-slim
app_dir = /app
result_image = poetry:$(poetry_version)
home = /tmp
uid = $(shell id -u)
port = 8000
poetry_run = docker run -it --rm \
		-v $(PWD):$(app_dir) \
		-v ~/.cache/pypoetry:$(home)/.cache/pypoetry \
		-e HOME=$(home) \
		-w $(app_dir) \
                -p $(port):$(port) \
		-u $(uid) \
		$(result_image) \
		sh -c "poetry run $(1)"

.PHONY: poetry-image test run-dev

poetry-image:
	docker build --build-arg poetry_version=$(poetry_version) --build-arg python_image=$(python_image) -t $(result_image) .

tests: poetry-image
	$(call poetry_run,python -m pytest)

run-dev: poetry-image
	$(call poetry_run,fastapi dev --host 0.0.0.0 lucky/main.py)
