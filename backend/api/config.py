"""Configuration de l'API : tout vient des variables d'environnement (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30
    jwt_algorithm: str = "HS256"
    login_max_attempts: int = 5          # échecs consécutifs avant verrouillage du compte
    login_lockout_minutes: int = 15      # durée du verrouillage
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    alert_threshold: float = 0.8  # valeur initiale ; la valeur "vivante" est dans app_settings

    # Registre de modèles (MLflow)
    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_model_name: str = "predicare-fraud"
    mlflow_model_alias: str = "champion"   # alias de la version active
    shap_top_k: int = 5
    model_retry_interval_s: int = 10       # délai mini entre deux tentatives de chargement

    # Dérive (P3-19)
    drift_features: str = ""            # variables suivies (séparées par des virgules) ; vide = top SHAP
    drift_top_k: int = 5
    drift_reference_size: int = 500     # nombre de premières prédictions servant de référence
    drift_window_days: int = 7
    drift_min_samples: int = 30

    # Optional demonstration accounts (created when DEMO_PASSWORD is configured).
    demo_password: str | None = None

    # Initial administrator account. Existing accounts are never overwritten.
    admin_email: str = "admin@predicare.local"
    admin_initial_password: str | None = None

    # Déchiffrement des identités (Fernet) : réservé à l'affichage d'une alerte
    identity_encryption_key: str | None = None

    # Alertes n8n (P3-13)
    n8n_webhook_url: str | None = None      # ex. http://n8n:5678/webhook/predicare-alert
    n8n_webhook_secret: str | None = None   # openssl rand -hex 32
    n8n_timeout_s: float = 3.0              # jamais bloquant pour /predict

    @property
    def drift_feature_list(self) -> list[str]:
        return [f.strip() for f in self.drift_features.split(",") if f.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
