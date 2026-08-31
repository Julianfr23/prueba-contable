from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración centralizada. Se lee de variables de entorno / .env.

    Decisión de diseño: se usa pydantic-settings en lugar de leer os.environ
    directamente para tener validación de tipos y un único punto de verdad.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://contable:contable@localhost:5432/contable"
    environment: str = "local"

    # UVT: proveedor externo simulado / real. Ver app/infra/uvt_provider.py
    uvt_provider: str = "simulado"  # "simulado" | "http"
    uvt_provider_url: str | None = None
    uvt_refresh_interval_seconds: int = 3600

    jwt_secret: str = "dev-secret-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
