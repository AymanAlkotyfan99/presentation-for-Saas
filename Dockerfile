# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.7.22@sha256:629240833dd25d03949509fc01ceff56ae74f5e5f0fd264da634dd2f70e9cc70 AS uv

FROM python:3.11-slim-trixie@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS fastapi-builder

WORKDIR /app/servers/fastapi

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/
RUN python -m venv --without-pip /opt/venv

COPY servers/fastapi/pyproject.toml servers/fastapi/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.txt

COPY servers/fastapi /app/servers/fastapi
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-deps .
# mem0/spaCy BM25 lemmatization loads en_core_web_sm at runtime; spaCy tries pip to
# download it otherwise. Runtime image has no pip in PATH (--without-pip venv).
ADD --checksum=sha256:1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85 \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
    /tmp/en_core_web_sm-3.8.0-py3-none-any.whl
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python \
    /tmp/en_core_web_sm-3.8.0-py3-none-any.whl \
    && rm -f /tmp/en_core_web_sm-3.8.0-py3-none-any.whl
ENV ENABLE_SEMANTIC_ICON_SEARCH=false \
    ALLOW_UNVERIFIED_FASTEMBED_MODELS=false


FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS nextjs-builder

WORKDIR /app/servers/nextjs

ENV NEXT_TELEMETRY_DISABLED=1

COPY servers/nextjs/package.json servers/nextjs/package-lock.json ./
COPY servers/nextjs/scripts/prepare-vendor-assets.mjs ./scripts/prepare-vendor-assets.mjs
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY servers/nextjs /app/servers/nextjs
RUN npm run build \
    && rm -rf .next-build/cache


FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS assets-builder

WORKDIR /app

ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json /app/
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev --no-fund --no-audit

RUN mkdir -p /app/document-extraction-liteparse

COPY electron/resources/document-extraction/liteparse_runner.mjs /app/document-extraction-liteparse/liteparse_runner.mjs
COPY scripts/sync-presentation-export.cjs /app/scripts/sync-presentation-export.cjs
COPY config/artifact-integrity.json /app/config/artifact-integrity.json
# Bundled export still loads @img/sharp-* native addons from node_modules (not inlined).
RUN rm -rf /app/presentation-export \
    && EXPORT_RUNTIME_ARCH="${TARGETARCH}" node /app/scripts/sync-presentation-export.cjs --force \
    && find /app/presentation-export/py -maxdepth 1 -type f -name "convert-linux-*" -exec chmod +x {} \; \
    && test -f /app/node_modules/sharp/package.json


FROM python:3.11-slim-trixie@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS runtime

WORKDIR /app

ARG INSTALL_TESSERACT=true
ARG TARGETARCH
ARG CHROMIUM_VERSION=149.0.7827.196-1~deb13u1
ARG CHROMIUM_SNAPSHOT=20260625T180000Z

# LiteParse uses Node + @llamaindex/liteparse (same runner as Electron); OCR uses Tesseract.
ENV APP_DATA_DIRECTORY=/app_data \
    TEMP_DIRECTORY=/tmp/presenton \
    EXPORT_PACKAGE_ROOT=/app/presentation-export \
    EXPORT_RUNTIME_DIR=/app/presentation-export \
    BUILT_PYTHON_MODULE_PATH=/app/presentation-export/py/convert-linux-current \
    PRESENTON_APP_ROOT=/app \
    ENABLE_SEMANTIC_ICON_SEARCH=false \
    ALLOW_UNVERIFIED_FASTEMBED_MODELS=false \
    PATH="/opt/venv/bin:${PATH}" \
    NODE_ENV=production \
    START_OLLAMA=false \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

