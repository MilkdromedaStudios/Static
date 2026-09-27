FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BUNS_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md LICENSE ./
COPY buns ./buns
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 buns && mkdir -p /app/data && chown buns:buns /app/data
USER buns
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/',timeout=3)"
CMD ["buns", "--host", "0.0.0.0", "--data-dir", "/app/data"]
