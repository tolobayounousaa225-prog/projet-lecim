from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://psie:psie@localhost:5432/psie"
    debug: bool = False

    secret_key: str = "changez-cette-cle-en-production"
    access_token_expire_minutes: int = 180
    algorithm: str = "HS256"
    # True en production (HTTPS) : le cookie de session n'est envoye que sur HTTPS.
    cookie_secure: bool = False

    admin_bootstrap_email: str = "admin@psie.local"
    admin_bootstrap_password: str = "change-moi-123"
    admin_bootstrap_name: str = "Administrateur PSIE"


settings = Settings()
