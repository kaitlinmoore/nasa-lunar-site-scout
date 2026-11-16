# SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
# API container (FastAPI + lss engine). Built by deploy/deploy-api.sh via Cloud Build.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1     UV_LINK_MODE=copy     PYTHONUNBUFFERED=1     LSS_DATA_DIR=/data

# Dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY lss ./lss
COPY fixtures ./fixtures
# Precomputed served results, staged by deploy/deploy-api.sh (LSS_DATA_DIR=/data).
COPY bundle/served /data/cache/served
# Precomputed slope statistics (stream A's cache/terrain/), staged by deploy/deploy-api.sh.
COPY bundle/terrain /data/cache/terrain
RUN uv sync --frozen --no-dev
# /api/nl calls the Anthropic API over TLS. httpx2 (the anthropic SDK's HTTP client) verifies against the
# OS CA store on Linux, so the build fails here if the image has no CA certificates.
RUN /app/.venv/bin/python -c "from lss.api.nl import ca_certificates_available as ok; assert ok(), 'no CA certificates in the image'"

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn lss.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
