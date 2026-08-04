FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build with C:/Users/tiron/Desktop as the context so the pinned sibling source
# can be installed without copying its Git metadata or runtime files.
COPY lunar-forge/pyproject.toml lunar-forge/README.md /build/lunar-forge/
COPY lunar-forge/lunar_forge /build/lunar-forge/lunar_forge
COPY lunar-forge-web/backend/pyproject.toml lunar-forge-web/backend/README.md /build/web/
COPY lunar-forge-web/backend/src /build/web/src

RUN python -m pip install --no-cache-dir /build/lunar-forge /build/web

WORKDIR /app
USER 65532:65532
EXPOSE 8080

CMD ["lunar-forge-web-api"]
