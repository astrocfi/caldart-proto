"""The server installer under ``deploy/``: its scripts, their dry run, and their files.

``docs/developer/deployment.rst`` describes the scripts: ``install.sh`` runs the steps
under ``deploy/steps/`` in order, and ``--dry-run`` prints every command that changes
the machine instead of running it.  These tests read that dry run as an ordered command
list and hold it to the order the guide gives.  Nothing here needs root, Docker, or the
network: every dry run happens in a copy of ``deploy/`` in a checkout under a deploy
root in ``tmp_path``, laid out as a server's ``/opt/caldart`` is, with ``CALDART_ETC``
pointing at an empty temporary directory, so even a script that forgot the dry run could
only touch the copy.  ``configure.sh`` runs for real into that
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
    "compose.sh",
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

#: The directory in the deploy root the checkout sits in, as ``bootstrap.sh`` clones it.
CHECKOUT_NAME: Final = "caldart"

#: The shell assignments that make ``/srv/x`` the deploy root for a sourced ``lib.sh``.
SRV_X_LAYOUT: Final = "CHECKOUT=/srv/x/caldart; ROOT=/srv/x;"

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
    """A deploy root holding a checkout with a copy of ``deploy/``.

    A dry run can touch only the copy.
    """
    target = tmp_path / "root"
    shutil.copytree(DEPLOY_DIR, _checkout(target) / "deploy")
    return target


@pytest.fixture
def checkout(root: Path) -> Path:
    """The checkout inside the deploy root ``root``."""
    return _checkout(root)


def _checkout(root: Path) -> Path:
    """The checkout inside the deploy root ``root``: its ``caldart`` directory."""
    return root / CHECKOUT_NAME


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


def _errors(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The ``error:`` lines a script printed on stderr, without its notes."""
    return [line for line in result.stderr.splitlines() if line.startswith("error:")]


def _position(commands: list[str], fragment: str) -> int:
    """The index of the first command containing ``fragment``; fails when none does."""
    for index, command in enumerate(commands):
        if fragment in command:
            return index
    pytest.fail(f"no command contains {fragment!r}")


def _machine_path(
    tmp_path: Path,
    *,
    listening: tuple[int, ...] = (),
    container: bool = False,
    service_home: str | None = None,
    active: tuple[str, ...] = (),
) -> str:
    """A ``PATH`` whose command shims describe a machine, ahead of the real ones.

    ``ss`` reports a listener on each port in ``listening`` and nothing else,
    ``docker container inspect`` finds the CalDART database container only when
    ``container`` is true, the ``caldart`` user exists, with ``service_home`` as its
    home directory, only when ``service_home`` is given, and ``systemctl is-active``
    reports exactly the units in ``active`` as active, so no test depends on what
    the machine running it has.  The shims sit ahead of the real commands, and hand
    any other question to them.
    """
    shims = tmp_path / "machine"
    shims.mkdir(exist_ok=True)
    active_units = " ".join(active)
    (shims / "systemctl").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = is-active ]; then\n'
        f'    for unit in {active_units}; do [ "$3" = "$unit" ] && exit 0; done; exit 3\n'
        "fi\n"
        'exec /usr/bin/systemctl "$@"\n'
    )
    user_exists = 0 if service_home is not None else 1
    passwd_line = f"caldart:x:999:999::{service_home}:/usr/sbin/nologin" if service_home else ""
    # Only the questions about the service user are answered here; anything else
    # (``id -u`` for the root check, say) goes to the real command.
    (shims / "id").write_text(
        f'#!/bin/sh\n[ "$*" = "-u caldart" ] && exit {user_exists}\nexec /usr/bin/id "$@"\n'
    )
    (shims / "getent").write_text(
        "#!/bin/sh\n"
        'if [ "$*" = "passwd caldart" ]; then\n'
        f'    [ -n "{passwd_line}" ] && echo "{passwd_line}"; exit 0\n'
        "fi\n"
        'exec /usr/bin/getent "$@"\n'
    )
    ports = " ".join(str(port) for port in listening)
    (shims / "ss").write_text(
        "#!/bin/sh\n"
        f"for port in {ports}; do\n"
        '    case "$*" in *":$port") echo "LISTEN 0 4096 127.0.0.1:$port 0.0.0.0:*" ;; esac\n'
        "done\n"
    )
    (shims / "docker").write_text(f"#!/bin/sh\nexit {0 if container else 1}\n")
    for shim in shims.iterdir():
        shim.chmod(0o755)
    return f"{shims}:{os.environ['PATH']}"


def _install_dry_run(
    root: Path,
    etc: Path,
    tmp_path: Path,
    *extra: str,
    listening: tuple[int, ...] = (),
    container: bool = False,
    service_home: str | None = None,
    active: tuple[str, ...] = (),
    flags: tuple[str, ...] = FIRST_INSTALL,
) -> subprocess.CompletedProcess[str]:
    """The dry run of a first ``install.sh`` on Ubuntu, plus the ``extra`` flags.

    ``listening``, ``container``, ``service_home``, and ``active`` describe the
    machine (see ``_machine_path``), and ``flags`` replaces the first-install flags
    the ``extra`` ones follow.
    """
    env = _env(
        etc,
        CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")),
        PATH=_machine_path(
            tmp_path,
            listening=listening,
            container=container,
            service_home=service_home,
            active=active,
        ),
    )
    return _run(_checkout(root) / "deploy" / "install.sh", "--dry-run", *flags, *extra, env=env)


def _variables(env_file: Path) -> dict[str, str]:
    """The uncommented ``KEY=value`` lines of an environment file."""
    lines = env_file.read_text().splitlines()
    pairs = [line.split("=", 1) for line in lines if "=" in line and not line.startswith("#")]
    return dict(pairs)


