# ── Build stage ───────────────────────────────────────────────
FROM python:3.11-slim AS base

# Don't write .pyc files, don't buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer-cached until requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data files
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# ── Runtime ───────────────────────────────────────────────────
EXPOSE 8000

# start.sh: creates tables + imports data (first run only) → starts Gunicorn
CMD ["./start.sh"]
