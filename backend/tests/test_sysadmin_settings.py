"""Production settings and the shipped deploy configuration.

``caldart.settings.prod`` is never exercised by the rest of the suite, so this
module imports it against a minimal environment and checks the security
posture it promises -- and that the four variables with no default really do
fail loudly when they are missing.
"""

from __future__ import annotations

import ast
import importlib
import multiprocessing
import re
import runpy
import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured
from pytest_django import Settings

from caldart.settings import base
from tests.conftest import DEPLOY_DIR, REPO_ROOT

PROD_SETTINGS = REPO_ROOT / "backend" / "caldart" / "settings" / "prod.py"

#: The smallest environment a production box can boot with.
MINIMAL_ENV = {
    "SECRET_KEY": "prod-secret-not-a-real-key",
    "ALLOWED_HOSTS": "caldart.example.org,www.caldart.example.org",
    "SITE_URL": "https://caldart.example.org",
    "EMAIL_URL": "smtp://caldart%40example.org:hunter2@smtp.example.org:587",
    "DATABASE_URL": "postgres://caldart:caldart@db.example.org:5432/caldart",
}

#: Every other variable ``prod.py`` reads.  A developer's shell, and the ``.env``
#: the development and test settings load, would otherwise decide the outcome of
#: the assertions below, and a local run would disagree with CI.
#: ``test_unset_names_every_variable_production_reads`` keeps this list exact.
UNSET = [
    "CSRF_TRUSTED_ORIGINS",
    "SECURE_SSL_REDIRECT",
    "SECURE_HSTS_SECONDS",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "DB_CONN_MAX_AGE",
    "EMAIL_TIMEOUT",
    "DJANGO_VITE_MANIFEST_PATH",
    "PAYMENTS_MOCK_ENABLED_IN_PRODUCTION",
    "LOG_LEVEL",
    "ADMIN_EMAILS",
]


def variables_read_by(module_path: Path) -> set[str]:
    """Every environment variable a settings module reads through ``env``.

    Finds the first string argument of every ``env(...)``, ``env.bool(...)``,
    ``env.int(...)``, ``env.list(...)`` and ``env.email_url(...)`` call in the
    module's source, so a variable added to the module cannot be forgotten here.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(module_path.read_text())):
        if not isinstance(node, ast.Call) or len(node.args) == 0:
            continue
        func = node.func
        if isinstance(func, ast.Name):
            reader = func.id
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            reader = func.value.id
        else:
            continue
        first = node.args[0]
        if reader == "env" and isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.add(first.value)
    return names


def import_prod() -> ModuleType:
    """Import ``caldart.settings.prod`` fresh, however it was left."""
    sys.modules.pop("caldart.settings.prod", None)
    return importlib.import_module("caldart.settings.prod")


def apply_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``MINIMAL_ENV`` and clear every other variable ``prod.py`` reads."""
    for key, value in MINIMAL_ENV.items():
        monkeypatch.setenv(key, value)
    for key in UNSET:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def prod_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """A minimal production environment; the module is not imported yet."""
    apply_production_environment(monkeypatch)
    yield
    sys.modules.pop("caldart.settings.prod", None)


@pytest.fixture
def prod(prod_env: None) -> ModuleType:
    """The imported production settings module."""
    return import_prod()


# ------------------------------------------------------------------- import
def test_prod_settings_import_cleanly(prod: ModuleType) -> None:
    """Importing under ``MINIMAL_ENV`` sets DEBUG off and echoes the site identity."""
    assert prod.DEBUG is False
    assert MINIMAL_ENV["SECRET_KEY"] == prod.SECRET_KEY
    assert prod.ALLOWED_HOSTS == ["caldart.example.org", "www.caldart.example.org"]
    assert prod.SITE_URL == "https://caldart.example.org"
    assert prod.CSRF_TRUSTED_ORIGINS == ["https://caldart.example.org"]
    assert prod.WAGTAILADMIN_BASE_URL == prod.SITE_URL


@pytest.mark.parametrize("variable", ["SECRET_KEY", "ALLOWED_HOSTS", "SITE_URL", "EMAIL_URL"])
def test_the_required_variables_have_no_default(
    prod_env: None, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    """Unsetting a required variable raises ``ImproperlyConfigured`` naming it."""
    monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ImproperlyConfigured, match=variable):
        import_prod()


