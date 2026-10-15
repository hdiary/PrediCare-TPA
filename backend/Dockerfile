FROM python:3.12-slim

# libgomp1 : requis par XGBoost / LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
# La commande réelle est définie dans docker-compose.yml (api, loader)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
