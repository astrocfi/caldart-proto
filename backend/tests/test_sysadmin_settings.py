"""Production settings and the shipped deploy configuration.

``caldart.settings.prod`` is never exercised by the rest of the suite, so this
module imports it against a minimal environment and checks the security
posture it promises — and that the four variables with no default really do
fail loudly when they are missing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"

#: The smallest environment a production box can boot with.
MINIMAL_ENV = {
    "SECRET_KEY": "prod-secret-not-a-real-key",
    "ALLOWED_HOSTS": "caldart.example.org,www.caldart.example.org",
    "SITE_URL": "https://caldart.example.org",
    "EMAIL_URL": "smtp://caldart%40example.org:hunter2@smtp.example.org:587",
    "DATABASE_URL": "postgres://caldart:caldart@db.example.org:5432/caldart",
}

#: Everything ``.env`` sets that would otherwise leak into the assertions.
UNSET = [
    "CSRF_TRUSTED_ORIGINS",
    "SECURE_SSL_REDIRECT",
    "SECURE_HSTS_SECONDS",
    "PAYMENTS_MOCK_ENABLED",
    "DJANGO_VITE_MANIFEST_PATH",
    "LOG_LEVEL",
    "ADMIN_EMAILS",
    "DB_CONN_MAX_AGE",
]


def _import_prod():
    """Import ``caldart.settings.prod`` fresh, however it was left."""
    sys.modules.pop("caldart.settings.prod", None)
    return importlib.import_module("caldart.settings.prod")


@pytest.fixture
def prod_env(monkeypatch):
    """A minimal production environment; the module is not imported yet."""
    for key, value in MINIMAL_ENV.items():
        monkeypatch.setenv(key, value)
    for key in UNSET:
        monkeypatch.delenv(key, raising=False)
    yield
    sys.modules.pop("caldart.settings.prod", None)


@pytest.fixture
def prod(prod_env):
    """The imported production settings module."""
    return _import_prod()


# ------------------------------------------------------------------- import
def test_prod_settings_import_cleanly(prod):
    assert prod.DEBUG is False
    assert prod.SECRET_KEY == MINIMAL_ENV["SECRET_KEY"]
    assert prod.ALLOWED_HOSTS == ["caldart.example.org", "www.caldart.example.org"]
    assert prod.SITE_URL == "https://caldart.example.org"
    assert prod.CSRF_TRUSTED_ORIGINS == ["https://caldart.example.org"]
    assert prod.WAGTAILADMIN_BASE_URL == prod.SITE_URL


@pytest.mark.parametrize("variable", ["SECRET_KEY", "ALLOWED_HOSTS", "SITE_URL", "EMAIL_URL"])
def test_the_required_variables_have_no_default(prod_env, monkeypatch, variable):
    monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ImproperlyConfigured):
        _import_prod()


# ----------------------------------------------------------------- security
def test_tls_is_enforced_behind_the_proxy(prod):
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS == 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"


def test_cookies_are_secure_but_the_csrf_token_stays_readable(prod):
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.CSRF_COOKIE_SECURE is True
    # The SPA reads this one from JavaScript and echoes it as X-CSRFToken.
    assert prod.CSRF_COOKIE_HTTPONLY is False


def test_framing_is_same_origin_so_wagtail_previews_work(prod):
    assert prod.X_FRAME_OPTIONS == "SAMEORIGIN"


def test_hsts_can_be_disabled_for_a_first_deploy(prod_env, monkeypatch):
    monkeypatch.setenv("SECURE_HSTS_SECONDS", "0")

    assert _import_prod().SECURE_HSTS_SECONDS == 0


def test_mock_payments_are_off_by_default(prod):
    assert prod.PAYMENTS_MOCK_ENABLED is False


# ------------------------------------------------------- assets and email
def test_static_files_use_the_hashed_manifest_storage(prod):
    backend = prod.STORAGES["staticfiles"]["BACKEND"]
    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"


def test_vite_reads_the_built_manifest(prod):
    assert prod.VITE_DEV_MODE is False
    assert prod.DJANGO_VITE["default"]["dev_mode"] is False
    assert prod.DJANGO_VITE["default"]["manifest_path"].endswith("manifest.json")


def test_email_comes_from_email_url(prod):
    assert prod.EMAIL_HOST == "smtp.example.org"
    assert prod.EMAIL_PORT == 587
    assert prod.EMAIL_HOST_USER == "caldart@example.org"


def test_logging_goes_to_the_console(prod):
    assert prod.LOGGING["root"]["handlers"] == ["console"]
    assert prod.LOGGING["root"]["level"] == "INFO"
    assert "mail_admins" in prod.LOGGING["loggers"]["django.request"]["handlers"]


def test_database_connections_are_reused(prod):
    assert prod.DATABASES["default"]["CONN_MAX_AGE"] == 60
    assert prod.DATABASES["default"]["CONN_HEALTH_CHECKS"] is True


def test_importing_prod_does_not_disturb_the_running_settings(prod, settings):
    """``prod.py`` copies the dicts it edits rather than mutating base's."""
    from caldart.settings import base

    # Django itself fills CONN_MAX_AGE in with its 0 default; what must not
    # happen is prod's 60 leaking back into the settings the suite runs under.
    assert base.DATABASES["default"].get("CONN_MAX_AGE") != 60
    assert settings.DATABASES["default"].get("CONN_MAX_AGE") != 60
    assert "mail_admins" not in base.LOGGING["handlers"]
    assert settings.DEBUG is False
    assert settings.LOGGING["root"]["level"] == "ERROR"


