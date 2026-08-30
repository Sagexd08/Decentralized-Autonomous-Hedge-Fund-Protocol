# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app

# curl is needed by the compose healthcheck
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./
# CPU-only torch. The default wheel drags in ~2.5GB of CUDA runtime that no
# container here can use, and it dominates both image size and build time.
RUN pip install --no-cache-dir -r requirements.txt       --extra-index-url https://download.pytorch.org/whl/cpu

COPY apps/api/ ./
# The agent runtime lives at the repo root per v2 section 4, but runs inside
# the api process. Copied alongside so `import agents...` resolves.
COPY agents/ ./agents/
COPY ml/ ./ml/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
