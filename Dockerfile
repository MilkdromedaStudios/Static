FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md LICENSE ./
COPY static_ai ./static_ai
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 static && mkdir -p /app/data && chown static:static /app/data
USER static
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/',timeout=3)"
CMD ["static-ai", "--host", "0.0.0.0", "--data-dir", "/app/data"]
