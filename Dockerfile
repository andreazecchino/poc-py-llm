# Building stage
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

# Enable bytecode compilation,
# copy from the cache instead of linking,
# omit development dependencies,
# disable Python downloads
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Working stage
FROM python:3.14-slim

RUN groupadd --system --gid 1000 appuser \
 && useradd --system --gid 1000 --uid 1000 --create-home appuser

COPY --from=builder --chown=appuser:appuser /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
WORKDIR /app

CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "main.py"]