RUN set -eux; \
    printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99snapshot; \
    printf 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/%s trixie-security main\n' "$CHROMIUM_SNAPSHOT" > /etc/apt/sources.list.d/chromium-snapshot.list; \
    packages="ca-certificates nginx fontconfig imagemagick zstd \
    fonts-liberation fonts-noto-core fonts-noto-extra fonts-noto-mono fonts-noto-ui-core fonts-noto-ui-extra \
    fonts-noto-cjk fonts-noto-cjk-extra fonts-noto-color-emoji xdg-utils \
    libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 \
    libcairo2 libcups2t64 libdbus-1-3 libdrm2 libexpat1 libgbm1 \
    libglib2.0-0t64 libgtk-3-0t64 libnspr4 libnss3 libpango-1.0-0 \
    libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxkbcommon0 libxrandr2 libxshmfence1 libxss1 libxtst6"; \
    if [ "$INSTALL_TESSERACT" = "true" ]; then packages="$packages tesseract-ocr tesseract-ocr-eng"; fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends --allow-downgrades \
    $packages \
    chromium="${CHROMIUM_VERSION}" \
    chromium-common="${CHROMIUM_VERSION}" \
    chromium-driver="${CHROMIUM_VERSION}"; \
    apt-mark hold chromium chromium-common chromium-driver; \
    rm -rf /var/lib/apt/lists/*

# Remove any non-Noto fonts that may have been installed as dependencies.
RUN find /usr/share/fonts -type f ! -iname 'Noto*' -delete \
    && find /usr/share/fonts -type d -empty -delete \
    && fc-cache -fsv

RUN mkdir -p /app/scripts /app/servers/fastapi /app/servers/nextjs
RUN mkdir -p /app_data/exports /app_data/images /app_data/uploads /app_data/fonts /app_data/templates /app_data/pptx-to-html /app_data/pptx-to-json \
    && chmod -R a+rX /app_data

COPY --from=fastapi-builder /opt/venv /opt/venv
COPY --from=fastapi-builder /app/servers/fastapi /app/servers/fastapi
COPY --from=nextjs-builder /app/servers/nextjs/public/vendor /app/servers/fastapi/static/vendor
COPY --from=nextjs-builder /usr/local/bin/node /usr/local/bin/node
COPY templates /app/templates

COPY --from=assets-builder /app/package.json /app/package.json
COPY --from=assets-builder /app/node_modules /app/node_modules
COPY --from=assets-builder /app/document-extraction-liteparse /app/document-extraction-liteparse
COPY --from=assets-builder /app/presentation-export /app/presentation-export
COPY --from=assets-builder /app/scripts/sync-presentation-export.cjs /app/scripts/sync-presentation-export.cjs
COPY --from=assets-builder /app/config/artifact-integrity.json /app/config/artifact-integrity.json

RUN set -eux; \
    if [ -z "${TARGETARCH:-}" ]; then TARGETARCH="$(dpkg --print-architecture)"; fi; \
    case "$TARGETARCH" in \
    amd64) export_arch="x64" ;; \
    arm64) export_arch="arm64" ;; \
    *) echo "Unsupported TARGETARCH: $TARGETARCH" && exit 1 ;; \
    esac; \
    test -f "/app/presentation-export/py/convert-linux-${export_arch}"; \
    ln -sf "/app/presentation-export/py/convert-linux-${export_arch}" /app/presentation-export/py/convert-linux-current; \
    chmod +x "/app/presentation-export/py/convert-linux-${export_arch}"; \
    ls -lah /app/presentation-export/py

COPY --from=nextjs-builder /app/servers/nextjs/.next-build/standalone/ /app/servers/nextjs/
COPY --from=nextjs-builder /app/servers/nextjs/public /app/servers/nextjs/public
COPY --from=nextjs-builder /app/servers/nextjs/.next-build/static /app/servers/nextjs/.next-build/static

COPY start.js LICENSE NOTICE ./
COPY scripts/presenton-terminal-banner.mjs /app/scripts/presenton-terminal-banner.mjs
COPY scripts/user-config-env.cjs /app/scripts/user-config-env.cjs
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:8000/api/v1/health/ready',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"
CMD ["node", "/app/start.js"]
