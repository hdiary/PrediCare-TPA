FROM python:3.11-slim

# libgomp1 : requis par XGBoost / LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non administrateur (P3-06) : l'API ne tourne jamais en root
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
RUN mkdir -p /models && chown -R app:app /models /app
RUN chmod +x /app/entrypoint.sh
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 HOME=/app
USER app
ENTRYPOINT ["/app/entrypoint.sh"]
EXPOSE 8000

# Santé : GET /health (503 si la base est injoignable)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# La commande réelle est définie dans docker-compose.yml (api, loader)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
