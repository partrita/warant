# WarAnt production image (single stage, frontend pre-built).
#
#   docker compose up --build     ->  http://localhost:8000
#
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# curl/unzip are needed by Reflex to bootstrap its bun runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY rxconfig.py ./
COPY assets ./assets
COPY scripts ./scripts
COPY warant ./warant

# Pre-build the frontend so container start is fast.
RUN .venv/bin/reflex init --log-level warning \
    && .venv/bin/reflex export --frontend-only --no-zip --log-level warning

ENV WARANT_DATABASE_URL=sqlite:////data/warant.db?check_same_thread=false
VOLUME /data
EXPOSE 8000

CMD ["/app/.venv/bin/reflex", "run", "--env", "prod", "--backend-host", "0.0.0.0"]
