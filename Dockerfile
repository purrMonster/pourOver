FROM python:3.13.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY pourover ./pourover
RUN pip install --no-cache-dir . && useradd --uid 10001 --no-create-home pourover \
    && mkdir -p /data && chown pourover /data
USER pourover
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "pourover.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
