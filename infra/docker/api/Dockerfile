FROM python:3.11-slim

WORKDIR /app

COPY requirements/api.txt requirements/api.txt
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements/api.txt

COPY . .

# Create non-root user and hand over ownership
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]