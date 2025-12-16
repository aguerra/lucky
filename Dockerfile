ARG python_image=python:latest
FROM $python_image
ARG poetry_version

ENV poetry_home=/opt/poetry
ENV PATH=$poetry_home/bin:$PATH

RUN python -m venv $poetry_home
RUN $poetry_home/bin/pip install poetry==$poetry_version

CMD ["poetry", "--version"]
