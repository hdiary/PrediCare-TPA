FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY rag/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY rag /app/rag

RUN useradd --create-home --uid 10002 rag \
    && chown -R rag:rag /app
USER rag

CMD ["python", "-m", "rag.ingest_corpus"]
