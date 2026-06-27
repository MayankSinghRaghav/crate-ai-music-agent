# Crate API — FastAPI agent runtime.
# Build from the REPO ROOT (needs data/ at the right relative path):
#   docker build -f services/api/Dockerfile -t crate-api .
#   docker run -p 8000:8000 crate-api
# Runs fully in deterministic stub mode with no env vars. Add GROQ_API_KEY etc.
# via -e / --env-file to upgrade generative text in place.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CRATE_DB_PATH=/app/services/api/crate.db

WORKDIR /app

# 1) deps first (cached layer)
COPY services/api/requirements.txt ./services/api/requirements.txt
RUN pip install -r services/api/requirements.txt

# 2) app code + seed data (data/ resolves to REPO_ROOT/data inside the app)
COPY services/api ./services/api
COPY data ./data

WORKDIR /app/services/api

EXPOSE 8000

# Idempotent seed, then serve. SEED_ON_START=0 skips the seed.
CMD ["sh", "-c", "if [ \"${SEED_ON_START:-1}\" = \"1\" ]; then python scripts/seed.py; fi; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
