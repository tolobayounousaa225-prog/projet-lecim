from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://lecim:lecim@localhost:5432/lecim"

    # Active la documentation interactive (/docs, /redoc, /openapi.json). Désactivée
    # par défaut : en production, elle cartographie toute la surface d'API admin
    # (chemins, schémas de champs) pour n'importe quel visiteur non authentifié.
    debug: bool = False

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

    # Sauvegarde hors-site : chaque sauvegarde nocturne est chiffrée avec cette clé
    # (Fernet — `cryptography.fernet.Fernet.generate_key()`) avant d'être envoyée
    # vers le dépôt GitHub privé dédié. Vide = synchronisation hors-site désactivée
    # (la sauvegarde locale continue normalement). Dépôt accédé via une clé de
    # déploiement SSH dédiée (voir ~/.ssh/config sur le VPS), jamais ce dépôt-ci.
    backup_encryption_key: str = ""
    backup_offsite_repo_ssh_url: str = ""

    # Clés VAPID pour les notifications push web (actualités urgentes). Vides = la
    # fonctionnalité est simplement désactivée (aucun envoi), sans erreur.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claim_email: str = "lecimnational@gmail.com"

    # URL publique de ce backend, utilisée pour générer le lien encodé dans le QR code
    # des cartes, attestations et certificats. Doit toujours pointer vers le domaine
    # réellement joignable par le public qui scanne le code — jamais localhost.
    public_base_url: str = "https://213-199-37-74.sslip.io"

    # URL publique du site vitrine (GitHub Pages), distinct du backend ci-dessus —
    # utilisée pour les liens dans le flux RSS et le sitemap.
    vitrine_base_url: str = "https://tolobayounousaa225-prog.github.io/projet-lecim"

    # Visioconférence interne (Jitsi Meet auto-hébergé) — jitsi_app_secret doit être
    # identique au JWT_APP_SECRET configuré côté serveur Jitsi (deploy/jitsi-meet/.env),
    # sinon les jetons générés ici sont rejetés à la connexion.
    jitsi_domain: str = "visio.213-199-37-74.sslip.io"
    jitsi_app_id: str = "lecim"
    jitsi_app_secret: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
