"""The audit log: one line per privileged action, on the ``caldart.audit`` logger.

Every administrative action that changes an account, a membership, a backup or
the database writes one record through :func:`record`, and every privileged
attempt that a rule turns away writes one through :func:`refuse` at WARNING.
The logger carries its own level and handler and does not propagate, so
lowering the root level to quiet ordinary chatter never silences the trail.

A record is ids, counts, flags and slugs -- nothing else.  Email addresses,
names, passwords, tokens and database contents are not values the renderer
accepts, so none of them can reach the log by accident: the call raises
``TypeError`` instead.  Where an operator typed the value, such as a backup
file name or a database name, :func:`safe_slug` reduces it to something the
renderer takes.

Every line has the same shape, which is what makes the journal greppable::

    action=account.roles actor=12 target=34 added=dart_leader removed=-

``actor`` is the id of the account that acted, or ``command`` for a management
command and the reminder timer; ``target`` is the id of the account or record
acted on, or ``-`` when the action has none.
"""

from __future__ import annotations

import logging
import re

from django.db.models import Model

#: The logger every audit record goes to.  ``caldart.settings.base.LOGGING``
#: configures it at INFO with ``propagate: False``.
LOGGER_NAME = "caldart.audit"

#: The actor a management command and the reminder timer log under.
COMMAND_ACTOR = "command"

#: What a missing target, an empty list and an empty name render as.
EMPTY = "-"

#: The longest slug a record may carry, so no single value can flood the journal.
MAX_SLUG_LENGTH = 64

#: A value a record may carry verbatim: it starts with a letter or a digit and
#: holds nothing that would break the ``key=value`` shape apart.
SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

#: What :func:`safe_slug` replaces, and what it strips from the front.
UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
LEADING_PUNCTUATION = "._-"
UNNAMED = "unnamed"

# -- the actions ------------------------------------------------------------
ACCOUNT_UPDATE = "account.update"
ACCOUNT_ROLES = "account.roles"
ACCOUNT_ACTIVATE = "account.activate"
ACCOUNT_DEACTIVATE = "account.deactivate"
MEMBER_CREATE = "member.create"
MEMBER_DELETE = "member.delete"
MEMBERSHIP_GRANT = "membership.grant"
MEMBERSHIP_CORRECT = "membership.correct"
PASSWORD_RESET_ADMIN_SENT = "password_reset.admin_sent"
BACKUP_CREATE = "backup.create"
BACKUP_DOWNLOAD = "backup.download"
BACKUP_RESTORE = "backup.restore"
DB_RESET = "db.reset"
REMINDERS_RUN = "reminders.run"

# -- why an attempt was turned away -----------------------------------------
REASON_SELF_DEACTIVATION = "self_deactivation"
REASON_ROLES_NOT_HELD = "roles_not_held"
REASON_SYSTEM_ADMIN_ROLE = "system_admin_role"
REASON_SELF_DELETE = "self_delete"
REASON_SYSTEM_ADMIN_TARGET = "system_admin_target"
REASON_HAS_PAYMENTS = "has_payments"
REASON_INACTIVE_ACCOUNT = "inactive_account"
REASON_NO_SUCH_BACKUP = "no_such_backup"

log = logging.getLogger(LOGGER_NAME)


def record(
    action: str,
    *,
    actor: Model | str,
    target: Model | int | None = None,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    """Write one audit line for ``action``, at INFO unless ``level`` says otherwise.

    ``actor`` is the account that acted, or the string ``command``; ``target``
    is the account or record acted on, given as a model instance or an id, and
    renders as ``-`` when there is none.  Each keyword in ``fields`` becomes one
    ``key=value`` pair, in the order given, after ``action``, ``actor`` and
    ``target``.

    A field value may be an int, a bool (rendered ``true``/``false``), a slug of
    at most ``MAX_SLUG_LENGTH`` characters, or a list of such slugs (rendered
    comma-separated, and ``-`` when empty).  Anything else raises ``TypeError``
    naming the field, which is what keeps personal data out of the log.  An
    actor that is neither a model instance nor ``command``, and a target that is
    neither a model instance, an int nor ``None``, raise ``TypeError`` too.
    """
    pairs = [
        f"action={_slug('action', action)}",
        f"actor={_actor_id(actor)}",
        f"target={_target_id(target)}",
    ]
    pairs += [f"{name}={_rendered(name, value)}" for name, value in fields.items()]
    log.log(level, " ".join(pairs))


def refuse(
    action: str,
    *,
    actor: Model | str,
    target: Model | int | None = None,
    reason: str,
    **fields: object,
) -> None:
    """Write one WARNING audit line for a privileged attempt a rule turned away.

    ``reason`` is a slug saying which rule refused it, and is the last field on
    the line.  Everything else behaves as :func:`record`.
    """
    record(action, actor=actor, target=target, level=logging.WARNING, **fields, reason=reason)


def safe_slug(value: str) -> str:
    """``value`` reduced to something a record may carry.

    Every character outside a slug becomes ``_``, leading punctuation goes, and
    the result is cut to ``MAX_SLUG_LENGTH``.  A value with nothing left, such
    as ``""`` or ``"///"``, becomes ``unnamed``.  Use it for a file name or a
    database name an operator typed; an id or a slug the application owns needs
    no such treatment.
    """
    cleaned = UNSAFE_RE.sub("_", value).lstrip(LEADING_PUNCTUATION)[:MAX_SLUG_LENGTH]
    return cleaned or UNNAMED


def _actor_id(actor: Model | str) -> str:
    """``actor``'s id, or ``command``."""
    if isinstance(actor, Model):
        return str(actor.pk)
    if actor == COMMAND_ACTOR:
        return COMMAND_ACTOR
    raise TypeError(f"Audit actor takes a model instance or {COMMAND_ACTOR!r}, not {actor!r}.")


def _target_id(target: Model | int | None) -> str:
    """``target``'s id, or ``-`` when the action has no target."""
    if target is None:
        return EMPTY
    if isinstance(target, Model):
        return str(target.pk)
    if isinstance(target, int) and not isinstance(target, bool):
        return str(target)
    raise TypeError(f"Audit target takes a model instance, an int or None, not {target!r}.")


def _rendered(name: str, value: object) -> str:
    """Render ``value`` as it appears after ``name=``.

    A bool renders as ``true`` or ``false``, any other int as its digits, a slug
    verbatim, and a list or tuple of slugs as the slugs joined with commas. An empty
    list or tuple renders as ``-``, never as an empty string.

    Raises the error :func:`_field_error` builds when ``value`` is not an id, a count, a
    flag or a slug (or a list/tuple of slugs).
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if _is_slug(value):
        return str(value)
    if isinstance(value, list | tuple) and all(_is_slug(item) for item in value):
        return ",".join(value) if len(value) > 0 else EMPTY
    raise _field_error(name, value)


def _is_slug(value: object) -> bool:
    """True when ``value`` is a string a record may carry verbatim."""
    return (
        isinstance(value, str)
        and len(value) <= MAX_SLUG_LENGTH
        and SLUG_RE.fullmatch(value) is not None
    )


def _slug(name: str, value: str) -> str:
    """``value`` itself, or ``TypeError`` when it is not a slug."""
    if not _is_slug(value):
        raise _field_error(name, value)
    return value


def _field_error(name: str, value: object) -> TypeError:
    """The refusal every field that is not an id, a count, a flag or a slug gets."""
    return TypeError(
        f"Audit field {name!r} takes an int, a bool, a slug or a list of slugs, not {value!r}."
    )
