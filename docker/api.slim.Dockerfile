# syntax=docker/dockerfile:1
#
# The API without the machine-learning stack.
#
# `docker/api.Dockerfile` builds the full image — torch, scipy, scikit-learn —
# and that is what the scheduled cycle needs, because the cycle fits models and
# runs agents. The API does neither. It answers questions about what the
# protocol already did, and every one of those answers is a database read.
#
# The difference is not cosmetic. The full image is ~3.35GB and the container
# idles at 652MiB with torch imported, which does not fit a 512MB instance. This
# one carries no torch at all, so the API can run somewhere small while the
# fitting happens on a schedule where a slow, fat job is fine.
#
# What makes this safe rather than a gamble is that the split is verified: every
# router and service in `apps/api` imports clean of torch, and the one endpoint
# that did not — /api/market/training — now reads the snapshot pointer through
# `ml.training.dataset`, which imports numpy and nothing else.
#
# If something in the API ever does need to fit a model, it will fail loudly on
# an ImportError here rather than quietly working in development and blowing the
# memory limit in production.

FROM python:3.11-slim
WORKDIR /app

# curl is needed by the compose healthcheck and by Render's health check.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements-slim.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/ ./
# The agent runtime lives at the repo root per v2 section 4. Copied in because
# the API imports the read-side of it — market ingest, settlement, scoring,
# allocation — all of which are torch-free. The graph nodes are here too and
# will raise on import of torch if anything tries to run inference in this
# image, which is the intended failure.
COPY agents/ ./agents/
COPY ml/ ./ml/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
