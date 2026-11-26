"""Le script d'installation des sauvegardes automatiques : idempotent, ne remplace jamais la phrase secrète."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent.parent / "deploy"


def setup(tmp_path):
    folder = tmp_path / "deploy"
    folder.mkdir()
    for name in ("sauvegardes-auto.sh", "backup.sh", "restore.sh"):
        shutil.copy(DEPLOY / name, folder / name)
        (folder / name).chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    store = tmp_path / "crontab.txt"
    fake = bin_dir / "crontab"                                   # faux crontab : un simple fichier
    fake.write_text(f'#!/bin/sh\nif [ "$1" = "-l" ]; then cat "{store}" 2>/dev/null; else cat > "{store}"; fi\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    dump = bin_dir / "faux-pg_dump"                               # remplace pg_dump : produit un faux export assez long
    dump.write_text("#!/bin/sh\nhead -c 3000 /dev/urandom | base64\n")
    dump.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PGDUMP_CMD": str(dump)}
    return folder, store, env


def run(folder, env, *args):
    return subprocess.run(["bash", "sauvegardes-auto.sh", "--sans-docker", "--sans-test", *args], cwd=folder, env=env,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


def test_install_creates_secret_backup_and_cron_once(tmp_path):
    folder, store, env = setup(tmp_path)
    r = run(folder, env)
    assert r.returncode == 0, r.stdout + r.stderr
    passfile = folder / "backup.pass"
    assert passfile.stat().st_size > 20 and oct(passfile.stat().st_mode)[-3:] == "600"
    secret = passfile.read_text()
    assert secret in r.stdout                                          # affichée une fois pour être copiée
    assert len(list((folder / "backups").glob("psie-*.sql.gz.enc"))) == 1
    cron = store.read_text()
    assert cron.count("psie-sauvegarde") == 2 and "./backup.sh" in cron and "restore.sh --test" in cron
    r2 = run(folder, env)                                              # relance : rien ne change
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert passfile.read_text() == secret and secret not in r2.stdout   # jamais remplacée ni réaffichée
    assert store.read_text().count("psie-sauvegarde") == 2             # pas de doublons dans le crontab


def test_other_cron_lines_are_preserved_and_status_reports(tmp_path):
    folder, store, env = setup(tmp_path)
    store.write_text("0 5 * * * /usr/bin/autre-tache\n")
    assert run(folder, env).returncode == 0
    assert "autre-tache" in store.read_text()
    status = run(folder, env, "--statut")
    assert status.returncode == 0 and "Sauvegarde récente" in status.stdout and "Tâches planifiées en place" in status.stdout


def test_status_fails_loudly_without_any_backup(tmp_path):
    folder, _, env = setup(tmp_path)
    status = run(folder, env, "--statut")
    assert status.returncode == 1 and "Aucune sauvegarde" in status.stdout
