"""Translation from an ``EMAIL_URL`` into Django's ``MAILERS`` setting.

Django configures outgoing mail through ``MAILERS``, a dict keyed by mailer alias
whose entries name a ``BACKEND`` and the ``OPTIONS`` its constructor takes.  The
deployment interface stays a single ``EMAIL_URL`` environment variable, which
django-environ parses into one value per connection detail, so the settings modules
hand that result to ``default_mailer`` and store what it returns under ``"default"``.
``docs/developer/configuration.rst`` documents the variable itself.
"""

from typing import Any

from django.core.exceptions import ImproperlyConfigured

CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"
DUMMY_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
FILE_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

#: The ``env.email_url`` keys each backend accepts, mapped to its option names.  Every
#: backend django-environ's ``email_url`` can name has an entry, and one that takes no
#: options has an empty one: passing an option to a backend that does not know it is an
#: error rather than a value it ignores.  A backend outside the table is a backend whose
#: options nothing here has established, so it is rejected rather than configured blind.
OPTIONS_FOR_BACKEND: dict[str, dict[str, str]] = {
    SMTP_BACKEND: {
        "EMAIL_HOST": "host",
        "EMAIL_PORT": "port",
        "EMAIL_HOST_USER": "username",
        "EMAIL_HOST_PASSWORD": "password",
        "EMAIL_USE_TLS": "use_tls",
        "EMAIL_USE_SSL": "use_ssl",
    },
    FILE_BACKEND: {"EMAIL_FILE_PATH": "file_path"},
    CONSOLE_BACKEND: {},
    LOCMEM_BACKEND: {},
    DUMMY_BACKEND: {},
}


def default_mailer(email_url: dict[str, Any], *, timeout: int | None = None) -> dict[str, Any]:
    """Return the ``MAILERS["default"]`` entry an ``EMAIL_URL`` describes.

    ``email_url`` is what django-environ's ``email_url`` returns: an ``EMAIL_BACKEND``
    dotted path plus one key per connection detail the URL carried.  Only the keys the
    named backend accepts become ``OPTIONS``, and a key the URL left empty is dropped
    so the backend's own default applies; a backend that takes no options gets no
    ``OPTIONS`` entry.  ``timeout`` is the SMTP socket timeout in seconds and is
    dropped for any other backend, which has no socket to time out.

    For ``smtp://caldart%40example.org:hunter2@smtp.example.org:587`` the result is
    ``{"BACKEND": SMTP_BACKEND, "OPTIONS": {"host": "smtp.example.org", "port": 587,
    "username": "caldart@example.org", "password": "hunter2"}}``.

    Raises ``ImproperlyConfigured``, naming the backend, when ``EMAIL_BACKEND`` is one
    ``OPTIONS_FOR_BACKEND`` does not list, since which of the URL's values that backend
    accepts is then unknown.
    """
    backend = email_url["EMAIL_BACKEND"]
    try:
        names = OPTIONS_FOR_BACKEND[backend]
    except KeyError as exc:
        known = ", ".join(sorted(OPTIONS_FOR_BACKEND))
        raise ImproperlyConfigured(
            f"EMAIL_URL names the mail backend {backend}, whose options caldart does "
            f"not know. Known backends: {known}."
        ) from exc
    options: dict[str, Any] = {
        option: email_url[key]
        for key, option in names.items()
        if key in email_url and email_url[key] is not None and email_url[key] != ""
    }
    if timeout is not None and backend == SMTP_BACKEND:
        options["timeout"] = timeout

    mailer: dict[str, Any] = {"BACKEND": backend}
    if len(options) > 0:
        mailer["OPTIONS"] = options
    return mailer