def _configure(root: Path, etc: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    """Run ``configure.sh`` for real into ``etc``."""
    return _run(
        _checkout(root) / "deploy" / "steps" / "configure.sh", *args, env=_env(etc, **extra)
    )


def _render_vhost(root: Path, vhost: str, www: str, tls: str) -> str:
    """What ``render_vhost`` writes for ``caldart.test`` under the root ``/srv/x``."""
    dest = root / "rendered"
    source = DEPLOY_DIR / vhost
    _source_lib(
        root,
        f'{SRV_X_LAYOUT} render_vhost "{source}" "{dest}" caldart.test {www} {tls}',
    )
    return dest.read_text()


def _source_lib(root: Path, snippet: str) -> subprocess.CompletedProcess[str]:
    """Run ``snippet`` in a shell that has sourced ``deploy/lib.sh`` as a script does.

    ``CHECKOUT`` is the checkout in ``root`` when the library is sourced, so ``ROOT`` is
    ``root``; a snippet that sets both first writes in another layout.
    """
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [
            BASH,
            "-c",
            f'set -euo pipefail; CHECKOUT="$2"; source "$1"; {snippet}',
            "bash",
            str(_checkout(root) / "deploy" / "lib.sh"),
            str(_checkout(root)),
        ],
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


#: The scripts that hand everything after their own flags to another program.
PASS_THROUGH: Final = ("manage.sh", "compose.sh")


@pytest.mark.parametrize("script", [name for name in ENTRY_POINTS if name not in PASS_THROUGH])
def test_an_unknown_flag_is_a_usage_error(script: str, etc: Path) -> None:
    """A flag the script does not know exits 2 with an ``error:`` line on stderr."""
    result = _run(DEPLOY_DIR / script, "--nonsense", env=_env(etc))
    assert result.returncode == 2
    assert "error: unknown option --nonsense" in result.stderr


def test_manage_without_a_command_is_a_usage_error(etc: Path) -> None:
    """``manage.sh`` hands its arguments to ``manage.py``, so it needs a command name."""
    result = _run(DEPLOY_DIR / "manage.sh", "--dry-run", env=_env(etc))
    assert result.returncode == 2
    assert _errors(result) == ["error: name the management command to run"]


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
        ("collectstatic", "systemctl restart caldart-web"),
        ("systemctl restart caldart-web", "systemctl enable --now caldart-registry.timer"),
        ("db_backup", "systemctl is-active"),
    ],
    ids=[
        "packages-before-the-user",
        "database-up-before-the-password",
        "build-before-collectstatic",
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


def test_the_vhost_is_enabled_after_the_certificate(root: Path, etc: Path, tmp_path: Path) -> None:
    """The shipped vhost names the certificate, so it goes in once certbot has one."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert _position(commands, "certbot certonly") < commands.index("a2ensite caldart")


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


@pytest.mark.parametrize("flag", ["--hostname", "--email-url", "--certbot-email"])
def test_a_first_install_names_the_flag_it_is_missing(
    flag: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """With no record and no environment file, a missing flag exits 2 naming it."""
    index = FIRST_INSTALL.index(flag)
    args = (*FIRST_INSTALL[:index], *FIRST_INSTALL[index + 2 :])
    result = _install_dry_run(root, etc, tmp_path, flags=args)
    assert result.returncode == 2
    assert flag in result.stderr


def test_an_unknown_web_server_is_a_usage_error(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--web-server`` accepts only ``apache`` and ``nginx``."""
    result = _install_dry_run(root, etc, tmp_path, "--web-server", "caddy")
    assert result.returncode == 2
    assert _errors(result) == ["error: --web-server must be apache or nginx, not caddy"]


@pytest.mark.parametrize(
    "hostname",
    ["https://caldart.org/", "caldart org", "caldart", "-caldart.org", "cal&dart.org"],
)
def test_a_hostname_that_is_not_a_dns_name_is_a_usage_error(
    hostname: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--hostname`` must be a DNS name: it is written into sed, the vhost, and files."""
    args = ["--hostname", hostname, *FIRST_INSTALL[2:]]
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")))
    result = _run(_checkout(root) / "deploy" / "install.sh", "--dry-run", *args, env=env)
    assert _errors(result) == [
        f"error: --hostname must be a DNS name such as caldart.example.org, not {hostname}"
    ]


def test_a_hostname_that_is_not_a_dns_name_exits_2(root: Path, etc: Path, tmp_path: Path) -> None:
    """A malformed ``--hostname`` is a usage error, not a failure."""
    args = ["--hostname", "https://caldart.org/", *FIRST_INSTALL[2:]]
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")))
    result = _run(_checkout(root) / "deploy" / "install.sh", "--dry-run", *args, env=env)
    assert result.returncode == 2


def test_the_install_record_supplies_the_flags(root: Path, etc: Path, tmp_path: Path) -> None:
    """A later run reads the hostname and the web server from ``install.conf``."""
    (etc / "install.conf").write_text(
        "CALDART_HOSTNAME=recorded.test\nCALDART_WWW=no\nCALDART_WEB_SERVER=nginx\n"
        "CALDART_TLS=self-signed\n"
    )
    (etc / "caldart.env").write_text("SECRET_KEY=x\n")
    result = _install_dry_run(root, etc, tmp_path, flags=())
    assert "/etc/nginx/sites-available/caldart" in result.stdout


def test_the_dry_run_prints_the_record_it_would_write(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The install record is written through ``install`` like every other file."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert f"install -m 0644 -o root -g root /dev/stdin {etc}/install.conf" in commands


# -- the database port --------------------------------------------------------------


def test_the_compose_file_publishes_the_configurable_port() -> None:
    """``docker-compose.yml`` publishes ``CALDART_DB_PORT`` on loopback, default 5432."""
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    assert '"127.0.0.1:${CALDART_DB_PORT:-5432}:5432"' in compose


def test_postgres_starts_on_5432_by_default(root: Path, etc: Path, tmp_path: Path) -> None:
    """Without ``--db-port`` the database is published on port 5432."""
    result = _install_dry_run(root, etc, tmp_path)
    assert "==> Starting Postgres on 127.0.0.1:5432" in result.stdout.splitlines()


def test_db_port_moves_postgres(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--db-port 5433`` publishes the database on port 5433."""
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "5433")
    assert "==> Starting Postgres on 127.0.0.1:5433" in result.stdout.splitlines()


@pytest.mark.parametrize("port", ["1023", "65536", "5433x", "05433", "-1"])
def test_a_db_port_out_of_range_is_a_usage_error(
    port: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--db-port`` takes an integer from 1024 to 65535 and nothing else."""
    result = _install_dry_run(root, etc, tmp_path, "--db-port", port)
    assert _errors(result) == [
        f"error: --db-port must be a port number from 1024 to 65535, not {port}"
    ]


def test_a_db_port_out_of_range_exits_2(root: Path, etc: Path, tmp_path: Path) -> None:
    """A malformed ``--db-port`` is a usage error, not a failure."""
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "80")
    assert result.returncode == 2


def test_the_install_record_keeps_the_db_port(root: Path) -> None:
    """``install.conf`` records ``CALDART_DB_PORT`` beside the other values."""
    result = _source_lib(root, "ROOT=/r; CALDART_DB_PORT=5433; write_file() { cat; }; write_record")
    assert "CALDART_DB_PORT=5433" in result.stdout.splitlines()


def test_the_recorded_db_port_reaches_docker_compose(root: Path) -> None:
    """``load_record`` exports ``CALDART_DB_PORT``, so ``docker compose`` sees it."""
    (root / "install.conf").write_text("CALDART_DB_PORT=5433\n")
    result = _source_lib(root, "load_record; bash -c 'printf %s \"$CALDART_DB_PORT\"'")
    assert result.stdout == "5433"


def test_a_taken_port_stops_the_first_postgres_start(root: Path, etc: Path, tmp_path: Path) -> None:
    """With no CalDART container yet, a listener on the port stops the install."""
    result = _install_dry_run(root, etc, tmp_path, listening=(5432,))
    assert _errors(result) == [
        "error: port 5432 is already in use on this machine; "
        "run install.sh --db-port PORT to put CalDART's Postgres on another port"
    ]


def test_a_taken_port_fails_the_install(root: Path, etc: Path, tmp_path: Path) -> None:
    """The taken-port refusal is a failure, exit 1."""
    result = _install_dry_run(root, etc, tmp_path, listening=(5432,))
    assert result.returncode == 1


def test_another_port_avoids_the_taken_one(root: Path, etc: Path, tmp_path: Path) -> None:
    """A Postgres already on 5432 is left alone when ``--db-port`` names another port."""
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "5433", listening=(5432,))
    assert result.returncode == 0, result.stderr


def test_an_existing_container_skips_the_port_check(root: Path, etc: Path, tmp_path: Path) -> None:
    """A later run finds its own container on the port and carries on."""
    result = _install_dry_run(root, etc, tmp_path, listening=(5432,), container=True)
    assert result.returncode == 0, result.stderr


def _installed_on_5432(etc: Path) -> None:
    """Write the record and environment file of a box with Postgres on 5432."""
    (etc / "install.conf").write_text(
        "CALDART_HOSTNAME=caldart.test\nCALDART_TLS=self-signed\nCALDART_DB_PORT=5432\n"
    )
    (etc / "caldart.env").write_text(
        "SECRET_KEY=x\nDATABASE_URL=postgres://caldart:pw@localhost:5432/caldart\n"
    )


def test_a_db_port_that_disagrees_with_database_url_is_refused(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """Moving the port on an installed box names ``DATABASE_URL`` first."""
    _installed_on_5432(etc)
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "5433", container=True, flags=())
    assert _errors(result) == [
        f"error: --db-port 5433 differs from the port in DATABASE_URL in {etc}/caldart.env "
        "(5432); edit DATABASE_URL to use port 5433 first, then run install.sh again"
    ]


def test_a_db_port_that_disagrees_with_database_url_exits_2(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The refusal is a usage error, not a failure."""
    _installed_on_5432(etc)
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "5433", container=True, flags=())
    assert result.returncode == 2


def test_a_db_port_that_matches_database_url_carries_on(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """Once ``DATABASE_URL`` names the new port, the run moves the container."""
    _installed_on_5432(etc)
    env_file = etc / "caldart.env"
    env_file.write_text(env_file.read_text().replace(":5432/", ":5433/"))
    result = _install_dry_run(root, etc, tmp_path, "--db-port", "5433", container=True, flags=())
    assert "==> Starting Postgres on 127.0.0.1:5433" in result.stdout.splitlines()


def test_configure_writes_the_recorded_db_port(root: Path, etc: Path) -> None:
    """``DATABASE_URL`` connects to the port the install record names."""
    (etc / "install.conf").write_text("CALDART_HOSTNAME=caldart.test\nCALDART_DB_PORT=5433\n")
    _configure(root, etc, "--email-url", "smtp://x:25")
    assert _variables(etc / "caldart.env")["DATABASE_URL"].endswith("@localhost:5433/caldart")


def test_configure_writes_5432_by_default(env_file: Path) -> None:
    """With no port recorded, ``DATABASE_URL`` connects to port 5432."""
    assert _variables(env_file)["DATABASE_URL"].endswith("@localhost:5432/caldart")


# -- compose.sh ---------------------------------------------------------------------


def test_compose_runs_with_the_recorded_port(root: Path, etc: Path) -> None:
    """``compose.sh`` hands its arguments to ``docker compose`` with the recorded port."""
    (etc / "install.conf").write_text("CALDART_DB_PORT=5433\n")
    result = _run(_checkout(root) / "deploy" / "compose.sh", "--dry-run", "ps", "db", env=_env(etc))
    assert _commands(result) == [
        f"cd {_checkout(root)}",
        "env CALDART_DB_PORT=5433 docker compose ps db",
    ]


def test_compose_defaults_to_5432(root: Path, etc: Path) -> None:
    """With no install record, ``compose.sh`` uses port 5432."""
    result = _run(
        _checkout(root) / "deploy" / "compose.sh", "--dry-run", "logs", "-f", "db", env=_env(etc)
    )
    assert _commands(result)[-1] == "env CALDART_DB_PORT=5432 docker compose logs -f db"


def test_compose_without_a_command_is_a_usage_error(etc: Path) -> None:
    """``compose.sh`` needs the ``docker compose`` command to run."""
    result = _run(DEPLOY_DIR / "compose.sh", "--dry-run", env=_env(etc))
    assert result.returncode == 2
    assert _errors(result) == ["error: name the docker compose command to run"]


# -- mail through a local postfix -------------------------------------------------------

#: The first-install flags with ``--email local`` in place of ``--email-url``.
LOCAL_MAIL_INSTALL: Final = (
    "--hostname",
    "caldart.test",
    "--certbot-email",
    "ops@caldart.test",
    "--email",
    "local",
)

#: The note ``configure.sh`` prints when ``--email local`` finds nothing on port 25.
PORT_25_NOTE: Final = (
    "Nothing listens on port 25 on this machine: mail fails until postfix is "
    "installed and listening on localhost."
)


def test_email_local_notes_an_empty_port_25(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--email local`` with nothing on port 25 prints the note and carries on."""
    result = _install_dry_run(root, etc, tmp_path, flags=LOCAL_MAIL_INSTALL)
    assert PORT_25_NOTE in result.stderr.splitlines()


def test_email_local_with_nothing_on_port_25_still_installs(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The port 25 note is not an error: the dry run exits 0."""
    result = _install_dry_run(root, etc, tmp_path, flags=LOCAL_MAIL_INSTALL)
    assert result.returncode == 0, result.stderr


def test_email_local_with_postfix_listening_prints_no_note(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """With something on port 25 the install says nothing about mail."""
    result = _install_dry_run(root, etc, tmp_path, flags=LOCAL_MAIL_INSTALL, listening=(25,))
    assert PORT_25_NOTE not in result.stderr.splitlines()


def test_email_local_and_email_url_together_are_a_usage_error(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--email local`` and ``--email-url`` are alternatives: both exits 2."""
    result = _install_dry_run(root, etc, tmp_path, "--email", "local")
    assert result.returncode == 2
    assert _errors(result) == ["error: give --email local or --email-url, not both"]


def test_email_takes_only_local(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--email`` accepts the one value ``local``."""
    result = _install_dry_run(root, etc, tmp_path, "--email", "smtp")
    assert _errors(result) == ["error: --email takes only local, not smtp"]


def test_a_first_install_without_mail_names_both_flags(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """With neither mail flag and no environment file, the error names both."""
    result = _install_dry_run(root, etc, tmp_path, flags=LOCAL_MAIL_INSTALL[:4])
    assert _errors(result) == [
        f"error: --email-url or --email local is required until {etc}/caldart.env exists"
    ]


def test_configure_email_local_relays_through_localhost(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--email local`` writes ``EMAIL_URL=smtp://localhost:25``."""
    _configure(
        root,
        etc,
        "--hostname",
        "caldart.test",
        "--email",
        "local",
        PATH=_machine_path(tmp_path, listening=(25,)),
    )
    assert _variables(etc / "caldart.env")["EMAIL_URL"] == "smtp://localhost:25"


def test_configure_reports_an_ignored_email_local(
    env_file: Path, root: Path, etc: Path, tmp_path: Path
) -> None:
    """Once the file exists, ``--email local`` is ignored and the step says so."""
    result = _configure(root, etc, "--email", "local", PATH=_machine_path(tmp_path))
    assert "--email local is ignored" in result.stdout


def test_bootstrap_passes_the_port_and_mail_flags_through(tmp_path: Path) -> None:
    """``--db-port`` and ``--email`` take values that reach ``install.sh``."""
    result = _bootstrap_dry_run(tmp_path, "--db-port", "5433", "--email", "local")
    assert _commands(result)[-1] == (
        f"bash {tmp_path}/srv/caldart/deploy/install.sh --dry-run --db-port 5433 --email local"
    )


# -- packages.sh --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("distro", "compose"),
    [("debian", "docker-compose"), ("ubuntu", "docker-compose-v2")],
)
def test_the_compose_package_follows_the_distribution(
    distro: str, compose: str, etc: Path, root: Path, tmp_path: Path
) -> None:
    """Debian installs ``docker-compose`` and Ubuntu ``docker-compose-v2``."""
    env = _env(
        etc,
        CALDART_OS_RELEASE=str(_os_release(tmp_path, distro)),
        PATH=_machine_path(tmp_path),
    )
    result = _run(_checkout(root) / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    commands = _commands(result)
    packages = commands[_position(commands, "apt-get install")].split()
    assert [name for name in packages if name.startswith("docker-compose")] == [compose]


def test_another_distribution_is_refused(etc: Path, root: Path, tmp_path: Path) -> None:
    """Any other ``ID`` stops with a message naming the two supported families."""
    env = _env(etc, CALDART_OS_RELEASE=str(_os_release(tmp_path, "fedora")))
    result = _run(_checkout(root) / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    assert result.returncode == 1
    assert "error: fedora is not supported; use Debian or Ubuntu" in result.stderr


def test_the_nodesource_installer_fails_when_its_download_fails(
    etc: Path, root: Path, tmp_path: Path
) -> None:
    """The ``curl | bash`` installer runs under ``pipefail``: a failed download stops."""
    shims = tmp_path / "shims"
    shims.mkdir()
    (shims / "node").write_text("#!/bin/sh\necho v18.19.1\n")
    (shims / "node").chmod(0o755)
    env = _env(
        etc,
        CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")),
        PATH=f"{shims}:{os.environ['PATH']}",
    )
    commands = _commands(
        _run(_checkout(root) / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    )
    assert "'set -o pipefail; curl" in commands[_position(commands, "deb.nodesource.com")]


# -- lib.sh -------------------------------------------------------------------------


def test_a_failing_command_names_the_stage_it_failed_in(root: Path) -> None:
    """A command failing under ``set -e`` leaves an ``error:`` line naming the stage."""
    result = _source_lib(root, 'log "Building the frontend"; false')
    assert result.stderr.splitlines() == [
        "error: Building the frontend failed: false exited with status 1"
    ]


def test_a_failing_command_keeps_its_exit_status(root: Path) -> None:
    """The stage report leaves the failing command's status as the script's."""
    result = _source_lib(root, 'log "Stage"; (exit 3)')
    assert result.returncode == 3


def test_a_command_tested_in_a_condition_reports_nothing(root: Path) -> None:
    """A command whose failure a condition handles is not an error."""
    result = _source_lib(root, 'log "Stage"; if false; then :; fi; false || true')
    assert result.stderr == ""


# -- bootstrap.sh -------------------------------------------------------------------


def _bootstrap_dry_run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The dry run of ``bootstrap.sh`` into an absent deploy root under ``tmp_path``."""
    env = _env(tmp_path, CALDART_ROOT=str(tmp_path / "srv"))
    return _run(DEPLOY_DIR / "bootstrap.sh", "--dry-run", "--repo", "/nowhere", *args, env=env)


def test_bootstrap_masks_the_email_url(tmp_path: Path) -> None:
    """The mail relay's credential is never printed in the installer line."""
    result = _bootstrap_dry_run(tmp_path, "--email-url", "smtp+tls://user:mailsecret@x.org:587")
    assert _commands(result)[-1] == (
        f"bash {tmp_path}/srv/caldart/deploy/install.sh --dry-run --email-url '<email-url>'"
    )


def test_bootstrap_quotes_what_it_prints(tmp_path: Path) -> None:
    """An argument with spaces is printed shell-quoted, so the line runs as printed."""
    result = _bootstrap_dry_run(tmp_path, "--from-email", "CalDART <ops@x.org>")
    assert _commands(result)[-1] == (
        f"bash {tmp_path}/srv/caldart/deploy/install.sh --dry-run "
        "--from-email 'CalDART <ops@x.org>'"
    )


# -- configure.sh -------------------------------------------------------------------


@pytest.fixture
def env_file(root: Path, etc: Path) -> Path:
    """The environment file ``configure.sh`` writes for ``caldart.test``."""
    result = _configure(
        root, etc, "--hostname", "caldart.test", "--email-url", "smtp://localhost:25"
    )
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
    ("variable", "suffix"), [("BACKUP_DIR", "backups"), ("MEDIA_ROOT", "media")]
)
def test_configure_puts_the_data_in_the_deploy_root(
    variable: str, suffix: str, env_file: Path, root: Path
) -> None:
    """``BACKUP_DIR`` and ``MEDIA_ROOT`` name directories in the deploy root.

    They sit beside the checkout rather than inside it.
    """
    assert _variables(env_file)[variable] == f"{root}/{suffix}"


def test_configure_puts_the_user_guide_in_the_checkout(env_file: Path, checkout: Path) -> None:
    """``USER_GUIDE_ROOT`` names the build output inside the checkout."""
    assert _variables(env_file)["USER_GUIDE_ROOT"] == f"{checkout}/docs/_build/guide"


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
    """A second run leaves the file alone and says ``--email-url`` is ignored."""
    result = _configure(root, etc, "--email-url", "smtp://elsewhere:25")
    assert "--email-url is ignored" in result.stdout


def test_configure_without_www_names_one_host(root: Path, etc: Path) -> None:
    """``--no-www`` leaves the ``www.`` form out of ``ALLOWED_HOSTS``."""
    _configure(root, etc, "--hostname", "caldart.test", "--no-www", "--email-url", "smtp://x:25")
    assert _variables(etc / "caldart.env")["ALLOWED_HOSTS"] == "caldart.test"


def test_self_signed_turns_hsts_off(root: Path, etc: Path) -> None:
    """With ``--tls self-signed`` the file sets ``SECURE_HSTS_SECONDS=0``."""
    _configure(
        root,
        etc,
        "--hostname",
        "caldart.test",
        "--tls",
        "self-signed",
        "--email-url",
        "smtp://x:25",
    )
    assert _variables(etc / "caldart.env")["SECURE_HSTS_SECONDS"] == "0"


def test_certbot_keeps_the_hsts_default(env_file: Path) -> None:
    """With certbot the template's commented HSTS default stands."""
    assert "SECURE_HSTS_SECONDS" not in _variables(env_file)


def test_configure_needs_a_hostname(root: Path, etc: Path) -> None:
    """With no record and no ``--hostname`` the step exits 2 naming the flag."""
    result = _configure(root, etc, "--email-url", "smtp://localhost:25")
    assert result.returncode == 2
    assert _errors(result) == [f"error: --hostname is required to write {etc}/caldart.env"]


def test_configure_refuses_a_hostname_that_is_not_a_dns_name(root: Path, etc: Path) -> None:
    """``configure.sh`` checks ``--hostname`` as ``install.sh`` does."""
    result = _configure(root, etc, "--hostname", "https://x.org/", "--email-url", "smtp://x:25")
    assert _errors(result) == [
        "error: --hostname must be a DNS name such as caldart.example.org, not https://x.org/"
    ]


@pytest.fixture
def recorded_env_file(root: Path, etc: Path) -> Path:
    """What ``configure.sh`` writes from the install record and ``--email-url``."""
    (etc / "install.conf").write_text(
        "CALDART_HOSTNAME=recorded.test\nCALDART_WWW=no\nCALDART_TLS=self-signed\n"
    )
    result = _configure(root, etc, "--email-url", "smtp://x:25")
    assert result.returncode == 0, result.stderr
    return etc / "caldart.env"


@pytest.mark.parametrize(
    ("variable", "expected"),
    [("ALLOWED_HOSTS", "recorded.test"), ("SECURE_HSTS_SECONDS", "0")],
)
def test_configure_reads_the_install_record(
    variable: str, expected: str, recorded_env_file: Path
) -> None:
    """Run alone, the step reads the hostname, ``www``, and TLS mode from the record."""
    assert _variables(recorded_env_file)[variable] == expected


def test_a_configure_flag_overrides_the_install_record(root: Path, etc: Path) -> None:
    """``--hostname`` given to the step wins over the recorded one."""
    (etc / "install.conf").write_text("CALDART_HOSTNAME=recorded.test\nCALDART_WWW=no\n")
    _configure(root, etc, "--hostname", "flag.test", "--email-url", "smtp://x:25")
    assert _variables(etc / "caldart.env")["ALLOWED_HOSTS"] == "flag.test"


@pytest.fixture
def exec_log(root: Path, etc: Path, tmp_path: Path) -> tuple[str, Path]:
    """The argv of every program ``configure.sh`` execs, logged by shims on ``PATH``.

    Returns the file the step wrote, read back, and the log of argument lists.
    """
    shims = tmp_path / "shims"
    shims.mkdir()
    log = tmp_path / "exec.log"
    real_path = os.environ["PATH"]
    for program in ("env", "awk", "install", "python3", "sed", "cat"):
        shim = shims / program
        shim.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$0 $*" >> "{log}"\n'
            f'PATH="{real_path}" exec {program} "$@"\n'
        )
        shim.chmod(0o755)
    result = _run(
        _checkout(root) / "deploy" / "steps" / "configure.sh",
        "--hostname",
        "caldart.test",
        "--email-url",
        "smtp://user:mailsecret@localhost:25",
        env={**_env(etc), "PATH": f"{shims}:{real_path}"},
    )
    assert result.returncode == 0, result.stderr
    assert "awk" in log.read_text()
    return (etc / "caldart.env").read_text(), log


@pytest.mark.parametrize("variable", ["SECRET_KEY", "DATABASE_URL", "EMAIL_URL"])
def test_configure_never_puts_a_secret_on_a_command_line(
    variable: str, exec_log: tuple[str, Path]
) -> None:
    """The key, the database password, and the mail relay reach no program's arguments."""
    content, log = exec_log
    values = [
        line.split("=", 1)[1] for line in content.splitlines() if line.startswith(f"{variable}=")
    ]
    assert [line for line in log.read_text().splitlines() if values[0] in line] == []


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
    """``render_file`` replaces ``/opt/caldart`` with the root as it copies a file."""
    dest = root / "rendered"
    _source_lib(root, f'{SRV_X_LAYOUT} render_file "{DEPLOY_DIR / source}" "{dest}"')
    assert "/opt/caldart" not in dest.read_text()


@pytest.mark.parametrize("source", [*(f"systemd/{unit}" for unit in UNITS), *VHOSTS])
def test_every_shipped_file_names_the_opt_root(source: str) -> None:
    """The units and the vhosts name ``/opt/caldart``, the default deploy root."""
    assert "/opt/caldart" in (DEPLOY_DIR / source).read_text()


def test_bootstrap_names_the_opt_root(etc: Path) -> None:
    """``bootstrap.sh`` uses ``/opt/caldart`` unless ``CALDART_ROOT`` says not."""
    result = _run(DEPLOY_DIR / "bootstrap.sh", "--help", env=_env(etc))
    assert (
        "CALDART_ROOT   the deploy root, which the checkout goes in as caldart/\n"
        "                 (default /opt/caldart)"
    ) in result.stdout


@pytest.mark.parametrize(
    "source", [f"systemd/{unit}" for unit in UNITS if unit.endswith("service")]
)
def test_render_file_writes_the_checkout(source: str, root: Path) -> None:
    """A rendered service runs the interpreter in the checkout under the deploy root."""
    assert "/srv/x/caldart/.venv/bin/" in _render_at_srv_x(root, source)


@pytest.mark.parametrize(
    "source", [f"systemd/{unit}" for unit in UNITS if unit.endswith("service")]
)
def test_every_service_works_in_the_checkouts_backend(source: str) -> None:
    """Every shipped service runs from ``backend/`` in the checkout in the deploy root."""
    assert "WorkingDirectory=/opt/caldart/caldart/backend\n" in (DEPLOY_DIR / source).read_text()


@pytest.mark.parametrize(
    "path",
    [
        "ReadWritePaths=/srv/x/media\n",
        "ReadWritePaths=/srv/x/backups\n",
        "ReadWritePaths=/srv/x/caldart/backend/staticfiles\n",
    ],
)
def test_the_web_unit_writes_the_data_in_the_deploy_root(path: str, root: Path) -> None:
    """The web unit may write the uploads and dumps beside the checkout.

    It may also write the static files, which live in the checkout.
    """
    assert path in _render_at_srv_x(root, "systemd/caldart-web.service")


@pytest.mark.parametrize(
    "path", ["/srv/x/caldart/backups", "/srv/x/caldart/media", "backend/media"]
)
def test_nothing_rendered_puts_the_data_in_the_checkout(path: str, root: Path) -> None:
    """No unit, vhost, or snippet names a dump or upload directory inside the checkout."""
    sources = [*(f"systemd/{unit}" for unit in UNITS), *VHOSTS, *(s for s, _ in SNIPPETS.values())]
    assert [source for source in sources if path in _render_at_srv_x(root, source)] == []


def test_render_file_writes_a_checkout_path_once(root: Path) -> None:
    """A deploy root that itself lies under ``/opt/caldart`` is not written in twice."""
    dest = root / "rendered"
    source = DEPLOY_DIR / "systemd" / "caldart-web.service"
    _source_lib(
        root,
        "CHECKOUT=/opt/caldart/site/caldart; ROOT=/opt/caldart/site; "
        f'render_file "{source}" "{dest}"',
    )
    assert "WorkingDirectory=/opt/caldart/site/caldart/backend\n" in dest.read_text()


@pytest.mark.parametrize(
    ("vhost", "fragment"),
    [
        ("apache/caldart.conf", "Alias /media/ /srv/x/media/"),
        ("apache/caldart.conf", '<Directory "/srv/x/media/documents">'),
        ("nginx/caldart.conf", "alias /srv/x/media/;"),
    ],
)
def test_the_vhost_serves_the_uploads_from_the_deploy_root(
    vhost: str, fragment: str, root: Path
) -> None:
    """Each vhost aliases ``/media/`` to the deploy root's ``media`` directory."""
    assert fragment in _render_vhost(root, vhost, "yes", "certbot")


def _render_at_srv_x(root: Path, source: str) -> str:
    """What ``render_file`` writes from ``source`` for the deploy root ``/srv/x``."""
    dest = root / "rendered"
    result = _source_lib(
        root,
        f'{SRV_X_LAYOUT} render_file "{DEPLOY_DIR / source}" "{dest}"',
    )
    assert result.returncode == 0, result.stderr
    return dest.read_text()


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_replaces_the_example_hostname(vhost: str, root: Path) -> None:
    """Every ``caldart.example.org`` in a vhost becomes the hostname."""
    assert "caldart.example.org" not in _render_vhost(root, vhost, "yes", "certbot")


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_keeps_the_www_alias(vhost: str, root: Path) -> None:
    """With ``www`` the vhost answers for ``www.HOST`` too."""
    assert "www.caldart.test" in _render_vhost(root, vhost, "yes", "certbot")


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_drops_the_www_alias(vhost: str, root: Path) -> None:
    """Without ``www`` no ``www.`` name is left in the vhost."""
    assert "www." not in _render_vhost(root, vhost, "no", "certbot")


@pytest.mark.parametrize("vhost", VHOSTS)
def test_render_vhost_points_self_signed_at_the_local_certificate(vhost: str, root: Path) -> None:
    """In self-signed mode the certificate paths name ``/etc/caldart/tls/``."""
    assert "/etc/letsencrypt/live/" not in _render_vhost(root, vhost, "yes", "self-signed")


def test_the_backup_unit_prunes_by_the_retention_variable() -> None:
    """``caldart-backup.service`` prunes by ``BACKUP_RETENTION_DAYS``, not a literal."""
    unit = (DEPLOY_DIR / "systemd" / "caldart-backup.service").read_text()
    assert "-mtime +${BACKUP_RETENTION_DAYS} -delete" in unit


def test_the_template_sets_the_backup_retention() -> None:
    """``caldart.env.example`` keeps dumps for 30 days by default."""
    assert "\nBACKUP_RETENTION_DAYS=30\n" in (DEPLOY_DIR / "caldart.env.example").read_text()


def test_gunicorn_finds_the_project_from_its_own_location() -> None:
    """``gunicorn.conf.py`` computes ``chdir`` from its own path, not ``/opt/caldart``."""
    config: dict[str, object] = {"__file__": "/srv/x/caldart/deploy/gunicorn.conf.py"}
    source = (DEPLOY_DIR / "gunicorn.conf.py").read_text()
    exec(compile(source, "gunicorn.conf.py", "exec"), config)  # noqa: S102 - our own config file
    assert config["chdir"] == "/srv/x/caldart/backend"


# -- manage.sh, upgrade.sh, uninstall.sh --------------------------------------------


def test_manage_runs_the_command_as_the_service_user(root: Path, etc: Path) -> None:
    """``manage.sh`` runs ``manage.py`` through ``systemd-run`` as ``caldart``."""
    result = _run(_checkout(root) / "deploy" / "manage.sh", "--dry-run", "migrate", env=_env(etc))
    command = _commands(result)[0]
    assert command.startswith("systemd-run --quiet --wait --collect --pty --pipe --uid=caldart")


def test_manage_writes_with_the_service_umask(root: Path, etc: Path) -> None:
    """A dump written through ``manage.sh`` is never world-readable."""
    result = _run(_checkout(root) / "deploy" / "manage.sh", "--dry-run", "db_backup", env=_env(etc))
    assert "--property=UMask=0027" in _commands(result)[0]


def test_manage_passes_the_arguments_through(root: Path, etc: Path) -> None:
    """Everything after the command name reaches ``manage.py`` unchanged."""
    result = _run(
        _checkout(root) / "deploy" / "manage.sh", "--dry-run", "health", "--json", env=_env(etc)
    )
    assert _commands(result)[0].endswith(
        f"{_checkout(root)}/.venv/bin/python manage.py health --json"
    )


@pytest.fixture
def git_checkout(checkout: Path) -> Path:
    """The checkout in the deploy root as a clean git checkout."""
    git = shutil.which("git")
    assert git is not None
    identity = ("-c", "user.name=Test", "-c", "user.email=test@example.org")
    for args in (("init", "-q"), ("add", "."), (*identity, "commit", "-qm", "init")):
        subprocess.run([git, *args], cwd=checkout, check=True, capture_output=True)  # noqa: S603 - fixed argv
    return checkout


def test_upgrade_backs_up_before_it_pulls(git_checkout: Path, etc: Path) -> None:
    """The upgrade takes a dump before it changes the code."""
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    commands = _commands(result)
    assert _position(commands, "db_backup") < _position(commands, "git pull --ff-only")


def test_upgrade_reopens_the_uploads_to_the_web_server(git_checkout: Path, etc: Path) -> None:
    """After pulling, the upgrade runs the user step, which opens every upload to Apache.

    An install whose uploads were written under ``UMask=0027`` has ``0750`` directories
    and ``0640`` files the web server cannot read; the upgrade repairs them before it
    restarts the site.
    """
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    commands = _commands(result)
    media = git_checkout.parent / "media"
    reopen_dirs = f"find {media} -type d -exec chmod 0755 '{{}}' +"
    reopen_files = f"find {media} -type f -exec chmod 0644 '{{}}' +"
    assert _position(commands, "git pull --ff-only") < _position(commands, reopen_dirs)
    assert _position(commands, reopen_files) < _position(commands, "systemctl restart caldart-web")


def test_upgrade_ends_with_the_check(git_checkout: Path, etc: Path) -> None:
    """The last thing an upgrade runs is the check."""
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    commands = _commands(result)
    assert _position(commands, "systemctl restart caldart-web") < _position(
        commands, "systemctl is-active"
    )


def test_upgrade_checks_out_a_ref(git_checkout: Path, etc: Path) -> None:
    """``--ref`` fetches and checks out that ref instead of pulling."""
    result = _run(
        git_checkout / "deploy" / "upgrade.sh",
        "--dry-run",
        "--ref",
        "v1.2",
        env=_env(etc),
        cwd=git_checkout,
    )
    commands = _commands(result)
    assert _position(commands, "git fetch origin") < _position(commands, "git checkout v1.2")


def test_upgrade_never_touches_the_environment_file_or_the_vhost(
    git_checkout: Path, etc: Path
) -> None:
    """The upgrade leaves ``caldart.env`` and the web server's configuration alone."""
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    commands = _commands(result)
    written = [c for c in commands if c.endswith("caldart.env") or "sites-available" in c]
    assert written == []


def test_upgrade_refuses_local_changes(git_checkout: Path, etc: Path) -> None:
    """A checkout with local changes stops the upgrade before the code changes."""
    (git_checkout / "stray.txt").write_text("local change\n", encoding="utf-8")
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    assert result.returncode == 1
    assert _errors(result) == [
        f"error: the checkout at {git_checkout} has local changes; "
        "commit, stash, or discard them first"
    ]


def test_upgrade_refuses_a_detached_head_before_the_backup(git_checkout: Path, etc: Path) -> None:
    """A plain upgrade of a checkout left detached by ``--ref`` stops naming the fix."""
    git = shutil.which("git")
    assert git is not None
    subprocess.run(  # noqa: S603 - fixed argv
        [git, "checkout", "-q", "--detach"], cwd=git_checkout, check=True, capture_output=True
    )
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    assert _errors(result) == [
        "error: the checkout is on a detached HEAD; run upgrade.sh --ref <branch>"
    ]


def test_upgrade_of_a_detached_head_takes_no_backup(git_checkout: Path, etc: Path) -> None:
    """The detached-HEAD refusal comes before anything runs."""
    git = shutil.which("git")
    assert git is not None
    subprocess.run(  # noqa: S603 - fixed argv
        [git, "checkout", "-q", "--detach"], cwd=git_checkout, check=True, capture_output=True
    )
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    assert _commands(result) == []


def test_uninstall_needs_yes(root: Path, etc: Path) -> None:
    """Without ``--yes`` the uninstall is a usage error."""
    result = _run(_checkout(root) / "deploy" / "uninstall.sh", "--dry-run", env=_env(etc))
    assert result.returncode == 2
    assert _errors(result) == ["error: --yes is required: this removes the site"]


def _purge_dry_run(root: Path, etc: Path) -> list[str]:
    """The commands the dry run of ``uninstall.sh --yes --purge`` in ``root`` prints."""
    result = _run(
        _checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc)
    )
    assert result.returncode == 0, result.stderr
    return _commands(result)


def _deploy_root_with_data(root: Path) -> Path:
    """Give the deploy root ``root`` the dumps and uploads directories of an install."""
    (root / "backups").mkdir()
    (root / "media").mkdir()
    return root


def test_uninstall_purge_removes_the_data(root: Path, etc: Path) -> None:
    """``--purge`` drops the database volume before it removes the checkout."""
    commands = _purge_dry_run(root, etc)
    assert _position(commands, "docker compose down -v") < _position(
        commands, f"rm -rf {_checkout(root)}"
    )


@pytest.mark.parametrize("entry", [CHECKOUT_NAME, "backups", "media"])
def test_uninstall_purge_removes_what_the_install_made(entry: str, root: Path, etc: Path) -> None:
    """``--purge`` removes the checkout, the dumps, and the uploads in the deploy root."""
    commands = _purge_dry_run(_deploy_root_with_data(root), etc)
    assert f"rm -rf {root / entry}" in commands


def test_uninstall_purge_removes_the_emptied_deploy_root(root: Path, etc: Path) -> None:
    """A deploy root that holds only what the install made is removed once emptied."""
    commands = _purge_dry_run(_deploy_root_with_data(root), etc)
    assert commands[-1] == f"rmdir {root}"


def test_uninstall_purge_never_removes_the_deploy_root_whole(root: Path, etc: Path) -> None:
    """The purge removes the deploy root's entries one by one, never the root at once."""
    commands = _purge_dry_run(_deploy_root_with_data(root), etc)
    assert f"rm -rf {root}" not in commands


def test_uninstall_purge_keeps_a_deploy_root_holding_more(root: Path, etc: Path) -> None:
    """A deploy root that holds anything else keeps it, and the root stays."""
    (_deploy_root_with_data(root) / "other").mkdir()
    commands = _purge_dry_run(root, etc)
    assert [c for c in commands if c.startswith("rmdir") or str(root / "other") in c] == []


def test_uninstall_purge_says_it_keeps_a_deploy_root_holding_more(root: Path, etc: Path) -> None:
    """The purge names the deploy root it leaves in place."""
    (root / "other").mkdir()
    result = _run(
        _checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc)
    )
    assert (
        f"kept {root}: it holds more than the checkout, the backups, and the uploads"
    ) in result.stderr.splitlines()


def test_uninstall_purge_of_a_checkout_layout_removes_only_the_checkout(
    root: Path, etc: Path
) -> None:
    """A record naming the checkout as the deploy root purges the checkout alone.

    The dumps and uploads of such an install are inside the checkout, and its parent
    (``/opt`` for a checkout at ``/opt/caldart``) belongs to the machine.
    """
    _record_checkout_layout(root, etc)
    commands = _purge_dry_run(_deploy_root_with_data(root), etc)
    removed = [c for c in commands if c.startswith(("rm -rf", "rmdir")) and str(etc) not in c]
    assert removed == [f"rm -rf {_checkout(root)}"]


def test_uninstall_purge_says_what_the_deploy_root_holds(root: Path, etc: Path) -> None:
    """The purge's stage line names the checkout, the backups, and the uploads."""
    result = _run(
        _checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc)
    )
    assert (
        f"==> Removing the configuration, the database, and {root} "
        "(the checkout, the backups, and the uploads)"
    ) in result.stdout.splitlines()


def test_uninstall_purge_composes_down_from_the_checkout(root: Path, etc: Path) -> None:
    """``docker compose down`` runs where ``docker-compose.yml`` is: the checkout."""
    result = _run(
        _checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc)
    )
    commands = _commands(result)
    assert commands[_position(commands, "docker compose down -v") - 1] == f"cd {_checkout(root)}"


def test_uninstall_dry_run_removes_nothing(root: Path, etc: Path) -> None:
    """The dry run of a purge leaves the deploy root in place."""
    _run(
        _checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", "--purge", env=_env(etc)
    )
    assert (_checkout(root) / "deploy" / "lib.sh").is_file()


def test_uninstall_keeps_the_data_without_purge(root: Path, etc: Path) -> None:
    """Without ``--purge`` the database volume stays."""
    result = _run(_checkout(root) / "deploy" / "uninstall.sh", "--dry-run", "--yes", env=_env(etc))
    assert "docker compose down" not in result.stdout


# -- an install whose checkout is the deploy root ----------------------------------

#: The message every script but the uninstaller, manage.sh, and compose.sh stops with on
#: an install that keeps its data inside the checkout.
CHECKOUT_LAYOUT_ERROR: Final = (
    "error: this install keeps its data inside the checkout at {checkout}; "
    "see 'Moving to the current layout' in deploy/README.rst"
)

#: Every step, each of which refuses such an install when run on its own.
STEPS: Final = sorted(
    path.relative_to(DEPLOY_DIR).as_posix() for path in (DEPLOY_DIR / "steps").glob("*.sh")
)


def _record_checkout_layout(root: Path, etc: Path) -> None:
    """Write an install record whose deploy root is the checkout in ``root`` itself."""
    (etc / "install.conf").write_text(
        f"CALDART_ROOT={_checkout(root)}\nCALDART_HOSTNAME=caldart.test\n"
    )


@pytest.mark.parametrize("script", ["install.sh", *STEPS])
def test_a_checkout_layout_is_refused(script: str, root: Path, etc: Path) -> None:
    """The installer and every step stop, naming the runbook section, and run nothing."""
    _record_checkout_layout(root, etc)
    result = _run(_checkout(root) / "deploy" / script, "--dry-run", env=_env(etc))
    assert (_errors(result), _commands(result), result.returncode) == (
        [CHECKOUT_LAYOUT_ERROR.format(checkout=_checkout(root))],
        [],
        1,
    )


def test_an_upgrade_of_a_checkout_layout_is_refused_before_the_backup(
    git_checkout: Path, etc: Path
) -> None:
    """``upgrade.sh`` stops before it backs up, pulls, or restarts anything."""
    _record_checkout_layout(git_checkout.parent, etc)
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    assert (_errors(result), _commands(result)) == (
        [CHECKOUT_LAYOUT_ERROR.format(checkout=git_checkout)],
        [],
    )


def test_manage_still_runs_on_a_checkout_layout(root: Path, etc: Path) -> None:
    """``manage.sh`` still runs there, so the backup the move starts with can be taken."""
    _record_checkout_layout(root, etc)
    result = _run(_checkout(root) / "deploy" / "manage.sh", "--dry-run", "db_backup", env=_env(etc))
    assert result.returncode == 0, result.stderr


def test_a_deploy_root_elsewhere_is_not_a_checkout_layout(root: Path, etc: Path) -> None:
    """A record naming the checkout's parent as the deploy root lets a step run."""
    (etc / "install.conf").write_text(f"CALDART_ROOT={root}\n")
    result = _run(_checkout(root) / "deploy" / "steps" / "build.sh", "--dry-run", env=_env(etc))
    assert result.returncode == 0, result.stderr


def test_bootstrap_refuses_a_deploy_root_that_is_a_checkout(tmp_path: Path) -> None:
    """``bootstrap.sh`` never clones into a checkout that is itself the deploy root."""
    (tmp_path / "srv" / ".git").mkdir(parents=True)
    result = _bootstrap_dry_run(tmp_path)
    assert (_errors(result), _commands(result)) == (
        [
            f"error: {tmp_path}/srv is a checkout, which keeps the data inside it; "
            "see 'Moving to the current layout' in deploy/README.rst"
        ],
        [],
    )


# -- a real machine, as the rehearsal in a systemd container finds it ---------------


@pytest.mark.parametrize(
    ("web_server", "unit"), [("apache", "apache2"), ("nginx", "nginx")], ids=["apache", "nginx"]
)
def test_the_web_server_step_starts_a_stopped_web_server(
    web_server: str, unit: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """The vhost is applied with ``reload-or-restart``, which starts a stopped server.

    A package install need not leave the web server running (a ``policy-rc.d`` can
    forbid it, and an operator can stop it), and ``systemctl reload`` fails on a
    stopped unit.
    """
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--web-server", web_server, "--tls", "self-signed")
    )
    assert f"systemctl reload-or-restart {unit}" in commands


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_the_web_server_step_never_plainly_reloads(
    web_server: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """The install's web-server step never runs a plain ``systemctl reload``.

    ``uninstall.sh`` still does, guarded by ``systemctl is-active``: removing a vhost
    from a server that was never started does not need to start it, so the guard
    (rather than ``reload-or-restart``) is the right fix there.
    """
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--web-server", web_server))
    assert [command for command in commands if command.startswith("systemctl reload ")] == []


# -- under a URL prefix, behind an existing site ------------------------------------

#: The prefix the tests serve the site under; production code never names it.
PREFIX: Final = "/caldart-proto"

#: The first-install flags for a site under ``PREFIX`` behind an existing HTTPS site.
EXISTING_INSTALL: Final = (
    "--hostname",
    "caldart.test",
    "--tls",
    "existing",
    "--url-prefix",
    PREFIX,
    "--email",
    "local",
)

#: The shipped snippets and where the ``existing`` mode installs each one.
SNIPPETS: Final = {
    "apache": ("apache/caldart-attach.conf", "/etc/apache2/conf-available/caldart.conf"),
    "nginx": ("nginx/caldart-attach.conf", "/etc/nginx/snippets/caldart.conf"),
}

#: The line that includes the snippet in the existing site's vhost, per web server.
INCLUDE_LINES: Final = {
    "apache": "Include conf-available/caldart.conf",
    "nginx": "include snippets/caldart.conf;",
}

#: An existing Apache site: a plain-HTTP host that redirects, and the HTTPS one.
APACHE_SITE: Final = """\
<VirtualHost *:80>
    ServerName caldart.test
    Redirect permanent / https://caldart.test/
</VirtualHost>

<VirtualHost *:443>
    ServerName caldart.test
    SSLEngine on
    DocumentRoot /var/www/html
</VirtualHost>
"""

#: ``APACHE_SITE`` with the snippet included in its HTTPS host.
APACHE_SITE_ATTACHED: Final = APACHE_SITE.replace(
    "    DocumentRoot /var/www/html\n",
    "    DocumentRoot /var/www/html\n    Include conf-available/caldart.conf\n",
)

#: An existing nginx site: a plain-HTTP server, and the HTTPS one with a location.
NGINX_SITE: Final = """\
server {
    listen 80;
    server_name caldart.test;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name caldart.test;
    location / {
        root /var/www/html;
    }
}
"""

#: ``NGINX_SITE`` with the snippet included in its HTTPS server.
NGINX_SITE_ATTACHED: Final = NGINX_SITE.replace(
    "        root /var/www/html;\n    }\n}\n",
    "        root /var/www/html;\n    }\n    include snippets/caldart.conf;\n}\n",
)

#: An Apache site as certbot leaves it: a ``:80`` host that redirects with mod_alias,
#: and a ``:443`` host whose ``SSLEngine`` comes from certbot's options include.
APACHE_CERTBOT_SITE: Final = """\
<VirtualHost *:80>
    ServerName caldart.test
    Redirect permanent / https://caldart.test/
</VirtualHost>
<IfModule mod_ssl.c>
<virtualhost *:443>
    ServerName caldart.test
    DocumentRoot /var/www/html
    SSLCertificateFile /etc/letsencrypt/live/caldart.test/fullchain.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</virtualhost>
</IfModule>
"""

#: ``APACHE_CERTBOT_SITE`` with the snippet included in its ``:443`` host only.
APACHE_CERTBOT_SITE_ATTACHED: Final = APACHE_CERTBOT_SITE.replace(
    "    Include /etc/letsencrypt/options-ssl-apache.conf\n",
    "    Include /etc/letsencrypt/options-ssl-apache.conf\n"
    "    Include conf-available/caldart.conf\n",
)

#: An nginx site whose HTTPS server listens on 443 without ``ssl`` on the ``listen``.
NGINX_CERTIFICATE_SITE: Final = """\
server {
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443;
    ssl_certificate /etc/ssl/site.pem;
}
"""

#: ``NGINX_CERTIFICATE_SITE`` with the snippet included in its HTTPS server only.
NGINX_CERTIFICATE_SITE_ATTACHED: Final = NGINX_CERTIFICATE_SITE.replace(
    "    ssl_certificate /etc/ssl/site.pem;\n}\n",
    "    ssl_certificate /etc/ssl/site.pem;\n    include snippets/caldart.conf;\n}\n",
)

#: A shell function that stands in for a configuration check that fails.
FAILING_CHECK: Final = {
    "apache": "apachectl() { echo 'Syntax error' >&2; return 1; }",
    "nginx": "nginx() { echo 'duplicate location' >&2; return 1; }",
}


def _render_snippet(root: Path, source: str, prefix: str) -> str:
    """What ``render_snippet`` writes from ``source`` for ``prefix`` under ``/srv/x``."""
    dest = root / "rendered"
    result = _source_lib(
        root,
        f"{SRV_X_LAYOUT} CALDART_HOSTNAME=caldart.test; CALDART_URL_PREFIX={prefix}; "
        f'render_snippet "{DEPLOY_DIR / source}" "{dest}"',
    )
    assert result.returncode == 0, result.stderr
    return dest.read_text()


def _attach(
    root: Path, web_server: str, vhost: Path, *, then: str = ""
) -> subprocess.CompletedProcess[str]:
    """Run ``attach_include`` from the web-server step on ``vhost``, then ``then``."""
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [
            BASH,
            "-c",
            'set -euo pipefail; source "$1"; CALDART_WEB_SERVER=$2; attach_include "$3"; ' + then,
            "bash",
            str(_checkout(root) / "deploy" / "steps" / "web-server.sh"),
            web_server,
            str(vhost),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_env(root),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("caldart-proto", "/caldart-proto"),
        ("/caldart-proto", "/caldart-proto"),
        ("/caldart-proto/", "/caldart-proto"),
        ("/dart/caldart-proto", "/dart/caldart-proto"),
        ("/", ""),
        ("", ""),
    ],
)
def test_the_url_prefix_is_normalized(raw: str, expected: str, root: Path) -> None:
    """One leading and one trailing slash are optional, as ``URL_PREFIX`` reads them."""
    result = _source_lib(
        root, f"CALDART_URL_PREFIX='{raw}'; validate_url_prefix; printf %s \"$CALDART_URL_PREFIX\""
    )
    assert result.stdout == expected


@pytest.mark.parametrize("prefix", ["//x//", "/a b", "/../x", "/x?y", "/./x", "/x#y"])
def test_a_url_prefix_that_is_not_a_path_is_a_usage_error(
    prefix: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--url-prefix`` segments are letters, digits, ``.``, ``_``, ``~``, and ``-``."""
    flags = (*EXISTING_INSTALL[:5], prefix, *EXISTING_INSTALL[6:])
    result = _install_dry_run(root, etc, tmp_path, flags=flags)
    assert _errors(result) == [
        f"error: --url-prefix must be a path such as /caldart-proto, not {prefix}"
    ]


def test_a_url_prefix_that_is_not_a_path_exits_2(root: Path, etc: Path, tmp_path: Path) -> None:
    """A malformed ``--url-prefix`` is a usage error, not a failure."""
    flags = (*EXISTING_INSTALL[:5], "//x//", *EXISTING_INSTALL[6:])
    result = _install_dry_run(root, etc, tmp_path, flags=flags)
    assert result.returncode == 2


@pytest.mark.parametrize(
    ("key", "line"),
    [
        ("CALDART_URL_PREFIX", f"CALDART_URL_PREFIX={PREFIX}"),
        ("CALDART_ATTACH_TO", "CALDART_ATTACH_TO=/etc/apache2/sites-available/site.conf"),
    ],
)
def test_the_install_record_keeps_the_prefix_and_the_attached_file(
    key: str, line: str, root: Path
) -> None:
    """``install.conf`` records the prefix and the vhost the snippet is included in."""
    result = _source_lib(
        root,
        f"ROOT=/r; CALDART_URL_PREFIX={PREFIX}; "
        "CALDART_ATTACH_TO=/etc/apache2/sites-available/site.conf; "
        "write_file() { cat; }; write_record",
    )
    assert line in result.stdout.splitlines()


def test_the_recorded_prefix_is_read_back(root: Path) -> None:
    """``load_record`` reads ``CALDART_URL_PREFIX`` like every other recorded value."""
    (root / "install.conf").write_text(f"CALDART_URL_PREFIX={PREFIX}\n")
    result = _source_lib(root, 'load_record; printf %s "$CALDART_URL_PREFIX"')
    assert result.stdout == PREFIX


def test_an_unknown_tls_mode_names_the_three(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--tls`` accepts ``certbot``, ``self-signed``, and ``existing``."""
    result = _install_dry_run(root, etc, tmp_path, "--tls", "none")
    assert _errors(result) == ["error: --tls must be certbot, self-signed, or existing, not none"]


def test_existing_needs_no_certbot_email(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--tls existing`` obtains no certificate, so it needs no Let's Encrypt account."""
    result = _install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL)
    assert result.returncode == 0, result.stderr


def test_existing_never_runs_certbot(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--tls existing`` installs no certbot package and runs no certbot command."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL))
    assert [command for command in commands if "certbot" in command] == []


def test_existing_still_installs_the_web_server(root: Path, etc: Path, tmp_path: Path) -> None:
    """The web server package stays: its tools check and reload the configuration."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL))
    assert "apache2" in commands[_position(commands, "apt-get install")].split()


def test_existing_makes_no_certificate(root: Path, etc: Path, tmp_path: Path) -> None:
    """The existing site's certificate is the one browsers see: no ``openssl req``."""
    output = _install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL).stdout
    assert "openssl req" not in output


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_existing_installs_no_vhost(web_server: str, root: Path, etc: Path, tmp_path: Path) -> None:
    """``--tls existing`` writes nothing into the web server's sites directory."""
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--web-server", web_server, flags=EXISTING_INSTALL)
    )
    assert [command for command in commands if "sites-available/caldart" in command] == []


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_existing_installs_the_snippet(
    web_server: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """The snippet is rendered to the web server's include directory."""
    source, dest = SNIPPETS[web_server]
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--web-server", web_server, flags=EXISTING_INSTALL)
    )
    rendered = commands[_position(commands, f"deploy/{source}")]
    assert rendered.endswith(f"install -m 0644 /dev/stdin {dest}")


def test_existing_nginx_installs_the_upstream_once(root: Path, etc: Path, tmp_path: Path) -> None:
    """The nginx upstream goes in ``conf.d``, outside the snippet a server includes."""
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--web-server", "nginx", flags=EXISTING_INSTALL)
    )
    rendered = commands[_position(commands, "deploy/nginx/caldart-upstream.conf")]
    assert rendered.endswith("install -m 0644 /dev/stdin /etc/nginx/conf.d/caldart-upstream.conf")


@pytest.mark.parametrize(("web_server", "unit"), [("apache", "apache2"), ("nginx", "nginx")])
def test_existing_reloads_the_web_server(
    web_server: str, unit: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """After the snippet, the configuration is checked and the server reloaded."""
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--web-server", web_server, flags=EXISTING_INSTALL)
    )
    assert f"systemctl reload-or-restart {unit}" in commands


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_without_attach_to_the_step_prints_the_include_line(
    web_server: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """With no ``--attach-to`` the step says which line to add to the existing vhost."""
    output = _install_dry_run(
        root, etc, tmp_path, "--web-server", web_server, flags=EXISTING_INSTALL
    ).stdout
    assert f"    {INCLUDE_LINES[web_server]}" in output.splitlines()


def test_attach_to_needs_the_existing_mode(root: Path, etc: Path, tmp_path: Path) -> None:
    """``--attach-to`` names an existing site's vhost, so it needs ``--tls existing``."""
    result = _install_dry_run(root, etc, tmp_path, "--attach-to", "/etc/apache2/x.conf")
    assert _errors(result) == ["error: --attach-to is used only with --tls existing"]


def test_attach_to_must_be_an_absolute_path(root: Path, etc: Path, tmp_path: Path) -> None:
    """A relative ``--attach-to`` would mean a different file for each step."""
    result = _install_dry_run(
        root, etc, tmp_path, "--attach-to", "site.conf", flags=EXISTING_INSTALL
    )
    assert _errors(result) == ["error: --attach-to must be an absolute path, not site.conf"]


def test_the_owner_one_liner_inserts_the_include(root: Path, etc: Path, tmp_path: Path) -> None:
    """The dry run with ``--attach-to`` prints the insertion into the named file."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE)
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--attach-to", str(vhost), flags=EXISTING_INSTALL)
    )
    assert (
        f"sed -i --follow-symlinks -e '10i\\    Include conf-available/caldart.conf' {vhost}"
        in commands
    )


def test_the_owner_one_liner_keeps_a_copy(root: Path, etc: Path, tmp_path: Path) -> None:
    """The dry run copies the vhost aside before it inserts the include."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE)
    commands = _commands(
        _install_dry_run(root, etc, tmp_path, "--attach-to", str(vhost), flags=EXISTING_INSTALL)
    )
    assert _position(commands, f"cp -p {vhost} {vhost}.caldart.bak") < _position(commands, "sed -i")


def test_the_one_liner_dry_run_names_an_absent_vhost(root: Path, etc: Path, tmp_path: Path) -> None:
    """A dry run on a machine without the named vhost still prints the insertion."""
    vhost = tmp_path / "absent.conf"
    result = _install_dry_run(
        root, etc, tmp_path, "--attach-to", str(vhost), flags=EXISTING_INSTALL
    )
    assert (
        f"dry run: {vhost} does not exist here; the real run inserts "
        "'Include conf-available/caldart.conf' before the end of each HTTPS block in it"
    ) in result.stderr.splitlines()


@pytest.mark.parametrize(
    ("web_server", "site", "attached"),
    [("apache", APACHE_SITE, APACHE_SITE_ATTACHED), ("nginx", NGINX_SITE, NGINX_SITE_ATTACHED)],
)
def test_the_include_goes_in_the_https_block(
    web_server: str, site: str, attached: str, root: Path, tmp_path: Path
) -> None:
    """The include line lands before the end of the block that serves HTTPS, only."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    result = _attach(root, web_server, vhost)
    assert result.returncode == 0, result.stderr
    assert vhost.read_text() == attached


@pytest.mark.parametrize(
    ("web_server", "site", "attached"),
    [
        ("apache", APACHE_CERTBOT_SITE, APACHE_CERTBOT_SITE_ATTACHED),
        ("nginx", NGINX_CERTIFICATE_SITE, NGINX_CERTIFICATE_SITE_ATTACHED),
    ],
    ids=["apache-certbot", "nginx-ssl-certificate"],
)
def test_a_block_with_a_certificate_counts_as_https(
    web_server: str, site: str, attached: str, root: Path, tmp_path: Path
) -> None:
    """A certificate or port 443 marks HTTPS; the plain-HTTP block gets no include."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    result = _attach(root, web_server, vhost)
    assert result.returncode == 0, result.stderr
    assert vhost.read_text() == attached


@pytest.mark.parametrize(
    ("web_server", "site"),
    [("apache", APACHE_SITE), ("nginx", NGINX_SITE)],
    ids=["apache", "nginx"],
)
def test_a_failed_check_puts_the_vhost_back(
    web_server: str, site: str, root: Path, tmp_path: Path
) -> None:
    """When the configuration check fails, the include this run inserted is taken out."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    _attach(root, web_server, vhost, then=f'{FAILING_CHECK[web_server]}; check_or_detach "$3"')
    assert vhost.read_text() == site


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_a_failed_check_says_the_vhost_was_put_back(
    web_server: str, root: Path, tmp_path: Path
) -> None:
    """The step stops naming itself and the vhost it restored."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE if web_server == "apache" else NGINX_SITE)
    result = _attach(
        root, web_server, vhost, then=f'{FAILING_CHECK[web_server]}; check_or_detach "$3"'
    )
    assert _errors(result) == [
        "error: web-server step: the configuration check failed with the snippet included; "
        f"{vhost} is back as it was before this run"
    ]


def test_a_failed_check_leaves_an_earlier_include_alone(root: Path, tmp_path: Path) -> None:
    """A vhost that carried the include before this run keeps it: nothing was inserted."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE_ATTACHED)
    _attach(root, "apache", vhost, then=f'{FAILING_CHECK["apache"]}; check_or_detach "$3"')
    assert vhost.read_text() == APACHE_SITE_ATTACHED


def test_a_failed_check_without_an_insertion_names_the_step(root: Path, tmp_path: Path) -> None:
    """With nothing to put back, the step stops saying the check failed."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE_ATTACHED)
    result = _attach(root, "apache", vhost, then=f'{FAILING_CHECK["apache"]}; check_or_detach "$3"')
    assert _errors(result) == [
        "error: web-server step: the configuration check failed with the snippet in place"
    ]


@pytest.mark.parametrize(
    ("web_server", "site"),
    [
        ("apache", "<VirtualHost *:80>\n    ServerName a.test\n</VirtualHost>\n"),
        ("nginx", "server {\n    listen 80;\n}\n"),
    ],
)
def test_without_an_https_block_every_block_gets_the_include(
    web_server: str, site: str, root: Path, tmp_path: Path
) -> None:
    """A vhost that terminates no TLS (behind a proxy) gets the line in every block."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    _attach(root, web_server, vhost)
    assert f"    {INCLUDE_LINES[web_server]}\n" in vhost.read_text()


@pytest.mark.parametrize(("web_server", "site"), [("apache", APACHE_SITE), ("nginx", NGINX_SITE)])
def test_attaching_twice_changes_nothing(
    web_server: str, site: str, root: Path, tmp_path: Path
) -> None:
    """A vhost already carrying the include line is left byte-identical."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    _attach(root, web_server, vhost)
    once = vhost.read_bytes()
    _attach(root, web_server, vhost)
    assert vhost.read_bytes() == once


@pytest.mark.parametrize(("web_server", "site"), [("apache", APACHE_SITE), ("nginx", NGINX_SITE)])
def test_attaching_keeps_the_original_beside_it(
    web_server: str, site: str, root: Path, tmp_path: Path
) -> None:
    """``FILE.caldart.bak`` holds the vhost as it was before the first insertion."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(site)
    _attach(root, web_server, vhost)
    _attach(root, web_server, vhost)
    assert (tmp_path / "site.conf.caldart.bak").read_text() == site


def test_attaching_through_a_symlink_keeps_the_link(root: Path, tmp_path: Path) -> None:
    """An ``--attach-to`` in ``sites-enabled`` edits the file the link points at."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE)
    link = tmp_path / "enabled.conf"
    link.symlink_to(vhost)
    _attach(root, "apache", link)
    assert link.is_symlink()


def test_attaching_through_a_symlink_edits_its_target(root: Path, tmp_path: Path) -> None:
    """The include line lands in the vhost the link points at."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE)
    link = tmp_path / "enabled.conf"
    link.symlink_to(vhost)
    _attach(root, "apache", link)
    assert vhost.read_text() == APACHE_SITE_ATTACHED


@pytest.mark.parametrize(
    ("web_server", "block"), [("apache", "<VirtualHost>"), ("nginx", "server")]
)
def test_a_vhost_with_no_block_is_refused(
    web_server: str, block: str, root: Path, tmp_path: Path
) -> None:
    """A file with nothing to include the snippet in stops the step naming the file."""
    vhost = tmp_path / "site.conf"
    vhost.write_text("# nothing here\n")
    result = _attach(root, web_server, vhost)
    assert _errors(result) == [f"error: {vhost} holds no {block} block to include the snippet in"]


def test_a_missing_vhost_is_refused(root: Path, tmp_path: Path) -> None:
    """A real run on an ``--attach-to`` that does not exist stops naming it."""
    vhost = tmp_path / "absent.conf"
    result = _attach(root, "apache", vhost)
    assert _errors(result) == [
        f"error: {vhost} does not exist; --attach-to names the vhost file of the existing site"
    ]


@pytest.mark.parametrize(
    ("web_server", "fragment"),
    [
        ("apache", 'ProxyPass "/caldart-proto/" "http://127.0.0.1:8001/"'),
        ("apache", 'ProxyPass "/caldart-proto/media/" "!"'),
        ("apache", 'RedirectMatch 301 "^/caldart-proto$" "/caldart-proto/"'),
        ("apache", 'Alias "/caldart-proto/media/" "/srv/x/media/"'),
        ("apache", '<Directory "/srv/x/media/documents">'),
        ("nginx", "location ^~ /caldart-proto/ {"),
        ("nginx", "proxy_pass http://caldart_app/;"),
        ("nginx", "location ^~ /caldart-proto/media/documents/ {"),
        ("nginx", "alias /srv/x/media/;"),
        ("nginx", "return 301 /caldart-proto/;"),
    ],
)
def test_the_snippet_serves_the_prefix(web_server: str, fragment: str, root: Path) -> None:
    """The snippet proxies the prefix, serves media, and redirects the bare path."""
    assert fragment in _render_snippet(root, SNIPPETS[web_server][0], PREFIX)


@pytest.mark.parametrize("web_server", ["apache", "nginx"])
def test_the_snippet_leaves_no_placeholder(web_server: str, root: Path) -> None:
    """Every ``__PREFIX__`` and ``/opt/caldart`` is replaced as the snippet is copied."""
    rendered = _render_snippet(root, SNIPPETS[web_server][0], PREFIX)
    assert [word for word in ("__PREFIX__", "/opt/caldart") if word in rendered] == []


@pytest.mark.parametrize(
    ("web_server", "fragment"),
    [
        ("apache", "RequestHeader unset X-Forwarded-Ssl"),
        ("apache", "RequestHeader unset X-Forwarded-Protocol"),
        ("nginx", 'proxy_set_header X-Forwarded-Ssl   "";'),
        ("nginx", 'proxy_set_header X-Forwarded-Protocol "";'),
    ],
)
def test_the_snippet_drops_the_other_scheme_headers(
    web_server: str, fragment: str, root: Path
) -> None:
    """A client's own scheme headers never reach gunicorn to contradict the proxy's."""
    assert fragment in _render_snippet(root, SNIPPETS[web_server][0], PREFIX)


def test_the_apache_snippet_sends_the_scheme(root: Path) -> None:
    """Django learns the request arrived over HTTPS from the proxy's header."""
    rendered = _render_snippet(root, SNIPPETS["apache"][0], PREFIX)
    assert 'RequestHeader set X-Forwarded-Proto "https"' in rendered


def test_the_apache_snippet_keeps_media_ahead_of_the_proxy(root: Path) -> None:
    """``ProxyPass P/media/ !`` must come before ``ProxyPass P/`` or the proxy wins."""
    rendered = _render_snippet(root, SNIPPETS["apache"][0], PREFIX)
    assert rendered.index('ProxyPass "/caldart-proto/media/"') < rendered.index(
        'ProxyPass "/caldart-proto/" '
    )


def test_the_nginx_snippet_defines_no_upstream(root: Path) -> None:
    """A second include of the snippet must not define ``caldart_app`` again."""
    rendered = _render_snippet(root, SNIPPETS["nginx"][0], PREFIX)
    assert "upstream caldart_app" not in rendered


def test_the_nginx_upstream_names_gunicorn() -> None:
    """``caldart-upstream.conf`` points ``caldart_app`` at gunicorn on loopback."""
    upstream = (DEPLOY_DIR / "nginx" / "caldart-upstream.conf").read_text()
    assert "server 127.0.0.1:8001" in upstream


@pytest.mark.parametrize(
    ("web_server", "fragment"),
    [
        ("apache", 'ProxyPass "/" "http://127.0.0.1:8001/"'),
        ("nginx", "location ^~ / {"),
    ],
)
def test_the_snippet_without_a_prefix_serves_the_whole_host(
    web_server: str, fragment: str, root: Path
) -> None:
    """With no prefix the snippet proxies everything from ``/``."""
    assert fragment in _render_snippet(root, SNIPPETS[web_server][0], "")


@pytest.fixture
def prefixed_env_file(root: Path, etc: Path, tmp_path: Path) -> Path:
    """What ``configure.sh`` writes for ``caldart.test`` under ``PREFIX``."""
    result = _configure(
        root,
        etc,
        "--hostname",
        "caldart.test",
        "--tls",
        "existing",
        "--url-prefix",
        PREFIX,
        "--email",
        "local",
        PATH=_machine_path(tmp_path, listening=(25,)),
    )
    assert result.returncode == 0, result.stderr
    return etc / "caldart.env"


@pytest.mark.parametrize(
    ("variable", "expected"),
    [
        ("SITE_URL", f"https://caldart.test{PREFIX}"),
        ("URL_PREFIX", PREFIX),
        ("ALLOWED_HOSTS", "caldart.test,www.caldart.test"),
        ("CSRF_TRUSTED_ORIGINS", "https://caldart.test,https://www.caldart.test"),
    ],
)
def test_configure_writes_the_prefix(variable: str, expected: str, prefixed_env_file: Path) -> None:
    """``SITE_URL`` ends in the prefix, and the origins stay scheme and host."""
    assert _variables(prefixed_env_file)[variable] == expected


def test_configure_leaves_hsts_to_the_existing_site(prefixed_env_file: Path) -> None:
    """In ``existing`` mode the template's HSTS default is not written over."""
    assert "SECURE_HSTS_SECONDS" not in _variables(prefixed_env_file)


def test_configure_without_a_prefix_leaves_url_prefix_commented(env_file: Path) -> None:
    """A site at the root of its host keeps the template's commented ``URL_PREFIX``."""
    assert "URL_PREFIX" not in _variables(env_file)


def test_a_prefixed_file_passes_the_deployment_checks(prefixed_env_file: Path) -> None:
    """``prod.py`` accepts the file: ``SITE_URL`` ends in ``URL_PREFIX``."""
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
        env={**base, **_variables(prefixed_env_file)},
    )
    assert result.returncode == 0, result.stderr


def _installed_at_the_root(etc: Path) -> None:
    """Write the record and environment file of a box serving from ``/``."""
    (etc / "install.conf").write_text("CALDART_HOSTNAME=caldart.test\nCALDART_TLS=existing\n")
    (etc / "caldart.env").write_text(
        "SECRET_KEY=x\nSITE_URL=https://caldart.test\n#URL_PREFIX=\n"
        "DATABASE_URL=postgres://caldart:pw@localhost:5432/caldart\n"
    )


def test_a_prefix_that_disagrees_with_the_env_file_is_refused(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """Moving an installed site under a prefix names ``URL_PREFIX`` first."""
    _installed_at_the_root(etc)
    result = _install_dry_run(root, etc, tmp_path, "--url-prefix", PREFIX, flags=())
    assert _errors(result) == [
        f"error: the URL prefix {PREFIX} differs from URL_PREFIX in {etc}/caldart.env (none); "
        "set URL_PREFIX and the path of SITE_URL there to match first, then run install.sh again"
    ]


def test_a_prefix_that_disagrees_with_the_env_file_exits_2(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The refusal is a usage error, not a failure."""
    _installed_at_the_root(etc)
    result = _install_dry_run(root, etc, tmp_path, "--url-prefix", PREFIX, flags=())
    assert result.returncode == 2


def test_a_prefix_that_matches_the_env_file_carries_on(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """Once ``URL_PREFIX`` names the prefix, the install runs."""
    _installed_at_the_root(etc)
    env_file = etc / "caldart.env"
    env_file.write_text(env_file.read_text().replace("#URL_PREFIX=", f"URL_PREFIX={PREFIX}/"))
    result = _install_dry_run(root, etc, tmp_path, "--url-prefix", PREFIX, flags=())
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", [f"{PREFIX}/", f"{PREFIX}/portal/login"], ids=["home", "login"])
def test_the_check_requests_the_prefixed_site(
    path: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """``check.sh`` asks for the home page and the sign-in page under the prefix."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL))
    assert f"curl -sk --resolve caldart.test:443:127.0.0.1 https://caldart.test{path}" in commands


def test_the_check_fetches_the_portal_bundle(root: Path, etc: Path, tmp_path: Path) -> None:
    """``check.sh`` fetches the script the sign-in page names, under the prefix."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL))
    assert (
        "curl -sk --resolve caldart.test:443:127.0.0.1 "
        f"'https://caldart.test{PREFIX}/static/<the bundle the sign-in page names>'"
    ) in commands


def test_the_summary_names_the_prefixed_address(root: Path, etc: Path, tmp_path: Path) -> None:
    """The last lines give the site's address with its prefix."""
    output = _install_dry_run(root, etc, tmp_path, flags=EXISTING_INSTALL).stdout
    assert f"CalDART is running at https://caldart.test{PREFIX}/" in output.splitlines()


def test_bootstrap_passes_the_prefix_and_attach_flags_through(tmp_path: Path) -> None:
    """``--url-prefix`` and ``--attach-to`` take values that reach ``install.sh``."""
    result = _bootstrap_dry_run(tmp_path, "--url-prefix", PREFIX, "--attach-to", "/etc/a.conf")
    assert _commands(result)[-1] == (
        f"bash {tmp_path}/srv/caldart/deploy/install.sh --dry-run --url-prefix {PREFIX} "
        "--attach-to /etc/a.conf"
    )


def test_uninstall_takes_the_include_line_out(root: Path, etc: Path, tmp_path: Path) -> None:
    """The recorded vhost loses the include line and nothing else."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE_ATTACHED)
    (etc / "install.conf").write_text(f"CALDART_TLS=existing\nCALDART_ATTACH_TO={vhost}\n")
    result = _run(_checkout(root) / "deploy" / "uninstall.sh", "--yes", "--dry-run", env=_env(etc))
    assert (
        "sed -i --follow-symlinks -e "
        f"'\\#^[[:space:]]*Include conf-available/caldart\\.conf[[:space:]]*$#d' {vhost}"
        in _commands(result)
    )


def test_uninstall_leaves_a_vhost_without_the_line_alone(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """A recorded vhost that no longer carries the include line is not edited."""
    vhost = tmp_path / "site.conf"
    vhost.write_text(APACHE_SITE)
    (etc / "install.conf").write_text(f"CALDART_TLS=existing\nCALDART_ATTACH_TO={vhost}\n")
    result = _run(_checkout(root) / "deploy" / "uninstall.sh", "--yes", "--dry-run", env=_env(etc))
    assert [command for command in _commands(result) if str(vhost) in command] == []


# -- a machine whose Docker is already installed ------------------------------------


def _packages_dry_run(etc: Path, root: Path, tmp_path: Path, docker: str) -> list[str]:
    """The ``apt-get install`` line of ``packages.sh`` with ``docker`` as the machine's.

    ``docker`` is a shell script body for the ``docker`` on ``PATH``.
    """
    shims = tmp_path / "docker-shims"
    shims.mkdir()
    (shims / "docker").write_text(f"#!/bin/sh\n{docker}\n")
    (shims / "docker").chmod(0o755)
    env = _env(
        etc,
        CALDART_OS_RELEASE=str(_os_release(tmp_path, "ubuntu")),
        PATH=f"{shims}:{os.environ['PATH']}",
    )
    commands = _commands(
        _run(_checkout(root) / "deploy" / "steps" / "packages.sh", "--dry-run", env=env)
    )
    return commands[_position(commands, "apt-get install")].split()


def test_a_working_docker_skips_the_docker_packages(etc: Path, root: Path, tmp_path: Path) -> None:
    """With ``docker compose`` already working, neither Docker package is installed."""
    packages = _packages_dry_run(etc, root, tmp_path, "exit 0")
    assert [name for name in packages if name.startswith("docker")] == []


def test_a_docker_without_compose_gets_only_compose(etc: Path, root: Path, tmp_path: Path) -> None:
    """A Docker with no Compose v2 plugin keeps its engine and gains the plugin."""
    packages = _packages_dry_run(
        etc, root, tmp_path, 'case "$1" in compose) exit 1 ;; *) exit 0 ;; esac'
    )
    assert [name for name in packages if name.startswith("docker")] == ["docker-compose-v2"]


def test_no_docker_installs_both_packages(etc: Path, root: Path, tmp_path: Path) -> None:
    """A machine without Docker gets the engine and the Compose v2 plugin."""
    packages = _packages_dry_run(etc, root, tmp_path, "exit 127")
    assert [name for name in packages if name.startswith("docker")] == [
        "docker.io",
        "docker-compose-v2",
    ]


# -- the gunicorn port --------------------------------------------------------------

#: A gunicorn port other than the default, which every test below moves gunicorn to.
GUNICORN_PORT: Final = "8101"

#: An install record that puts gunicorn on ``GUNICORN_PORT``.
MOVED_RECORD: Final = "CALDART_HOSTNAME=caldart.test\nCALDART_GUNICORN_PORT=8101\n"

#: Every shipped file that names gunicorn's address, and the function that copies it.
GUNICORN_FILES: Final = (
    ("apache/caldart.conf", "vhost"),
    ("nginx/caldart.conf", "vhost"),
    ("apache/caldart-attach.conf", "snippet"),
    ("nginx/caldart-upstream.conf", "snippet"),
)


def _render_with_port(root: Path, source: str, how: str, port: str) -> str:
    """What ``render_vhost`` or ``render_snippet`` writes from ``source`` for ``port``."""
    dest = root / "rendered"
    call = (
        f'render_vhost "{DEPLOY_DIR / source}" "{dest}" caldart.test yes certbot'
        if how == "vhost"
        else f'render_snippet "{DEPLOY_DIR / source}" "{dest}"'
    )
    result = _source_lib(
        root,
        f"{SRV_X_LAYOUT} CALDART_HOSTNAME=caldart.test; CALDART_GUNICORN_PORT={port}; {call}",
    )
    assert result.returncode == 0, result.stderr
    return dest.read_text()


def _web_service(
    root: Path, etc: Path, tmp_path: Path, *, installed: bool, listening: tuple[int, ...]
) -> subprocess.CompletedProcess[str]:
    """The dry run of the web-service step, with the unit installed or not."""
    answer = 0 if installed else 1
    env = _env(etc, PATH=_machine_path(tmp_path, listening=listening))
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [
            BASH,
            "-c",
            'set -euo pipefail; source "$1"; enable_dry_run; CALDART_HOSTNAME=caldart.test; '
            f"web_unit_installed() {{ return {answer}; }}; web_service_step",
            "bash",
            str(_checkout(root) / "deploy" / "steps" / "web-service.sh"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _gunicorn_bind(monkeypatch: pytest.MonkeyPatch, port: str | None) -> object:
    """The ``bind`` of ``gunicorn.conf.py`` with ``CALDART_GUNICORN_PORT`` at ``port``."""
    if port is None:
        monkeypatch.delenv("CALDART_GUNICORN_PORT", raising=False)
    else:
        monkeypatch.setenv("CALDART_GUNICORN_PORT", port)
    config: dict[str, object] = {"__file__": "/srv/x/caldart/deploy/gunicorn.conf.py"}
    source = (DEPLOY_DIR / "gunicorn.conf.py").read_text()
    exec(compile(source, "gunicorn.conf.py", "exec"), config)  # noqa: S102 - our own config file
    return config["bind"]


def test_gunicorn_binds_to_the_port_in_its_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """``CALDART_GUNICORN_PORT`` from the unit's environment file sets the port."""
    assert _gunicorn_bind(monkeypatch, GUNICORN_PORT) == "127.0.0.1:8101"


def test_gunicorn_binds_to_8001_without_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no ``CALDART_GUNICORN_PORT`` gunicorn listens on 8001."""
    assert _gunicorn_bind(monkeypatch, None) == "127.0.0.1:8001"


def test_the_install_record_keeps_the_gunicorn_port(root: Path) -> None:
    """``install.conf`` records ``CALDART_GUNICORN_PORT`` beside the other values."""
    result = _source_lib(
        root, "ROOT=/r; CALDART_GUNICORN_PORT=8101; write_file() { cat; }; write_record"
    )
    assert "CALDART_GUNICORN_PORT=8101" in result.stdout.splitlines()


def test_the_recorded_gunicorn_port_is_read_back(root: Path) -> None:
    """``load_record`` reads ``CALDART_GUNICORN_PORT`` and exports it."""
    (root / "install.conf").write_text("CALDART_GUNICORN_PORT=8101\n")
    result = _source_lib(root, "load_record; bash -c 'printf %s \"$CALDART_GUNICORN_PORT\"'")
    assert result.stdout == "8101"


def test_a_record_without_the_gunicorn_port_reads_as_8001(root: Path) -> None:
    """An install record written before the key existed means port 8001."""
    (root / "install.conf").write_text("CALDART_HOSTNAME=caldart.test\n")
    result = _source_lib(root, 'load_record; printf %s "$CALDART_GUNICORN_PORT"')
    assert result.stdout == "8001"


@pytest.mark.parametrize("port", ["80", "70000", "abc"])
def test_a_gunicorn_port_out_of_range_is_a_usage_error(
    port: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """``--gunicorn-port`` takes an integer from 1024 to 65535 and nothing else."""
    result = _install_dry_run(root, etc, tmp_path, "--gunicorn-port", port)
    assert _errors(result) == [
        f"error: --gunicorn-port must be a port number from 1024 to 65535, not {port}"
    ]


def test_a_gunicorn_port_out_of_range_exits_2(root: Path, etc: Path, tmp_path: Path) -> None:
    """A malformed ``--gunicorn-port`` is a usage error, not a failure."""
    result = _install_dry_run(root, etc, tmp_path, "--gunicorn-port", "80")
    assert result.returncode == 2


def test_the_install_waits_on_the_chosen_gunicorn_port(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The readiness check asks gunicorn on the port ``--gunicorn-port`` names."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--gunicorn-port", GUNICORN_PORT))
    assert (
        "curl -sI -H 'Host: caldart.test' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8101/"
        in commands
    )


def test_the_install_waits_on_8001_by_default(root: Path, etc: Path, tmp_path: Path) -> None:
    """Without ``--gunicorn-port`` the readiness check asks port 8001."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert (
        "curl -sI -H 'Host: caldart.test' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8001/"
        in commands
    )


def test_the_install_renders_the_vhost_for_the_chosen_port(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The vhost is copied with gunicorn's shipped address replaced by the chosen one."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, "--gunicorn-port", GUNICORN_PORT))
    vhost = commands[_position(commands, "/etc/apache2/sites-available/caldart.conf")]
    assert "-e 's#127.0.0.1:8001#127.0.0.1:8101#g'" in vhost


@pytest.mark.parametrize(("source", "how"), GUNICORN_FILES)
def test_a_rendered_file_proxies_to_the_chosen_port(source: str, how: str, root: Path) -> None:
    """Every vhost, snippet, and upstream names gunicorn on the chosen port."""
    assert "127.0.0.1:8101" in _render_with_port(root, source, how, GUNICORN_PORT)


@pytest.mark.parametrize(("source", "how"), GUNICORN_FILES)
def test_a_rendered_file_keeps_no_8001(source: str, how: str, root: Path) -> None:
    """No ``8001`` survives in a file rendered for another port, comments included."""
    assert "8001" not in _render_with_port(root, source, how, GUNICORN_PORT)


@pytest.mark.parametrize(("source", "how"), GUNICORN_FILES)
def test_every_shipped_proxy_file_names_the_default_port(source: str, how: str) -> None:
    """The shipped files name ``127.0.0.1:8001``, which rendering replaces."""
    assert "127.0.0.1:8001" in (DEPLOY_DIR / source).read_text()


def test_configure_writes_the_recorded_gunicorn_port(root: Path, etc: Path) -> None:
    """The environment file carries ``CALDART_GUNICORN_PORT`` from the install record."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    _configure(root, etc, "--email-url", "smtp://x:25")
    assert _variables(etc / "caldart.env")["CALDART_GUNICORN_PORT"] == "8101"


def test_configure_writes_8001_by_default(env_file: Path) -> None:
    """With no gunicorn port recorded, the environment file names 8001."""
    assert _variables(env_file)["CALDART_GUNICORN_PORT"] == "8001"


def test_configure_moves_the_port_in_an_existing_file(
    env_file: Path, root: Path, etc: Path
) -> None:
    """A changed port in the record reaches a file that exists already."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    _configure(root, etc)
    assert _variables(env_file)["CALDART_GUNICORN_PORT"] == "8101"


def test_configure_moves_the_port_and_nothing_else(env_file: Path, root: Path, etc: Path) -> None:
    """Moving the port rewrites that one line and keeps every other one."""
    before = env_file.read_text()
    (etc / "install.conf").write_text(MOVED_RECORD)
    _configure(root, etc)
    expected = before.replace("CALDART_GUNICORN_PORT=8001\n", "CALDART_GUNICORN_PORT=8101\n")
    assert env_file.read_text() == expected


def test_configure_adds_the_port_to_a_file_without_it(root: Path, etc: Path) -> None:
    """An environment file written before the variable existed gains the line."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    (etc / "caldart.env").write_text("SECRET_KEY=x\n")
    _configure(root, etc)
    assert (etc / "caldart.env").read_text() == "SECRET_KEY=x\nCALDART_GUNICORN_PORT=8101\n"


def test_configure_keeps_the_file_mode_when_it_moves_the_port(
    env_file: Path, root: Path, etc: Path
) -> None:
    """The rewritten environment file stays readable by its owner and group only."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    _configure(root, etc)
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o640


def test_a_taken_gunicorn_port_stops_the_first_start(root: Path, etc: Path, tmp_path: Path) -> None:
    """Before the unit is installed, a listener on the gunicorn port stops the step."""
    result = _web_service(root, etc, tmp_path, installed=False, listening=(8001,))
    assert _errors(result) == [
        "error: port 8001 is already in use on this machine; "
        "run install.sh --gunicorn-port PORT to put gunicorn on another port"
    ]


def test_a_taken_gunicorn_port_fails_the_install(root: Path, etc: Path, tmp_path: Path) -> None:
    """The taken-port refusal is a failure, exit 1, before the unit is installed."""
    result = _install_dry_run(root, etc, tmp_path, listening=(8001,))
    assert result.returncode == 1


def test_another_gunicorn_port_avoids_the_taken_one(root: Path, etc: Path, tmp_path: Path) -> None:
    """A listener on 8001 is left alone when ``--gunicorn-port`` names another port."""
    result = _install_dry_run(
        root, etc, tmp_path, "--gunicorn-port", GUNICORN_PORT, listening=(8001,)
    )
    assert result.returncode == 0, result.stderr


def test_an_installed_unit_skips_the_gunicorn_port_check(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """A later run finds gunicorn itself on the port and carries on."""
    result = _web_service(root, etc, tmp_path, installed=True, listening=(8001,))
    assert result.returncode == 0, result.stderr


def _installed_on_8001(etc: Path) -> None:
    """Write the record and environment file of a box with gunicorn on 8001."""
    (etc / "install.conf").write_text(
        "CALDART_HOSTNAME=caldart.test\nCALDART_TLS=self-signed\nCALDART_GUNICORN_PORT=8001\n"
    )
    (etc / "caldart.env").write_text("SECRET_KEY=x\nCALDART_GUNICORN_PORT=8001\n")


@pytest.mark.parametrize(
    ("earlier", "later"),
    [
        ("install -m 0640 /dev/stdin {etc}/caldart.env", "systemctl restart caldart-web"),
        ("systemctl restart caldart-web", "systemctl reload-or-restart apache2"),
    ],
    ids=["environment-then-service", "service-then-web-server"],
)
def test_moving_the_gunicorn_port_rewrites_restarts_and_reloads_in_order(
    earlier: str, later: str, root: Path, etc: Path, tmp_path: Path
) -> None:
    """The environment file, then gunicorn, then the web server take the new port."""
    _installed_on_8001(etc)
    commands = _commands(
        _install_dry_run(
            root, etc, tmp_path, "--gunicorn-port", GUNICORN_PORT, container=True, flags=()
        )
    )
    first = _position(commands, earlier.format(etc=etc))
    assert first < _position(commands, later)


def test_upgrade_keeps_the_recorded_gunicorn_port(git_checkout: Path, etc: Path) -> None:
    """The upgrade's readiness check asks gunicorn on the port the record names."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    assert _position(_commands(result), "http://127.0.0.1:8101/") >= 0


#: An install record that moved both gunicorn and Postgres off their defaults.
MOVED_PORTS_RECORD: Final = f"{MOVED_RECORD}CALDART_DB_PORT=5433\n"


def test_upgrade_probes_gunicorn_on_both_recorded_ports(git_checkout: Path, etc: Path) -> None:
    """With both ports moved, the web service's readiness probe asks gunicorn on 8101."""
    (etc / "install.conf").write_text(MOVED_PORTS_RECORD)
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    commands = _commands(result)
    probe = _position(commands, "http://127.0.0.1:8101/")
    assert probe < _position(commands, "systemctl is-active")


def test_upgrade_runs_docker_compose_with_the_recorded_db_port(
    git_checkout: Path, etc: Path
) -> None:
    """Every ``docker compose`` the upgrade prints runs with ``CALDART_DB_PORT=5433``."""
    (etc / "install.conf").write_text(MOVED_PORTS_RECORD)
    result = _run(
        git_checkout / "deploy" / "upgrade.sh", "--dry-run", env=_env(etc), cwd=git_checkout
    )
    composes = [command for command in _commands(result) if "docker compose" in command]
    assert composes == ["env CALDART_DB_PORT=5433 docker compose ps --format '{{.Health}}' db"]


@pytest.mark.parametrize("flag", ["--gunicorn-port", "--db-port"])
def test_upgrade_takes_no_port_flag(flag: str, etc: Path) -> None:
    """A port flag given to ``upgrade.sh`` is a usage error naming ``install.sh``."""
    result = _run(DEPLOY_DIR / "upgrade.sh", flag, "8101", env=_env(etc))
    assert result.returncode == 2
    assert _errors(result) == [
        f"error: upgrade.sh keeps the recorded ports; run install.sh {flag} PORT to move one"
    ]


def test_bootstrap_passes_the_gunicorn_port_through(tmp_path: Path) -> None:
    """``--gunicorn-port`` takes a value that reaches ``install.sh``."""
    result = _bootstrap_dry_run(tmp_path, "--gunicorn-port", GUNICORN_PORT)
    assert _commands(result)[-1] == (
        f"bash {tmp_path}/srv/caldart/deploy/install.sh --dry-run --gunicorn-port 8101"
    )


def test_the_install_dry_run_names_the_gunicorn_port_line(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The dry run, which never prints the environment file, still names the port line."""
    result = _install_dry_run(root, etc, tmp_path, "--gunicorn-port", GUNICORN_PORT)
    assert "    with CALDART_GUNICORN_PORT=8101" in result.stdout.splitlines()


# -- check.sh and the two ports -----------------------------------------------------


def _check_function(
    root: Path, tmp_path: Path, function: str, *, record: str, curl_status: str = "502"
) -> subprocess.CompletedProcess[str]:
    """Run ``function`` from ``check.sh`` with ``record`` as the install record.

    ``curl`` answers every request with ``curl_status`` and ``docker`` finds no
    container, so the result depends on nothing the machine running the test has.
    """
    shims = tmp_path / "check-shims"
    shims.mkdir()
    (shims / "curl").write_text(f"#!/bin/sh\nprintf 'HTTP/1.1 {curl_status} X\\r\\n'\n")
    (shims / "docker").write_text("#!/bin/sh\nexit 1\n")
    for shim in shims.iterdir():
        shim.chmod(0o755)
    etc = tmp_path / "check-etc"
    etc.mkdir()
    (etc / "install.conf").write_text(record)
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [
            BASH,
            "-c",
            f'set -euo pipefail; source "$1"; load_record; {function}',
            "bash",
            str(_checkout(root) / "deploy" / "steps" / "check.sh"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_env(etc, PATH=f"{shims}:{os.environ['PATH']}"),
    )


def test_the_check_dry_run_asks_gunicorn_on_the_recorded_port(root: Path, etc: Path) -> None:
    """The check asks gunicorn itself on the port the install record names."""
    (etc / "install.conf").write_text(MOVED_RECORD)
    result = _run(_checkout(root) / "deploy" / "steps" / "check.sh", "--dry-run", env=_env(etc))
    assert (
        "curl -sI -H 'Host: caldart.test' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8101/"
        in _commands(result)
    )


def test_the_check_dry_run_asks_gunicorn_on_8001_by_default(root: Path, etc: Path) -> None:
    """With no gunicorn port recorded, the check asks port 8001."""
    (etc / "install.conf").write_text("CALDART_HOSTNAME=caldart.test\n")
    result = _run(_checkout(root) / "deploy" / "steps" / "check.sh", "--dry-run", env=_env(etc))
    assert (
        "curl -sI -H 'Host: caldart.test' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8001/"
        in _commands(result)
    )


def test_a_gunicorn_that_does_not_answer_fails_the_check(root: Path, tmp_path: Path) -> None:
    """The check names the port gunicorn did not answer 200 on."""
    result = _check_function(root, tmp_path, "check_gunicorn", record=MOVED_RECORD)
    assert _errors(result) == ["error: check failed: gunicorn did not answer 200 on 127.0.0.1:8101"]


def test_a_gunicorn_that_answers_passes_the_check(root: Path, tmp_path: Path) -> None:
    """A ``200`` from gunicorn on the recorded port is no failure."""
    result = _check_function(
        root, tmp_path, "check_gunicorn", record=MOVED_RECORD, curl_status="200"
    )
    assert _errors(result) == []


def test_an_unhealthy_database_check_names_the_port(root: Path, tmp_path: Path) -> None:
    """The database check's failure names the port the record publishes Postgres on."""
    result = _check_function(
        root,
        tmp_path,
        "check_database",
        record="CALDART_HOSTNAME=caldart.test\nCALDART_DB_PORT=5433\n",
    )
    assert _errors(result) == [
        "error: check failed: the compose db service on 127.0.0.1:5433 is not healthy (not running)"
    ]


def test_a_first_install_creates_the_service_user_with_its_own_home(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The user step gives ``caldart`` its own ``/home/caldart``, never the checkout."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert (
        "useradd --system --create-home --home-dir /home/caldart --shell /usr/sbin/nologin caldart"
    ) in commands
    assert not any(command.startswith("usermod ") for command in commands)


def test_an_existing_user_homed_at_the_checkout_is_moved_to_its_own_home(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """A user an earlier install homed at the checkout is pointed at ``/home/caldart``."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, service_home=str(_checkout(root))))
    assert not any(command.startswith("useradd ") for command in commands)
    assert "install -d -o caldart -g caldart -m 0750 /home/caldart" in commands
    assert "usermod --home /home/caldart caldart" in commands


def test_a_user_already_homed_at_its_own_directory_is_left_alone(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """A second run neither recreates the user nor moves a home that is already right."""
    commands = _commands(_install_dry_run(root, etc, tmp_path, service_home="/home/caldart"))
    assert not any(command.startswith(("useradd ", "usermod ")) for command in commands)


def test_the_other_web_server_running_is_a_note_not_a_refusal(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """With both servers active, the step names the one it configures and carries on."""
    result = _install_dry_run(root, etc, tmp_path, active=("apache2", "nginx"))
    assert result.returncode == 0
    assert (
        "nginx is running too; CalDART configures apache2 only, "
        "and both cannot hold ports 80 and 443\n"
    ) in result.stderr


def test_behind_an_existing_site_the_other_web_server_is_not_mentioned(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """With ``--tls existing`` CalDART holds no port, so a second server draws no note."""
    result = _install_dry_run(
        root,
        etc,
        tmp_path,
        "--tls",
        "existing",
        "--web-server",
        "nginx",
        active=("apache2", "nginx"),
    )
    assert result.returncode == 0
    assert "is running too" not in result.stderr


# -- the layout: the checkout inside the deploy root, the data beside it ------------


def test_the_user_step_creates_the_data_in_the_deploy_root(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The dumps and uploads go in the deploy root and the static files in the checkout.

    All three are owned by the service user.
    """
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert (
        f"install -d -o caldart -g caldart {root}/backups {root}/media "
        f"{_checkout(root)}/backend/staticfiles"
    ) in commands


def test_the_install_record_names_the_deploy_root(root: Path) -> None:
    """``CALDART_ROOT`` in ``install.conf`` is the checkout's parent, not the checkout."""
    result = _source_lib(root, "write_file() { cat; }; write_record")
    assert f"CALDART_ROOT={root}" in result.stdout.splitlines()


def test_a_recorded_root_does_not_move_the_checkout(root: Path) -> None:
    """``load_record`` never reads ``CALDART_ROOT``.

    The scripts find the checkout from their own location.
    """
    (root / "install.conf").write_text("CALDART_ROOT=/elsewhere\n")
    result = _source_lib(root, 'load_record; printf "%s %s" "$ROOT" "$CHECKOUT"')
    assert result.stdout == f"{root} {_checkout(root)}"


def test_bootstrap_creates_the_deploy_root_and_clones_into_it(tmp_path: Path) -> None:
    """A fresh server gets the deploy root, then the checkout at ``caldart/`` in it."""
    commands = _commands(_bootstrap_dry_run(tmp_path))
    assert commands[:2] == [
        f"install -d {tmp_path}/srv",
        f"git clone /nowhere {tmp_path}/srv/caldart",
    ]


def test_bootstrap_keeps_the_data_of_an_earlier_install(tmp_path: Path) -> None:
    """A deploy root that already holds ``backups/`` and ``media/`` is cloned into."""
    for name in ("backups", "media"):
        (tmp_path / "srv" / name).mkdir(parents=True)
        (tmp_path / "srv" / name / "kept").write_text("kept\n")
    result = _bootstrap_dry_run(tmp_path)
    assert f"git clone /nowhere {tmp_path}/srv/caldart" in _commands(result)


def test_bootstrap_refuses_a_checkout_directory_that_is_not_a_checkout(tmp_path: Path) -> None:
    """Something other than a checkout at ``caldart/`` stops the bootstrap, naming it."""
    (tmp_path / "srv" / "caldart").mkdir(parents=True)
    (tmp_path / "srv" / "caldart" / "stray").write_text("stray\n")
    result = _bootstrap_dry_run(tmp_path)
    assert _errors(result) == [
        f"error: {tmp_path}/srv/caldart exists and is not a checkout; move it aside first"
    ]


def test_the_dry_run_names_the_code_in_the_checkout_and_the_data_beside_it(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """The install's rendering writes the checkout, then the deploy root, into a file."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    render = commands[_position(commands, "caldart-web.service")]
    assert render.startswith(
        f"sed -e 's#/opt/caldart/caldart#__CALDART_CHECKOUT__#g' -e 's#/opt/caldart#{root}#g' "
        f"-e 's#__CALDART_CHECKOUT__#{_checkout(root)}#g'"
    )


def test_the_user_step_opens_every_media_directory_to_the_web_server(
    root: Path, etc: Path, tmp_path: Path
) -> None:
    """Each install makes every directory under ``media/`` ``0755`` for the web server."""
    commands = _commands(_install_dry_run(root, etc, tmp_path))
    assert f"find {root}/media -type d -exec chmod 0755 '{{}}' +" in commands
    assert f"find {root}/media -type f -exec chmod 0644 '{{}}' +" in commands
