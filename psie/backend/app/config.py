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

    # URL publique de l'application : encodée dans les QR codes des reçus et attestations.
    public_base_url: str = "http://localhost:8100"

    # Double authentification par e-mail (admin et finances). À activer en production ;
    # nécessite un serveur SMTP configuré.
    two_factor_enabled: bool = True

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@psie.local"

    # Adresse prévenue à chaque nouvelle demande d'adhésion (facultatif)
    notify_email: str = ""

    # Tâches planifiées (génération des cotisations de l'année, relances, résumé hebdomadaire)
    scheduler_enabled: bool = True

    admin_bootstrap_email: str = "admin@psie.local"
    admin_bootstrap_password: str = "change-moi-123"
    admin_bootstrap_name: str = "Administrateur PSIE"


settings = Settings()
