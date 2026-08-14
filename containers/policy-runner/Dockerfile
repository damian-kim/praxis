FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/praxis
COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 praxis
USER praxis
ENTRYPOINT []
