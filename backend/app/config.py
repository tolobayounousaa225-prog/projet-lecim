from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://lecim:lecim@localhost:5432/lecim"

    secret_key: str = "changez-cette-cle-en-production"
    access_token_expire_minutes: int = 180
    algorithm: str = "HS256"

    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    admin_bootstrap_email: str = "admin@lecim.org"
    admin_bootstrap_password: str = "change-moi-123"
    admin_bootstrap_name: str = "Administrateur LECIM"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@lecim.org"
    contact_notify_email: str = ""

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 15

    # URL publique de ce backend, utilisée pour générer le lien encodé dans le QR code
    # des cartes de membres. À remplacer par le vrai domaine une fois en production.
    public_base_url: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
