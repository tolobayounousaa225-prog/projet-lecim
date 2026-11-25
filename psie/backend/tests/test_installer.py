"""Le script d'installation prépare un .env sûr, sans jamais lancer Docker ici (--seulement-env)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.config import Settings, production_problems

DEPLOY = Path(__file__).resolve().parent.parent.parent / "deploy"


def run(tmp_path, *args, **env):
    folder = tmp_path / "deploy"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(DEPLOY / "installer.sh", folder / "installer.sh")
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("PSIE_", "SMTP_", "ADMIN_", "VITRINE_"))}
    return subprocess.run(["bash", "installer.sh", "--seulement-env", *args], cwd=folder, env={**clean, **env},
                          capture_output=True, text=True, stdin=subprocess.DEVNULL), folder


def read_env(folder) -> dict:
    return dict(line.split("=", 1) for line in (folder / ".env").read_text().splitlines() if "=" in line and not line.startswith("#"))


GOOD = {"PSIE_DOMAIN": "app.psie-ci.org", "SMTP_HOST": "smtp.example.org", "SMTP_USER": "u", "SMTP_PASSWORD": "p",
        "ADMIN_EMAIL": "chef@psie-ci.org"}


def test_production_env_is_complete_private_and_accepted_by_the_app(tmp_path):
    r, folder = run(tmp_path, **GOOD)
    assert r.returncode == 0, r.stderr
    assert oct((folder / ".env").stat().st_mode & 0o777) == "0o600"
    env = read_env(folder)
    assert env["PUBLIC_BASE_URL"] == "https://app.psie-ci.org" and env["COOKIE_SECURE"] == "true"
    assert env["VITRINE_ORIGINS"] == "https://tolobayounousaa225-prog.github.io"          # sans chemin
    assert env["PSIE_PORT"] == "8100" and env["ADMIN_BOOTSTRAP_EMAIL"] == "chef@psie-ci.org"
    assert len(env["SECRET_KEY"]) >= 48 and len(env["POSTGRES_PASSWORD"]) >= 24
    assert "CHANGER" not in (folder / ".env").read_text()
    # l'application accepte cette configuration de production
    settings = Settings(_env_file=None, secret_key=env["SECRET_KEY"], cookie_secure=True, debug=False, two_factor_enabled=True,
                        smtp_host=env["SMTP_HOST"], public_base_url=env["PUBLIC_BASE_URL"], vitrine_url=env["VITRINE_URL"],
                        vitrine_origins=env["VITRINE_ORIGINS"])
    assert production_problems(settings) == []


def test_each_install_gets_different_secrets_and_an_existing_env_is_never_overwritten(tmp_path):
    r1, f1 = run(tmp_path / "a", **GOOD)
    r2, f2 = run(tmp_path / "b", **GOOD)
    assert read_env(f1)["SECRET_KEY"] != read_env(f2)["SECRET_KEY"]
    before = (f1 / ".env").read_text()
    again, _ = run(tmp_path / "a", **{**GOOD, "PSIE_DOMAIN": "autre.example.org"})
    assert again.returncode == 0 and "conservé" in again.stdout and (f1 / ".env").read_text() == before


def test_trial_mode_needs_no_domain_or_email_and_stays_local(tmp_path):
    r, folder = run(tmp_path, "--essai")
    assert r.returncode == 0, r.stderr
    env = read_env(folder)
    assert env["COOKIE_SECURE"] == "false" and env["TWO_FACTOR_ENABLED"] == "false"
    assert env["PUBLIC_BASE_URL"] == "http://127.0.0.1:8100"


@pytest.mark.parametrize("env,message", [
    ({**GOOD, "PSIE_DOMAIN": "mauvais domaine!"}, "invalide"),
    ({**GOOD, "PSIE_DOMAIN": ".sans-debut"}, "invalide"),
    ({k: v for k, v in GOOD.items() if k != "PSIE_DOMAIN"}, "obligatoire"),
    ({k: v for k, v in GOOD.items() if k != "SMTP_HOST"}, "e-mail"),
])
def test_missing_or_bad_answers_stop_the_install_before_writing_anything(tmp_path, env, message):
    r, folder = run(tmp_path, **env)
    assert r.returncode == 1 and message in r.stderr
    assert not (folder / ".env").exists()


def test_another_port_can_be_chosen_when_8100_is_taken(tmp_path):
    r, folder = run(tmp_path, **GOOD, PSIE_PORT="8110")
    assert r.returncode == 0 and read_env(folder)["PSIE_PORT"] == "8110"


def test_diagnostic_script_is_read_only_and_runs_anywhere():
    r = subprocess.run(["bash", str(DEPLOY / "diagnostic.sh")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "Aucun fichier n'a été modifié" in r.stdout and "Mémoire" in r.stdout
