# db-init image. The build context is the repository root.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY database/db_init/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY database/clean.py database/pseudo.py \
     database/encrypt_identities.py database/load.py \
     database/configure_agent_role.py ./
COPY database/alembic.ini ./alembic.ini
COPY database/migrations ./migrations
COPY database/db_init/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh \
    && useradd --create-home --uid 10001 dbinit \
    && mkdir -p /work && chown dbinit /work
USER dbinit

# The dataset is NOT baked into the image: mount it read-only at /data/dataset.
ENTRYPOINT ["/entrypoint.sh"]
