FROM python:3.11-slim

WORKDIR /app

# System libraries required by opencv (pulled in transitively via docling -> rapidocr)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libxcb1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/api.txt requirements/api.txt

# CPU-only torch first, so docling's transitive torch dependency doesn't pull the CUDA build
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --timeout=100 --retries=3 -r requirements/api.txt

COPY . .

RUN useradd -m -u 1001 appuser \
    && mkdir -p /documents \
    && mkdir -p /usr/local/lib/python3.11/site-packages/rapidocr/models \
    && chown -R appuser:appuser /app /documents /usr/local/lib/python3.11/site-packages/rapidocr


USER appuser

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]