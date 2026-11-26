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


def test_dedicated_server_without_domain_uses_a_provisional_ip_address(tmp_path):
    env = {k: v for k, v in GOOD.items() if k != "PSIE_DOMAIN"}
    r, folder = run(tmp_path, "--serveur-dedie", **env, PSIE_IP="185.215.166.186")
    assert r.returncode == 0, r.stderr
    values = read_env(folder)
    assert values["DOMAIN"] == "185-215-166-186.sslip.io" and values["PUBLIC_BASE_URL"] == "https://185-215-166-186.sslip.io"
    assert "adresse provisoire" in r.stdout.lower()


@pytest.mark.parametrize("ip", ["", "999", "185.215.166", "a.b.c.d", "1.2.3.4; rm -rf /"])
def test_dedicated_server_refuses_a_bad_ip(tmp_path, ip):
    env = {k: v for k, v in GOOD.items() if k != "PSIE_DOMAIN"}
    r, folder = run(tmp_path, "--serveur-dedie", **env, PSIE_IP=ip)
    assert r.returncode == 1 and not (folder / ".env").exists()


def test_dedicated_server_keeps_a_real_domain_when_given(tmp_path):
    r, folder = run(tmp_path, "--serveur-dedie", **GOOD)
    assert r.returncode == 0 and read_env(folder)["DOMAIN"] == "app.psie-ci.org"


def test_trial_and_dedicated_modes_cannot_be_combined(tmp_path):
    r, folder = run(tmp_path, "--essai", "--serveur-dedie")
    assert r.returncode == 2 and not (folder / ".env").exists()


# ---------------------------------------------------------------- passage en public

def public(folder, **env):
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("PSIE_", "SMTP_", "ADMIN_", "VITRINE_"))}
    shutil.copy(DEPLOY / "ouvrir-au-public.sh", folder / "ouvrir-au-public.sh")
    return subprocess.run(["bash", "ouvrir-au-public.sh", "--sans-docker"], cwd=folder, env={**clean, **env},
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


PUBLIC = {"PSIE_IP": "185.215.166.186", "SMTP_HOST": "smtp.gmail.com", "SMTP_USER": "psie@gmail.com",
          "SMTP_PASSWORD": "abcd efgh ijkl mnop"}


def trial_install(tmp_path):
    r, folder = run(tmp_path, "--essai", ADMIN_EMAIL="chef@psie-ci.org")
    assert r.returncode == 0, r.stderr
    return folder


def test_going_public_updates_only_what_is_needed_and_keeps_a_backup(tmp_path):
    folder = trial_install(tmp_path)
    before = read_env(folder)
    r = public(folder, **PUBLIC)
    assert r.returncode == 0, r.stderr
    after = read_env(folder)
    assert after["DOMAIN"] == "185-215-166-186.sslip.io" and after["PUBLIC_BASE_URL"] == "https://185-215-166-186.sslip.io"
    assert after["COOKIE_SECURE"] == "true" and after["TWO_FACTOR_ENABLED"] == "true"
    assert after["SMTP_HOST"] == "smtp.gmail.com" and after["SMTP_USER"] == "psie@gmail.com" and after["SMTP_FROM"] == "psie@gmail.com"
    assert after["SMTP_PASSWORD"] == "abcdefghijklmnop"                       # espaces du code Google retirés
    for same in ("POSTGRES_PASSWORD", "SECRET_KEY", "ADMIN_BOOTSTRAP_EMAIL", "ADMIN_BOOTSTRAP_PASSWORD", "PSIE_PORT"):
        assert after[same] == before[same], same                              # la base et les secrets ne changent pas
    assert oct((folder / ".env").stat().st_mode & 0o777) == "0o600"
    assert read_env_file(folder / ".env.avant-public")["COOKIE_SECURE"] == "false"
    settings = Settings(_env_file=None, secret_key=after["SECRET_KEY"], cookie_secure=True, debug=False, two_factor_enabled=True,
                        smtp_host=after["SMTP_HOST"], public_base_url=after["PUBLIC_BASE_URL"], vitrine_url=after["VITRINE_URL"],
                        vitrine_origins=after["VITRINE_ORIGINS"])
    assert production_problems(settings) == []


def read_env_file(path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))


def test_going_public_with_a_real_domain(tmp_path):
    folder = trial_install(tmp_path)
    env = {k: v for k, v in PUBLIC.items() if k != "PSIE_IP"}
    assert public(folder, **env, PSIE_DOMAIN="app.psie-ci.org").returncode == 0
    assert read_env(folder)["PUBLIC_BASE_URL"] == "https://app.psie-ci.org"


def test_going_public_twice_is_refused_and_changes_nothing(tmp_path):
    folder = trial_install(tmp_path)
    assert public(folder, **PUBLIC).returncode == 0
    snapshot = (folder / ".env").read_text()
    again = public(folder, **PUBLIC)
    assert again.returncode == 1 and "déjà en mode public" in again.stderr and (folder / ".env").read_text() == snapshot


@pytest.mark.parametrize("override,message", [
    ({"PSIE_IP": "999"}, "IP invalide"), ({"PSIE_IP": "1.2.3.4; rm -rf /"}, "IP invalide"),
    ({"SMTP_USER": ""}, "obligatoire"), ({"SMTP_PASSWORD": ""}, "obligatoire"),
    ({"SMTP_PASSWORD": "mot$de$passe"}, "non pris en charge"), ({"SMTP_PASSWORD": "a#b"}, "non pris en charge"),
    ({"PSIE_DOMAIN": "mauvais domaine!"}, "invalide"),
])
def test_bad_answers_leave_the_env_untouched(tmp_path, override, message):
    folder = trial_install(tmp_path)
    before = (folder / ".env").read_text()
    r = public(folder, **{**PUBLIC, **override})
    assert r.returncode == 1 and message in r.stderr
    assert (folder / ".env").read_text() == before and not (folder / ".env.avant-public").exists()


def test_going_public_needs_an_existing_install(tmp_path):
    folder = tmp_path / "vide"
    folder.mkdir()
    r = public(folder, **PUBLIC)
    assert r.returncode == 1 and "installer.sh" in r.stderr