def test_unset_names_every_variable_production_reads() -> None:
    """Anything left set would let the ambient environment decide a result."""
    assert variables_read_by(PROD_SETTINGS) - set(MINIMAL_ENV) == set(UNSET)


# ----------------------------------------------------------------- security
def test_tls_is_enforced_behind_the_proxy(prod: ModuleType) -> None:
    """TLS redirect, HSTS, and the proxy header are all on with a one-year HSTS window."""
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS == 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"


def test_cookies_are_secure_but_the_csrf_token_stays_readable(prod: ModuleType) -> None:
    """Session and CSRF cookies are secure, and only the session cookie is HTTP-only."""
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.CSRF_COOKIE_SECURE is True
    # The SPA reads this one from JavaScript and echoes it as X-CSRFToken.
    assert prod.CSRF_COOKIE_HTTPONLY is False


def test_framing_is_same_origin_so_wagtail_previews_work(prod: ModuleType) -> None:
    """``X_FRAME_OPTIONS`` is ``SAMEORIGIN``, not ``DENY``."""
    assert prod.X_FRAME_OPTIONS == "SAMEORIGIN"


def test_hsts_can_be_disabled_for_a_first_deploy(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting ``SECURE_HSTS_SECONDS=0`` turns HSTS off."""
    monkeypatch.setenv("SECURE_HSTS_SECONDS", "0")

    assert import_prod().SECURE_HSTS_SECONDS == 0


def test_hsts_preload_is_off_unless_it_is_asked_for(prod: ModuleType) -> None:
    """Preloading is a commitment browsers will not let the site take back."""
    assert prod.SECURE_HSTS_PRELOAD is False


def test_hsts_preload_can_be_turned_on(prod_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting ``SECURE_HSTS_PRELOAD=true`` turns preloading on."""
    monkeypatch.setenv("SECURE_HSTS_PRELOAD", "true")

    assert import_prod().SECURE_HSTS_PRELOAD is True


def test_the_preload_deployment_warning_is_silenced_deliberately(prod: ModuleType) -> None:
    """``check --deploy`` reports W021 whenever preload is off; that is the choice."""
    assert prod.SILENCED_SYSTEM_CHECKS == ["security.W021", "security.W019"]


def test_mock_payments_are_off_by_default(prod: ModuleType) -> None:
    """Mock payment providers are disabled by default."""
    assert prod.PAYMENTS_MOCK_ENABLED is False


# ------------------------------------------------------- throttles and cache
def test_one_proxy_sits_in_front_so_throttles_key_on_the_client_address(prod: ModuleType) -> None:
    """DRF otherwise keys on the whole ``X-Forwarded-For``, which a client writes."""
    assert prod.REST_FRAMEWORK["NUM_PROXIES"] == 1


def test_the_base_rest_framework_settings_are_not_mutated(prod: ModuleType) -> None:
    """``prod.py`` adds ``NUM_PROXIES`` to its own copy, leaving base's dict untouched."""
    assert "NUM_PROXIES" not in base.REST_FRAMEWORK


def test_throttle_counters_are_shared_through_the_database(prod: ModuleType) -> None:
    """Every gunicorn worker would otherwise keep a private budget of its own."""
    assert prod.CACHES["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"


def test_the_cache_table_is_the_one_the_deployment_guide_creates(prod: ModuleType) -> None:
    """The cache table name matches the one the deployment guide has the operator make."""
    assert prod.CACHES["default"]["LOCATION"] == "caldart_cache"


# ------------------------------------------------------- assets and email
def test_static_files_use_the_hashed_manifest_storage(prod: ModuleType) -> None:
    """Static files are served through whitenoise's compressed manifest storage."""
    backend = prod.STORAGES["staticfiles"]["BACKEND"]
    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_vite_reads_the_built_manifest(prod: ModuleType) -> None:
    """Vite dev mode is off and the manifest path points at a built ``manifest.json``."""
    assert prod.VITE_DEV_MODE is False
    assert prod.DJANGO_VITE["default"]["dev_mode"] is False
    assert prod.DJANGO_VITE["default"]["manifest_path"].endswith("manifest.json")


def test_email_comes_from_email_url(prod: ModuleType) -> None:
    """``EMAIL_URL`` is parsed into the options of the default mailer."""
    assert prod.MAILERS["default"] == {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": "smtp.example.org",
            "port": 587,
            "username": "caldart@example.org",
            "password": "hunter2",
            "timeout": 20,
        },
    }


def test_logging_goes_to_the_console(prod: ModuleType) -> None:
    """The root logger writes to the console at INFO; request errors also mail admins."""
    assert prod.LOGGING["root"]["handlers"] == ["console"]
    assert prod.LOGGING["root"]["level"] == "INFO"
    assert "mail_admins" in prod.LOGGING["loggers"]["django.request"]["handlers"]


def test_database_connections_are_reused(prod: ModuleType) -> None:
    """Database connections persist for 60 seconds and are health-checked before reuse."""
    assert prod.DATABASES["default"]["CONN_MAX_AGE"] == 60
    assert prod.DATABASES["default"]["CONN_HEALTH_CHECKS"] is True


def test_importing_prod_does_not_disturb_the_running_settings(
    prod: ModuleType, settings: Settings
) -> None:
    """``prod.py`` copies the dicts it edits rather than mutating base's."""
    # Django itself fills CONN_MAX_AGE in with its 0 default; what must not
    # happen is prod's 60 leaking back into the settings the suite runs under.
    assert base.DATABASES["default"].get("CONN_MAX_AGE") != 60
    assert settings.DATABASES["default"].get("CONN_MAX_AGE") != 60
    assert "mail_admins" not in base.LOGGING["handlers"]
    assert settings.DEBUG is False
    assert settings.LOGGING["root"]["level"] == "ERROR"


# ------------------------------------------------------------------- deploy
def test_gunicorn_binds_to_loopback_only() -> None:
    """Gunicorn binds to loopback, trusts the proxy, and sizes workers to the CPU."""
    config = (DEPLOY_DIR / "gunicorn.conf.py").read_text()

    assert 'bind = "127.0.0.1:8001"' in config
    assert 'forwarded_allow_ips = "127.0.0.1"' in config
    assert "multiprocessing.cpu_count()" in config


def test_gunicorn_worker_count_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every worker preloads Django, so the 2n+1 heuristic needs a ceiling."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)

    config = runpy.run_path(str(DEPLOY_DIR / "gunicorn.conf.py"))

    assert config["MAX_WORKERS"] == 12
    assert config["workers"] == min(multiprocessing.cpu_count() * 2 + 1, 12)


def test_web_concurrency_overrides_the_worker_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``WEB_CONCURRENCY`` sets the worker count outright, cap and heuristic aside."""
    monkeypatch.setenv("WEB_CONCURRENCY", "3")

    assert runpy.run_path(str(DEPLOY_DIR / "gunicorn.conf.py"))["workers"] == 3


def test_apache_proxies_to_gunicorn_and_sets_the_scheme_header() -> None:
    """The Apache vhost proxies to gunicorn, forwards HTTPS, and serves media, certbot."""
    config = (DEPLOY_DIR / "apache" / "caldart.conf").read_text()
    # Apache directives are free-form whitespace; collapse runs of spaces and tabs
    # so the assertion below survives realignment of the config's columns.
    normalized = re.sub(r"[ \t]+", " ", config)

    assert "ProxyPass / http://127.0.0.1:8001/" in normalized
    assert 'RequestHeader set X-Forwarded-Proto "https"' in config
    assert "Alias /media/ /srv/caldart/backend/media/" in config
    assert "certbot" in config


def test_nginx_is_shipped_as_the_alternative() -> None:
    """The nginx config proxies to gunicorn and forwards the original scheme."""
    config = (DEPLOY_DIR / "nginx" / "caldart.conf").read_text()

    assert "proxy_pass http://127.0.0.1:8001;" in config
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in config


def test_the_web_unit_runs_gunicorn_from_the_venv() -> None:
    """The systemd web unit runs gunicorn from the venv, under the ``caldart`` user."""
    unit = (DEPLOY_DIR / "systemd" / "caldart-web.service").read_text()

    assert "EnvironmentFile=/etc/caldart/caldart.env" in unit
    assert "ExecStart=/srv/caldart/.venv/bin/gunicorn" in unit
    assert "Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod" in unit
    assert "User=caldart" in unit


def test_the_reminder_timer_runs_daily_at_seven() -> None:
    """The reminder timer fires the daily service at 07:00 and survives a reboot."""
    service = (DEPLOY_DIR / "systemd" / "caldart-reminders.service").read_text()
    timer = (DEPLOY_DIR / "systemd" / "caldart-reminders.timer").read_text()

    assert "manage.py send_renewal_reminders" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-* 07:00:00" in timer
    assert "Persistent=true" in timer
