# AIDNEXUS ONE — application container
# Build:  docker build -t aidnexus-one .
# Run:    docker run -p 8000:8000 -e DATABASE_URL=... aidnexus-one
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend ./frontend
COPY AGENTS.md README.md LICENSE ./

# Run as non-root
RUN useradd -m -u 1001 aidnexus && chown -R aidnexus /app
USER aidnexus

ENV APP_ENV=production \
    DEV_AUTH_ENABLED=""

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
