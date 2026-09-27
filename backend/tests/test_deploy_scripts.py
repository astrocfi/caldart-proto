"""The server installer under ``deploy/``: its scripts, their dry run, and what they write.

``docs/developer/deployment.rst`` describes the scripts: ``install.sh`` runs the steps
under ``deploy/steps/`` in order, and ``--dry-run`` prints every command that changes
the machine instead of running it.  These tests read that dry run as an ordered command
list and hold it to the order the guide gives.  Nothing here needs root, Docker, or the
network: every dry run happens in a copy of ``deploy/`` under ``tmp_path``, with
``CALDART_ETC`` pointing at an empty temporary directory, so even a script that forgot
the dry run could only touch the copy.  ``configure.sh`` runs for real into that
temporary directory, and the file it writes is checked by ``manage.py check --deploy``.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEPLOY_DIR: Final = REPO_ROOT / "deploy"
MANAGE_PY: Final = REPO_ROOT / "backend" / "manage.py"

_bash = shutil.which("bash")
if _bash is None:  # pragma: no cover - the dev environment always has bash installed.
    raise RuntimeError("bash is not on PATH")
BASH: Final[str] = _bash

#: Every shell script the installer ships.
SCRIPTS: Final = sorted([*DEPLOY_DIR.glob("*.sh"), *(DEPLOY_DIR / "steps").glob("*.sh")])

#: The scripts an operator runs by name, each answering ``--help`` from its header.
ENTRY_POINTS: Final = (
    "bootstrap.sh",
    "install.sh",
    "upgrade.sh",
    "uninstall.sh",
    "manage.sh",
    "steps/packages.sh",
    "steps/user.sh",
    "steps/postgres.sh",
    "steps/configure.sh",
    "steps/build.sh",
    "steps/database.sh",
    "steps/web-service.sh",
    "steps/web-server.sh",
    "steps/timers.sh",
    "steps/backup.sh",
    "steps/check.sh",
)

#: Every file the installer copies out of ``deploy/`` through ``render_file``.
UNITS: Final = sorted(path.name for path in (DEPLOY_DIR / "systemd").iterdir())
VHOSTS: Final = ("apache/caldart.conf", "nginx/caldart.conf")

#: The flags a first install needs with the default web server and certbot.
FIRST_INSTALL: Final = (
    "--hostname",
    "caldart.test",
    "--certbot-email",
    "ops@caldart.test",
    "--email-url",
    "smtp://localhost:25",
    "--admin-email",
    "ops@caldart.test",
)

#: The five variables the production template leaves commented out.
REQUIRED_VARIABLES: Final = ("SECRET_KEY", "ALLOWED_HOSTS", "SITE_URL", "EMAIL_URL", "DATABASE_URL")

#: The published development key, which the production settings refuse.
DEVELOPMENT_SECRET_KEY: Final = "dev-insecure-secret-key-change-me"  # noqa: S105 - already public

OS_RELEASES: Final = {
    "debian": 'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\nVERSION_CODENAME=trixie\n',
    "ubuntu": 'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_CODENAME=noble\n',
    "fedora": 'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=40\n',
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A deploy root holding a copy of ``deploy/``, so a dry run can touch only it."""
    target = tmp_path / "root"
    shutil.copytree(DEPLOY_DIR, target / "deploy")
    return target


@pytest.fixture
def etc(tmp_path: Path) -> Path:
    """An empty directory standing in for ``/etc/caldart``."""
    path = tmp_path / "etc"
    path.mkdir()
    return path


def _os_release(tmp_path: Path, distro: str) -> Path:
    """Write the ``os-release`` of ``distro`` under ``tmp_path`` and return its path."""
    path = tmp_path / f"os-release-{distro}"
    path.write_text(OS_RELEASES[distro])
    return path


def _env(etc: Path, **extra: str) -> dict[str, str]:
    """A clean environment for a script: the interpreter's basics plus ``CALDART_ETC``."""
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    return {**base, "CALDART_ETC": str(etc), **extra}


