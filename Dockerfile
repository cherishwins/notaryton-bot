# syntax=docker/dockerfile:1

# =============================================================================
# NotaryTON / MemeSeal Telegram bot — deployable image for one shared Docker host
# aiogram + FastAPI (uvicorn) webhook server on $PORT, PostgreSQL via asyncpg.
#
# Secrets (BOT_TOKEN, TON_WALLET_SECRET, DATABASE_URL, TON/TonAPI/Twitter keys,
# wallet addresses, ...) are RUNTIME env only — nothing is baked into a layer.
# =============================================================================

# ---- Stage 1: build wheels into an isolated venv -----------------------------
# Base images are digest-pinned for reproducible, supply-chain-verifiable builds.
# `3.11-slim` is a mutable tag; the digest freezes exactly what runs. Update
# deliberately: `docker buildx imagetools inspect python:3.11-slim` for the new
# index digest, then bump both stages together.
FROM python:3.11-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv

# Install from prebuilt wheels only. Every dependency here publishes a
# cp311 manylinux wheel (asyncpg, cryptography, uvloop/httptools via
# uvicorn[standard], pytoniq, aiogram, ...), so no C toolchain is required
# and the builder stays slim. If a future dep ships sdist-only, add
# build-essential via apt in this stage (it is discarded from runtime).
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install --only-binary=:all: -r requirements.txt

# ---- Stage 2: slim runtime ---------------------------------------------------
# Same digest as the builder — one pinned base for both stages.
FROM python:3.11-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

# Non-root user.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser

# Bring in the prebuilt venv (no compilers, no pip cache in the final image).
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# App code (build context is trimmed by .dockerignore — no secrets, no .git,
# no data/, no heavy asset source dirs).
COPY . .

# Least privilege: the application code stays owned by root and read-only to the
# runtime user, so a compromise of bot.py (which parses untrusted Telegram and
# webhook input) cannot rewrite .py files in place for persistence. Only the one
# runtime-writable path — downloads/, for temp file fetches — is handed to
# appuser. (Under docker-compose.prod.yml this dir is further replaced by a
# tmpfs on a read-only root filesystem; chowning it here keeps the image usable
# on its own, e.g. a plain `docker run` without that tmpfs.)
RUN mkdir -p downloads \
 && chown appuser:appuser downloads

USER appuser

# FastAPI/uvicorn webhook + health server. $PORT is overridable at runtime;
# EXPOSE documents the default the reverse proxy (Caddy) should target.
EXPOSE 8000

# Hits the app's own /health route using only the stdlib — no curl needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=4).status==200 else sys.exit(1)" \
  || exit 1

CMD ["python", "bot.py"]
