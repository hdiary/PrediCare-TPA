# db-init image (P1). Build context = repository root:
#   docker build -f db_init/Dockerfile -t predicare-db-init .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY db_init/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY clean.py pseudo.py encrypt_identities.py load.py alembic.ini ./
COPY migrations ./migrations
COPY db_init/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh \
    && useradd --create-home --uid 10001 dbinit \
    && mkdir -p /work && chown dbinit /work
USER dbinit

# The dataset is NOT baked into the image: mount it read-only at /data/dataset.
ENTRYPOINT ["/entrypoint.sh"]
