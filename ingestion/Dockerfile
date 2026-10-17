FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# config/ is mounted read-only by docker-compose
CMD ["python", "-m", "ingestion"]