def _run(
    script: Path, *args: str, env: dict[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``script`` with ``bash`` and capture its output."""
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [BASH, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=cwd,
    )


def _commands(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The commands a dry run printed, in order, without their ``+ `` prefix."""
    return [line[2:] for line in result.stdout.splitlines() if line.startswith("+ ")]


def _position(commands: list[str], fragment: str) -> int:
    """The index of the first command containing ``fragment``; fails when none does."""
    for index, command in enumerate(commands):
        if fragment in command:
            return index
    pytest.fail(f"no command contains {fragment!r}")


def _install_dry_run(
    root: Path, etc: Path, tmp_path: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    """The dry run of ``install.sh`` for a first install on Ubuntu, plus ``extra`` flags."""
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")))
    return _run(root / "deploy" / "install.sh", "--dry-run", *FIRST_INSTALL, *extra, env=env)


def _variables(env_file: Path) -> dict[str, str]:
    """The uncommented ``KEY=value`` lines of an environment file."""
    lines = env_file.read_text().splitlines()
    pairs = [line.split("=", 1) for line in lines if "=" in line and not line.startswith("#")]
    return {key: value for key, value in pairs}


def _configure(
    root: Path, etc: Path, *args: str, **extra: str
) -> subprocess.CompletedProcess[str]:
    """Run ``configure.sh`` for real into ``etc``."""
    return _run(root / "deploy" / "steps" / "configure.sh", *args, env=_env(etc, **extra))


def _source_lib(root: Path, snippet: str) -> subprocess.CompletedProcess[str]:
    """Run ``snippet`` in a shell that has sourced ``deploy/lib.sh``."""
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [BASH, "-c", f'set -euo pipefail; source "$1"; {snippet}', "bash", str(root / "deploy" / "lib.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=_env(root),
    )


# -- every script -------------------------------------------------------------------


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_every_script_parses(script: Path) -> None:
    """``bash -n`` accepts every script under ``deploy/``."""
    result = subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [BASH, "-n", str(script)], capture_output=True, text=True, check=False
    )
    assert result.stderr == ""


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_every_script_is_executable(script: Path) -> None:
    """Every script carries its executable bit, so ``sudo deploy/...`` runs it."""
    assert script.stat().st_mode & stat.S_IXUSR


@pytest.mark.parametrize("script", ENTRY_POINTS)
def test_every_entry_point_answers_help_from_its_header(script: str, etc: Path) -> None:
    """``--help`` prints the header comment, whose usage line names the script."""
    result = _run(DEPLOY_DIR / script, "--help", env=_env(etc))
    assert result.returncode == 0
    assert f"Usage:\n  sudo deploy/{script}" in result.stdout


@pytest.mark.parametrize("script", ENTRY_POINTS)
def test_an_unknown_flag_is_a_usage_error(script: str, etc: Path) -> None:
    """A flag the script does not know exits 2 with an ``error:`` line on stderr."""
    if script == "manage.sh":
        pytest.skip("manage.sh hands every argument after its own flags to manage.py")
    result = _run(DEPLOY_DIR / script, "--nonsense", env=_env(etc))
    assert result.returncode == 2
    assert "error: unknown option --nonsense" in result.stderr


# -- install.sh ---------------------------------------------------------------------


def test_the_install_dry_run_succeeds(root: Path, etc: Path, tmp_path: Path) -> None:
    """The dry run of a first install exits 0."""
    result = _install_dry_run(root, etc, tmp_path)
    assert result.returncode == 0, result.stderr


def test_the_install_dry_run_changes_nothing(root: Path, etc: Path, tmp_path: Path) -> None:
    """A dry run writes neither the install record nor the environment file."""
    _install_dry_run(root, etc, tmp_path)
    assert list(etc.iterdir()) == []


@pytest.mark.parametrize(
    ("earlier", "later"),
    [
        ("apt-get install", "useradd"),
        ("docker compose up -d db", "ALTER USER"),
        ("npm run build", "collectstatic"),
        ("certbot certonly", "a2ensite caldart"),
        ("collectstatic", "systemctl restart caldart-web"),
        ("systemctl restart caldart-web", "systemctl enable --now caldart-registry.timer"),
        ("db_backup", "systemctl is-active"),
    ],
    ids=[
        "packages-before-the-user",
        "database-up-before-the-password",
        "build-before-collectstatic",
        "certificate-before-the-vhost",
        "collectstatic-before-the-restart",
        "web-unit-before-the-timers",
        "backup-before-the-check",
    ],
)
def test_the_install_runs_its_steps_in_order(
    earlier: str, later: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """The dry run prints each command before the ones that depend on it."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert _position(commands, earlier) < _position(commands, later)


def test_the_vhost_is_enabled_after_the_bootstrap_host(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The bootstrap host goes in first and the shipped vhost replaces it."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert commands.index("a2ensite caldart-acme") < commands.index("a2ensite caldart")


def test_the_install_creates_the_administrator(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--admin-email`` runs ``create_admin`` for that address through ``manage.sh``."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    admin = commands[_position(commands, "create_admin")]
    assert admin.endswith("manage.py create_admin --email ops@caldart.test")


def test_the_install_never_seeds_the_demo(root: Path, etc: Path, tmp_path: Path) -> None:
    """``seed_demo`` publishes a password, so no install runs it."""
    output = _install_dry_run(root, etc, tmp_path, "--seed-content").stdout
    assert "seed_demo" not in output


def test_seed_content_loads_the_example_pages(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--seed-content`` adds ``seed_content`` to the database step."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--seed-content"))
    assert _position(commands, "manage.py seed_content") > _position(commands, "migrate")


def test_the_dry_run_prints_no_secret(root: Path, etc: Path, tmp_path: Path) -> None:
    """The database password in the ``ALTER USER`` statement reads ``<generated>``."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    alter = commands[_position(commands, "ALTER USER")]
    assert "PASSWORD '\\''<generated>'\\''" in alter


def test_every_shipped_unit_is_installed(root: Path, etc: Path, tmp_path: Path) -> None:
    """Each unit under ``deploy/systemd/`` is rendered into ``/etc/systemd/system/``."""
    output = _install_dry_run(root, etc, tmp_path).stdout
    missing = [unit for unit in UNITS if f"/etc/systemd/system/{unit}" not in output]
    assert missing == []


def test_every_timer_is_enabled(root: Path, etc: Path, tmp_path: Path) -> None:
    """Each shipped timer is enabled and started."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    timers = [unit for unit in UNITS if unit.endswith(".timer")]
    missing = [timer for timer in timers if f"systemctl enable --now {timer}" not in commands]
    assert missing == []


def test_the_first_registry_import_starts_at_once(root: Path, etc: Path, tmp_path: Path) -> None:
    """The install starts one registry import so the type picker has its vocabulary."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert "systemctl start --no-block caldart-registry.service" in commands


def test_nginx_installs_nginx_and_never_apache(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--web-server nginx`` installs nginx's packages and touches no Apache command."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--web-server", "nginx"))
    assert [command for command in commands if "apache" in command] == []


def test_nginx_gets_the_nginx_certbot_plugin(root: Path, etc: Path, tmp_path: Path) -> None:
    """The nginx install names ``python3-certbot-nginx`` in its package list."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--web-server", "nginx"))
    assert "python3-certbot-nginx" in commands[_position(commands, "apt-get install")]


def test_self_signed_runs_openssl(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--tls self-signed`` makes the certificate with ``openssl``."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--tls", "self-signed"))
    assert _position(commands, "openssl req -x509") >= 0


def test_self_signed_never_asks_certbot_for_a_certificate(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--tls self-signed`` never runs ``certbot certonly``."""
    output = _install_dry_run(root, etc, tmp_path, "--tls", "self-signed").stdout
    assert "certbot certonly" not in output


def test_staging_asks_the_staging_directory(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--certbot-staging`` adds ``--staging`` to the certificate request."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--certbot-staging"))
    assert commands[_position(commands, "certbot certonly")].endswith("--staging")


def test_no_www_asks_for_one_name(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--no-www`` requests a certificate for the hostname alone."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--no-www"))
    assert "www.caldart.test" not in commands[_position(commands, "certbot certonly")]


@pytest.mark.parametrize(
    ("dropped", "flag"),
    [
        (("--hostname", "caldart.test"), "--hostname"),
        (("--email-url", "smtp://localhost:25"), "--email-url"),
        (("--certbot-email", "ops@caldart.test"), "--certbot-email"),
    ],
    ids=["hostname", "email-url", "certbot-email"],
)
def test_a_first_install_names_the_flag_it_is_missing(
    dropped: tuple[str, str], flag: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """With no record and no environment file, a missing required flag exits 2 naming it."""
    args = [arg for arg in FIRST_INSTALL if arg not in dropped]
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")))
    result = _run(root / "deploy" / "install.sh", "--dry-run", *args, env=env)
    assert result.returncode == 2
    assert flag in result.stderr


def test_an_unknown_web_server_is_a_usage_error(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--web-server`` accepts only ``apache`` and ``nginx``."""
    result = _install_dry_run(root, etc, tmp_path, "--web-server", "caddy")
    assert result.returncode == 2


def test_the_install_record_supplies_the_flags(root: Path, etc: Path, tmp_path: Path) -> None:
    """A later run reads the hostname and the web server from ``install.conf``."""
    (etc / "install.conf").write_text(
        "CALDART_HOSTNAME=recorded.test\nCALDART_WWW=no\nCALDART_WEB_SERVER=nginx\n"
        "CALDART_TLS=self-signed\n"
    )
    (etc / "caldart.env").write_text("SECRET_KEY=x\n")
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")))
    result = _run(root / "deploy" / "install.sh", "--dry-run", env=env)
    assert "/etc/nginx/sites-available/caldart" in result.stdout


def test_the_dry_run_prints_the_record_it_would_write(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The install record is written through ``install`` like every other file."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert f"install -m 0644 -o root -g root /dev/stdin {etc}/install.conf" in commands


# -- packages.sh --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("distro", "compose"),
    [("debian", "docker-compose"), ("ubuntu", "docker-compose-v2")],
)
def test_the_compose_package_follows_the_distribution(
    distro: str, compose: str, etc: Path, root: Path, tmp_path: Path
) -> None:
    """Debian installs ``docker-compose`` and Ubuntu ``docker-compose-v2``."""
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, distro)))
    result = _run(root / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    commands = _commands(result)
    packages = commands[_position(commands, "apt-get install")].split()
    assert [name for name in packages if name.startswith("docker-compose")] == [compose]


def test_another_distribution_is_refused(etc: Path, root: Path, tmp_path: Path) -> None:
    """Any other ``ID`` stops with a message naming the two supported families."""
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "fedora")))
    result = _run(root / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    assert result.returncode == 1
    assert "error: fedora is not supported; use Debian or Ubuntu" in result.stderr


# -- configure.sh -------------------------------------------------------------------


@pytest.fixture
def env_file(root: Path, etc: Path) -> Path:
    """The environment file ``configure.sh`` writes for ``caldart.test``."""
    result = _configure(root, etc, "--hostname", "caldart.test", "--email-url", "smtp://localhost:25")
    assert result.returncode == 0, result.stderr
    return etc / "caldart.env"


@pytest.mark.parametrize("variable", REQUIRED_VARIABLES)
def test_configure_sets_every_required_variable(variable: str, env_file: Path) -> None:
    """The five variables the template leaves commented out are uncommented and set."""
    assert _variables(env_file)[variable] != ""


def test_configure_generates_a_long_secret_key(env_file: Path) -> None:
    """``SECRET_KEY`` is at least 64 characters."""
    assert len(_variables(env_file)["SECRET_KEY"]) >= 64


def test_configure_never_writes_the_development_key(env_file: Path) -> None:
    """``SECRET_KEY`` is not the published development key."""
    assert _variables(env_file)["SECRET_KEY"] != DEVELOPMENT_SECRET_KEY


def test_configure_keeps_debug_off(env_file: Path) -> None:
    """``DEBUG`` stays ``false``."""
    assert _variables(env_file)["DEBUG"] == "false"


def test_configure_enables_no_mock_payments(env_file: Path) -> None:
    """No variable naming the mock provider is set."""
    assert [key for key in _variables(env_file) if "MOCK" in key] == []


@pytest.mark.parametrize(
    ("variable", "expected"),
    [
        ("ALLOWED_HOSTS", "caldart.test,www.caldart.test"),
        ("CSRF_TRUSTED_ORIGINS", "https://caldart.test,https://www.caldart.test"),
        ("SITE_URL", "https://caldart.test"),
        ("EMAIL_URL", "smtp://localhost:25"),
        ("DEFAULT_FROM_EMAIL", "CalDART <noreply@caldart.test>"),
        ("DB_BACKUP_VIA_DOCKER", "false"),
        ("BACKUP_RETENTION_DAYS", "30"),
    ],
)
def test_configure_fills_in_the_host_values(variable: str, expected: str, env_file: Path) -> None:
    """The hostname, both hosts, the mail settings, and the backup settings are set."""
    assert _variables(env_file)[variable] == expected


@pytest.mark.parametrize(
    ("variable", "suffix"),
    [("BACKUP_DIR", "backups"), ("USER_GUIDE_ROOT", "docs/_build/guide")],
)
def test_configure_puts_paths_under_the_deploy_root(
    variable: str, suffix: str, env_file: Path, root: Path
) -> None:
    """``BACKUP_DIR`` and ``USER_GUIDE_ROOT`` name directories inside the deploy root."""
    assert _variables(env_file)[variable] == f"{root}/{suffix}"


def test_configure_uses_the_generated_database_password(env_file: Path) -> None:
    """``DATABASE_URL`` carries a generated password, not the development one."""
    assert not _variables(env_file)["DATABASE_URL"].startswith("postgres://caldart:caldart@")


def test_configure_writes_the_file_group_readable_only(env_file: Path) -> None:
    """The file is mode ``0640``."""
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o640


def test_configure_keeps_the_template_comments(env_file: Path) -> None:
    """The comments the operator edits by stay in the file."""
    template = (DEPLOY_DIR / "caldart.env.example").read_text()
    comments = [line for line in template.splitlines() if line.startswith("# ")]
    assert [line for line in comments if line not in env_file.read_text()] == []


def test_configure_never_rewrites_the_file(env_file: Path, root: Path, etc: Path) -> None:
    """A second run leaves the file byte-identical."""
    before = env_file.read_bytes()
    _configure(root, etc, "--hostname", "other.test", "--email-url", "smtp://elsewhere:25")
    assert env_file.read_bytes() == before


def test_configure_reports_ignored_flags(env_file: Path, root: Path, etc: Path) -> None:
    """A second run says it is leaving the file alone and that ``--email-url`` is ignored."""
    result = _configure(root, etc, "--email-url", "smtp://elsewhere:25")
    assert "--email-url is ignored" in result.stdout


def test_configure_without_www_names_one_host(root: Path, etc: Path) -> None:
    """``--no-www`` leaves the ``www.`` form out of ``ALLOWED_HOSTS``."""
    _configure(root, etc, "--hostname", "caldart.test", "--no-www", "--email-url", "smtp://x:25")
    assert _variables(etc / "caldart.env")["ALLOWED_HOSTS"] == "caldart.test"


def test_self_signed_turns_hsts_off(root: Path, etc: Path) -> None:
    """With ``--tls self-signed`` the file sets ``SECURE_HSTS_SECONDS=0``."""
    _configure(
        root, etc, "--hostname", "caldart.test", "--tls", "self-signed", "--email-url", "smtp://x:25"
    )
    assert _variables(etc / "caldart.env")["SECURE_HSTS_SECONDS"] == "0"


def test_certbot_keeps_the_hsts_default(env_file: Path) -> None:
    """With certbot the template's commented HSTS default stands."""
    assert "SECURE_HSTS_SECONDS" not in _variables(env_file)


def test_configure_needs_a_hostname(root: Path, etc: Path) -> None:
    """With no record and no ``--hostname`` the step exits 2 naming the flag."""
    result = _configure(root, etc, "--email-url", "smtp://localhost:25")
    assert result.returncode == 2
    assert "--hostname" in result.stderr


def test_configure_writes_a_file_the_deployment_checks_accept(env_file: Path) -> None:
    """``manage.py check --deploy`` against the production settings passes on the file."""
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    result = subprocess.run(  # noqa: S603 - fixed argv, sys.executable is this interpreter
        [
            sys.executable,
            str(MANAGE_PY),
            "check",
            "--deploy",
            *("--tag", "security", "--tag", "caches", "--tag", "async_support", "--tag", "mail"),
            "--fail-level",
            "WARNING",
            "--settings",
            "caldart.settings.prod",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**base, **_variables(env_file)},
    )
    assert result.returncode == 0, result.stderr


# -- rendering ----------------------------------------------------------------------


@pytest.mark.parametrize("source", [*(f"systemd/{unit}" for unit in UNITS), *VHOSTS])
def test_render_file_moves_every_path_to_the_deploy_root(source: str, root: Path) -> None:
    """``render_file`` replaces ``/srv/caldart`` with the root as it copies a file."""
    dest = root / "rendered"
    _source_lib(root, f'ROOT=/opt/x; render_file "{DEPLOY_DIR / source}" "{dest}"')
    assert "/srv/caldart" not in dest.read_text()


@pytest.mark.parametrize("source", [f"systemd/{unit}" for unit in UNITS if unit.endswith("service")])
def test_render_file_writes_the_deploy_root(source: str, root: Path) -> None:
    """A rendered service names the root in place of ``/srv/caldart``."""
    dest = root / "rendered"
    _source_lib(root, f'ROOT=/opt/x; render_file "{DEPLOY_DIR / source}" "{dest}"')
    assert "/opt/x/.venv/bin/" in dest.read_text()


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_replaces_the_example_hostname(vhost: str, root: Path) -> None:
    """Every ``caldart.example.org`` in a vhost becomes the hostname."""
    dest = root / "rendered"
    _source_lib(root, f'render_vhost "{DEPLOY_DIR / vhost}" "{dest}" caldart.test yes certbot')
    assert "caldart.example.org" not in dest.read_text()


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_keeps_the_www_alias(vhost: str, root: Path) -> None:
    """With ``www`` the vhost answers for ``www.HOST`` too."""
    dest = root / "rendered"
    _source_lib(root, f'render_vhost "{DEPLOY_DIR / vhost}" "{dest}" caldart.test yes certbot')
    assert "www.caldart.test" in dest.read_text()


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_drops_the_www_alias(vhost: str, root: Path) -> None:
    """Without ``www`` no ``www.`` name is left in the vhost."""
    dest = root / "rendered"
    _source_lib(root, f'render_vhost "{DEPLOY_DIR / vhost}" "{dest}" caldart.test no certbot')
    assert "www." not in dest.read_text()


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_points_self_signed_at_the_local_certificate(vhost: str, root: Path) -> None:
    """In self-signed mode the certificate paths name ``/etc/caldart/tls/``."""
    dest = root / "rendered"
    _source_lib(root, f'render_vhost "{DEPLOY_DIR / vhost}" "{dest}" caldart.test yes self-signed')
    assert "/etc/letsencrypt/live/" not in dest.read_text()


def test_the_backup_unit_prunes_by_the_retention_variable() -> None:
    """``caldart-backup.service`` reads ``BACKUP_RETENTION_DAYS`` rather than a literal."""
    unit = (DEPLOY_DIR / "systemd" / "caldart-backup.service").read_text()
    assert "-mtime +${BACKUP_RETENTION_DAYS} -delete" in unit


def test_the_template_sets_the_backup_retention() -> None:
    """``caldart.env.example`` keeps dumps for 30 days by default."""
    assert "\nBACKUP_RETENTION_DAYS=30\n" in (DEPLOY_DIR / "caldart.env.example").read_text()


def test_gunicorn_finds_the_project_from_its_own_location() -> None:
    """``gunicorn.conf.py`` computes ``chdir`` from its own path, not ``/srv/caldart``."""
    config: dict[str, object] = {"__file__": "/opt/x/deploy/gunicorn.conf.py"}
    source = (DEPLOY_DIR / "gunicorn.conf.py").read_text()
    exec(compile(source, "gunicorn.conf.py", "exec"), config)  # noqa: S102 - our own config file
    assert config["chdir"] == "/opt/x/backend"


# -- manage.sh, upgrade.sh, uninstall.sh --------------------------------------------


def test_manage_runs_the_command_as_the_service_user(root: Path, etc: Path) -> None:
    """``manage.sh`` runs ``manage.py`` through ``systemd-run`` as ``caldart``."""
    result = _run(root / "deploy" / "manage.sh", "--dry-run", "migrate", env=_env(etc))
    command = _commands(result)[0]
    assert command.startswith("systemd-run --quiet --wait --collect --pty --pipe --uid=caldart")


def test_manage_writes_with_the_service_umask(root: Path, etc: Path) -> None:
    """A dump written through ``manage.sh`` is never world-readable."""
    result = _run(root / "deploy" / "manage.sh", "--dry-run", "db_backup", env=_env(etc))
    assert "--property=UMask=0027" in _commands(result)[0]


def test_manage_passes_the_arguments_through(root: Path, etc: Path) -> None:
    """Everything after the command name reaches ``manage.py`` unchanged."""
    result = _run(
        root / "deploy" / "manage.sh", "--dry-run", "health", "--json", env=_env(etc)
    )
    assert _commands(result)[0].endswith(f"{root}/.venv/bin/python manage.py health --json")


@pytest.fixture
def checkout(root: Path) -> Path:
    """The deploy root as a clean git checkout."""
    git = shutil.which("git")
    assert git is not None
    identity = ("-c", "user.name=Test", "-c", "user.email=test@example.org")
    for args in (("init", "-q"), ("add", "."), (*identity, "commit", "-qm", "init")):
        subprocess.run([git, *args], cwd=root, check=True, capture_output=True)  # noqa: S603 - fixed argv
    return root


def test_upgrade_backs_up_before_it_pulls(checkout: Path, etc: Path) -> None:
    """The upgrade takes a dump before it changes the code."""
    result = _run(checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=checkout)
    commands = _commands(result)
    assert _position(commands, "db_backup") < _position(commands, "git pull --ff-only")


def test_upgrade_ends_with_the_check(checkout: Path, etc: Path) -> None:
    """The last thing an upgrade runs is the check."""
    result = _run(checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=checkout)
    commands = _commands(result)
    assert _position(commands, "systemctl restart caldart-web") < _position(
        commands, "systemctl is-active"
    )


def test_upgrade_checks_out_a_ref(checkout: Path, etc: Path) -> None:
    """``--ref`` fetches and checks out that ref instead of pulling."""
    result = _run(
        checkout / "deploy" / "upgrade.sh", "--dry-run", "--ref", "v1.2", env=_env(etc), cwd=checkout
    )
    commands = _commands(result)
    assert _position(commands, "git fetch origin") < _position(commands, "git checkout v1.2")


def test_upgrade_never_touches_the_environment_file_or_the_vhost(
    checkout: Path, etc: Path
) -> None:
    """The upgrade leaves ``caldart.env`` and the web server's configuration alone."""
    result = _run(checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=checkout)
    output = result.stdout
    assert [word for word in ("caldart.env", "sites-available") if word in output] == []


def test_upgrade_refuses_local_changes(checkout: Path, etc: Path) -> None:
    """A checkout with local changes stops the upgrade before anything runs."""
    (checkout / "stray.txt").write_text("local change\n", encoding="utf-8")
    result = _run(checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=checkout)
    assert result.returncode == 1
    assert "local changes" in result.stderr


def test_uninstall_needs_yes(root: Path, etc: Path) -> None:
    """Without ``--yes`` the uninstall is a usage error."""
    result = _run(root / "deploy" / "uninstall.sh", "--dry-run", env=_env(etc))
    assert result.returncode == 2
    assert "--yes" in result.stderr


def test_uninstall_purge_removes_the_data(root: Path, etc: Path) -> None:
    """``--purge`` drops the database volume and the deploy root."""
    result = _run(root / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc))
    commands = _commands(result)
    assert _position(commands, "docker compose down -v") < _position(commands, f"rm -rf {root}")


def test_uninstall_dry_run_removes_nothing(root: Path, etc: Path) -> None:
    """The dry run of a purge leaves the deploy root in place."""
    _run(root / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc))
    assert (root / "deploy" / "lib.sh").is_file()


def test_uninstall_keeps_the_data_without_purge(root: Path, etc: Path) -> None:
    """Without ``--purge`` the database volume stays."""
    result = _run(root / "deploy" / "uninstall.sh", "--dry-run", "--yes", env=_env(etc))
    assert "docker compose down" not in result.stdout
