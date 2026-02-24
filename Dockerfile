FROM python:3.13-slim

# System dependencies (curl=HTTP, jq=JSON, ffmpeg=video, poppler-utils=PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq ffmpeg poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

# Python dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ src/
COPY config.yaml .

# Own everything by app user
RUN chown -R app:app /app

USER app

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import sqlite3; sqlite3.connect('/app/data/checkpoints.db').execute('SELECT 1')" || exit 1

CMD ["python", "-m", "src.main"]
