"""Configuration de l'API : tout vient des variables d'environnement (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    login_max_attempts: int = 5          # échecs consécutifs avant verrouillage du compte
    login_lockout_minutes: int = 15      # durée du verrouillage
    cors_origins: str = "http://localhost:3000"
    max_body_bytes: int = 1_000_000      # taille maximale d'une requête (413 au-delà)
    alert_threshold: float = 0.8  # valeur initiale ; la valeur "vivante" est dans app_settings

    # Registre de modèles (MLflow)
    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_model_name: str = "predicare-fraud"
    mlflow_model_alias: str = "champion"   # alias de la version active
    shap_top_k: int = 5
    model_retry_interval_s: int = 10       # délai mini entre deux tentatives de chargement

    # Comptes de démonstration (créés au démarrage si DEMO_PASSWORD est défini)
    demo_password: str | None = None

    # Déchiffrement des identités (Fernet) : réservé à l'affichage d'une alerte
    identity_encryption_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
