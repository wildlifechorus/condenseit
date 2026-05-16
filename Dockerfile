FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# Copy the built SPA into the static dist location that FastAPI serves
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV CONDENSEIT_DATA_DIR=/app/data
RUN mkdir -p /app/data/digests

EXPOSE 8899

CMD ["condenseit", "serve", "--host", "0.0.0.0", "--port", "8899"]
