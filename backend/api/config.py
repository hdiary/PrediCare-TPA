"""Configuration de l'API : tout vient des variables d'environnement (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:3000"
    alert_threshold: float = 0.8  # valeur initiale ; la valeur "vivante" sera en base

    # Comptes de démonstration (créés au démarrage si DEMO_PASSWORD est défini)
    demo_password: str | None = None
    demo_insured_id: str | None = None    # pseudonyme d'un assuré existant
    demo_provider_id: str | None = None   # identifiant d'un prestataire existant

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
