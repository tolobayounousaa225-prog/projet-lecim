"""brancher-site.sh : le jeton GitHub est contrôlé, écrit sans toucher au reste de .env, et ne s'affiche jamais."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent.parent / "deploy"
TOKEN = "github_pat_" + "A1b2C3d4" * 6


def run(tmp_path, token=TOKEN, env_text="SECRET_KEY=abc\nGITHUB_DISPATCH_REPO=\nGITHUB_DISPATCH_TOKEN=\nDOMAIN=x.ci\n", **extra):
    folder = tmp_path / "deploy"
    folder.mkdir(exist_ok=True)
    shutil.copy(DEPLOY / "brancher-site.sh", folder / "brancher-site.sh")
    (folder / ".env").write_text(env_text)
    env = {**os.environ, **extra}
    if token is not None:
        env["PSIE_TOKEN"] = token
    r = subprocess.run(["bash", "brancher-site.sh", "--seulement-env"], cwd=folder, env=env, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r, folder


def read_env(folder):
    return dict(l.split("=", 1) for l in (folder / ".env").read_text().splitlines() if "=" in l)


def test_token_is_written_without_touching_other_settings_and_never_printed(tmp_path):
    r, folder = run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    env = read_env(folder)
    assert env["GITHUB_DISPATCH_TOKEN"] == TOKEN and env["GITHUB_DISPATCH_REPO"] == "tolobayounousaa225-prog/PSIE"
    assert env["SECRET_KEY"] == "abc" and env["DOMAIN"] == "x.ci"
    assert TOKEN not in r.stdout + r.stderr
    assert oct((folder / ".env").stat().st_mode)[-3:] == "600"
    assert "GITHUB_DISPATCH_TOKEN=\n" in (folder / ".env.avant-site").read_text()      # l'ancien .env est conservé
    r2, _ = run(tmp_path, token="github_pat_" + "Z9y8X7w6" * 6)                       # relance : remplacé, pas dupliqué
    assert r2.returncode == 0
    assert (folder / ".env").read_text().count("GITHUB_DISPATCH_TOKEN=") == 1


@pytest.mark.parametrize("bad", ["motdepasse", "github_pat_court", "ghp_ " + "a" * 40, 'github_pat_"' + "a" * 40])
def test_malformed_tokens_are_refused_and_env_untouched(tmp_path, bad):
    r, folder = run(tmp_path, token=bad)
    assert r.returncode == 1 and "pas un jeton GitHub" in r.stderr
    assert read_env(folder)["GITHUB_DISPATCH_TOKEN"] == ""


def test_bad_repository_name_is_refused(tmp_path):
    r, _ = run(tmp_path, SITE_REPO="pas un depot")
    assert r.returncode == 2 and "dépôt invalide" in r.stderr
