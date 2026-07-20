# -------- Builder stage --------
FROM python:3.13-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
   build-essential \
   libpq-dev \
   && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --upgrade pip \
   && pip install --no-cache-dir -r requirements.txt


# -------- Final stage --------
FROM python:3.13-slim-bookworm AS runner

RUN apt-get update && apt-get install -y \
    libpq5 \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r appuser && \
   mkdir /app && \
   chown -R appuser /app

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY --chown=appuser:appuser . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app

ENV GUNICORN_WORKERS=3

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --worker-class gevent --access-logfile - --error-logfile - --timeout 120 --max-requests 1000 --max-requests-jitter 100 config.wsgi:application"]
