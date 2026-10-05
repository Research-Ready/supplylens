FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir \
    -r requirements.txt \
    fastapi "uvicorn[standard]" httpx

# Source
COPY src/ ./src/

ENV PYTHONPATH=/app

EXPOSE 8090

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8090/health || exit 1

CMD ["uvicorn", "src.agent_server:app", "--host", "0.0.0.0", "--port", "8090"]
