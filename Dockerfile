# syntax=docker/dockerfile:1

# --- Builder stage ---
# Previously this stage only COPYed pyproject.toml (never the actual
# `trace2pr` source) and built with `pip wheel --no-deps`, which produced a
# wheel with none of the project's dependencies (fastapi, uvicorn, ...)
# baked in — the final image would fail on the very first import.
FROM python:3.12-slim AS builder
WORKDIR /app

COPY pyproject.toml ./
COPY trace2pr ./trace2pr
COPY main.py ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip hatchling && \
    pip install --no-cache-dir .

# --- Runtime stage ---
FROM python:3.12-slim
WORKDIR /app

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /opt/venv /opt/venv
COPY trace2pr ./trace2pr
COPY main.py ./

ENV PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000
CMD ["python", "main.py"]
