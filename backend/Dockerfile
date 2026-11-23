FROM python:3.12-slim AS dependencies

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SK_ENV=production \
    HOME=/home/sk-under \
    SK_CLOUD_BACKUP_DIR=/var/lib/sk-under/backups

COPY --from=dependencies /opt/venv /opt/venv
COPY app/ ./app/
RUN mkdir -p "$HOME" /var/lib/sk-under/backups \
    && chown -R 10001:10001 "$HOME" /var/lib/sk-under \
    && chmod 700 /var/lib/sk-under/backups
USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).close()"]

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
