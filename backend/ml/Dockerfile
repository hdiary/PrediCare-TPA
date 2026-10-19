# Image d'entraînement ML (P2). Contexte de build : backend/ml
#   docker build -t predicare-ml backend/ml
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# libgomp1 : requis par LightGBM sur les images « slim »
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py ./

# Les données et les modèles ne sont PAS dans l'image : ils sont montés (voir
# docker-compose.ml.yml). Par défaut : entraîne et compare les 3 algorithmes.
ENTRYPOINT ["python", "train.py", "--dataset", "/data/dataset", "--labels", "/data/labels"]
CMD ["--algo", "all"]