# ------------------------------------------------------------------- deploy
def test_gunicorn_binds_to_loopback_only():
    config = (DEPLOY / "gunicorn.conf.py").read_text()

    assert 'bind = "127.0.0.1:8001"' in config
    assert 'forwarded_allow_ips = "127.0.0.1"' in config
    assert "multiprocessing.cpu_count()" in config


def test_gunicorn_worker_count_is_capped(monkeypatch):
    """Every worker preloads Django, so the 2n+1 heuristic needs a ceiling."""
    import runpy

    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    config = runpy.run_path(str(DEPLOY / "gunicorn.conf.py"))
    assert 1 <= config["workers"] <= config["MAX_WORKERS"]

    monkeypatch.setenv("WEB_CONCURRENCY", "3")
    assert runpy.run_path(str(DEPLOY / "gunicorn.conf.py"))["workers"] == 3


def test_apache_proxies_to_gunicorn_and_sets_the_scheme_header():
    config = (DEPLOY / "apache" / "caldart.conf").read_text()

    assert "ProxyPass        / http://127.0.0.1:8001/" in config
    assert 'RequestHeader set X-Forwarded-Proto "https"' in config
    assert "Alias /media/ /srv/caldart/backend/media/" in config
    assert "certbot" in config


def test_nginx_is_shipped_as_the_alternative():
    config = (DEPLOY / "nginx" / "caldart.conf").read_text()

    assert "proxy_pass http://127.0.0.1:8001;" in config
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in config


def test_the_web_unit_runs_gunicorn_from_the_venv():
    unit = (DEPLOY / "systemd" / "caldart-web.service").read_text()

    assert "EnvironmentFile=/etc/caldart/caldart.env" in unit
    assert "ExecStart=/srv/caldart/.venv/bin/gunicorn" in unit
    assert "Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod" in unit
    assert "User=caldart" in unit


def test_the_reminder_timer_runs_daily_at_seven():
    service = (DEPLOY / "systemd" / "caldart-reminders.service").read_text()
    timer = (DEPLOY / "systemd" / "caldart-reminders.timer").read_text()

    assert "manage.py send_renewal_reminders" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-* 07:00:00" in timer
    assert "Persistent=true" in timer
