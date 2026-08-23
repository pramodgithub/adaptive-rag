FROM python:3.11-slim

WORKDIR /app

COPY requirements/worker.txt requirements/worker.txt
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements/worker.txt

COPY . .

# Create non-root user and hand over ownership
RUN useradd -m -u 1001 appuser \
    && mkdir -p /documents \
    && chown -R appuser:appuser /app /documents
USER appuser

CMD ["celery", "-A", "apps.worker.celery_app:celery", "worker", "--loglevel=info"]