"""The types of bulk email, who may send each, and who has turned each one off.

A system administrator keeps the :class:`~apps.mail.models.EmailType` rows through
:func:`create_type`, :func:`update_type` and :func:`delete_type`, each audited.  A
sender is offered :func:`sendable_types`: the types whose ``sender_roles`` name one of
their roles, or every type for a system administrator.

A person's opt-outs are :class:`~apps.mail.models.EmailOptOut` rows: a row means opted
out and no row opted in, so an account starts opted in to every type.
:func:`set_opt_out` records a change from any of the three places it is made (the
person's Email preferences screen, the unsubscribe link, the member record) and audits
it as ``email.opt_out`` or ``email.opt_in`` with its ``source``.  :func:`is_opted_out`
is the question a send asks: an opt-out of a type that no longer allows opting out is
kept but does not apply.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Max, ProtectedError
from django.utils.text import slugify

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import DART_LEADER, MANAGEMENT
from apps.mail.models import EmailOptOut, EmailType, OptOutSource
from caldart import audit
from caldart.exceptions import DomainError, DomainValidationError

#: The roles a type may name as its senders: the roles that reach the bulk email
#: screens.  A system administrator sends every type and is never named.
SENDER_ROLES: tuple[str, ...] = (DART_LEADER, MANAGEMENT)

#: The refusal to delete a type a bulk email names, and what to do instead.
TYPE_IN_USE = (
    "{name} has been used for a bulk email, so it cannot be deleted. To keep DART "
    "leaders and CalDART management from sending it, take their roles off it instead."
)

#: The refusal for a second type whose name, or whose slug, another type holds.
NAME_TAKEN = "Another email type already has this name."

#: The refusal for a name with nothing in it to make a slug from.
NAME_NEEDS_LETTERS = "Use at least one letter or digit in the name."

#: The refusal to rename the Mission type, the one a mission callout goes as.
MISSION_RENAME_REFUSED = (
    "Mission is the type every mission callout goes as, so its name cannot change."
)

#: The refusal to delete the Mission type.
MISSION_DELETE_REFUSED = (
    "Mission is the type every mission callout goes as, so it cannot be deleted."
)

#: The refusal for an opt-out of a type that does not allow one.
OPT_OUT_NOT_ALLOWED = "{name} email cannot be turned off."


@dataclass(frozen=True)
class EmailTypeFields:
    """What a system administrator sets on a type: every column but the slug.

    ``position`` is ``None`` when the caller leaves the order alone: a new type then goes
    after every other, and an edited one keeps its place.
    """

    name: str
    description: str
    allow_opt_out: bool
    sender_roles: list[str]
    position: int | None = None


def list_types() -> list[EmailType]:
    """Every email type, in ``position`` order and then by name."""
    return list(EmailType.objects.all())


@transaction.atomic
def create_type(fields: EmailTypeFields, *, actor: User) -> EmailType:
    """Create a type from ``fields`` and audit it as ``email_type.create``.

    A blank ``position`` puts the type after every existing one.  A name another type
    holds, ignoring case, or one whose slug another type's name shares, raises
    ``DomainValidationError`` on ``name`` with :data:`NAME_TAKEN`, and a name with no
    letter or digit with :data:`NAME_NEEDS_LETTERS`; a role outside
    :data:`SENDER_ROLES` raises it on ``sender_roles``.
    """
    _check(fields, exclude=None)
    position = fields.position
    if position is None:
        highest = EmailType.objects.aggregate(highest=Max("position"))["highest"]
        position = 1 if highest is None else highest + 1
    email_type = EmailType.objects.create(
        name=fields.name,
        description=fields.description,
        allow_opt_out=fields.allow_opt_out,
        sender_roles=_ordered_roles(fields.sender_roles),
        position=position,
    )
    audit.record(audit.EMAIL_TYPE_CREATE, actor=actor, target=email_type)
    return email_type


@transaction.atomic
def update_type(email_type: EmailType, fields: EmailTypeFields, *, actor: User) -> EmailType:
    """Replace ``email_type``'s settings with ``fields`` and audit ``email_type.update``.

    The slug follows the name.  A blank ``position`` keeps the type's place.  Turning
    ``allow_opt_out`` off keeps every recorded opt-out, which applies again once it is
    turned back on.  The refusals are :func:`create_type`'s, with the type itself never
    counted as the other holder of its own name.  The Mission type keeps its name, since
    a mission callout finds it by the slug the name makes: a rename raises
    ``DomainValidationError`` on ``name`` with :data:`MISSION_RENAME_REFUSED`.
    """
    if email_type.is_mission and slugify(fields.name) != email_type.slug:
        raise DomainValidationError("name", MISSION_RENAME_REFUSED)
    _check(fields, exclude=email_type)
    email_type.name = fields.name
    email_type.description = fields.description
    email_type.allow_opt_out = fields.allow_opt_out
    email_type.sender_roles = _ordered_roles(fields.sender_roles)
    if fields.position is not None:
        email_type.position = fields.position
    email_type.save()
    audit.record(audit.EMAIL_TYPE_UPDATE, actor=actor, target=email_type)
    return email_type


def delete_type(email_type: EmailType, *, actor: User) -> None:
    """Delete ``email_type`` and every opt-out of it, auditing ``email_type.delete``.

    A type a bulk email names is protected: the delete raises ``DomainError`` with
    :data:`TYPE_IN_USE` naming the type, deletes nothing, and writes no audit line.  The
    Mission type is never deleted, used or not: the delete raises ``DomainError`` with
    :data:`MISSION_DELETE_REFUSED`.
    """
    if email_type.is_mission:
        raise DomainError(MISSION_DELETE_REFUSED)
    pk = email_type.pk
    try:
        with transaction.atomic():
            email_type.delete()
    except ProtectedError as error:
        raise DomainError(TYPE_IN_USE.format(name=email_type.name)) from error
    audit.record(audit.EMAIL_TYPE_DELETE, actor=actor, target=pk)


def sendable_types(user: User | AnonymousUser) -> list[EmailType]:
    """The types ``user`` may send, in the screens' order.

    A system administrator and a superuser may send every type; anybody else the types
    whose ``sender_roles`` name one of their roles, which is none for an account with
    no sending role and for an anonymous visitor.
    """
    types = list_types()
    return [
        email_type
        for email_type in types
        if user_has_any_role(user, tuple(email_type.sender_roles))
    ]


def opt_out_records(user: User) -> dict[int, EmailOptOut]:
    """Every opt-out ``user`` has recorded, by its type's id, with where and when."""
    return {row.email_type_id: row for row in EmailOptOut.objects.filter(user=user)}


def is_opted_out(user: User, email_type: EmailType) -> bool:
    """True when ``user`` has turned ``email_type`` off and the type allows that.

    An opt-out recorded while the type allowed one does not apply while it does not.
    """
    if not email_type.allow_opt_out:
        return False
    return EmailOptOut.objects.filter(user=user, email_type=email_type).exists()


def opted_out_user_ids(email_type: EmailType) -> frozenset[int]:
    """The ids of every account whose opt-out of ``email_type`` applies now.

    Empty for a type that does not allow opting out, whatever was recorded while it
    did.  One query, so a batch of any size asks once.
    """
    if not email_type.allow_opt_out:
        return frozenset()
    return frozenset(
        EmailOptOut.objects.filter(email_type=email_type).values_list("user_id", flat=True)
    )


def opt_out_types() -> list[EmailType]:
    """The types a person may turn off, in the screens' order."""
    return list(EmailType.objects.filter(allow_opt_out=True))


@transaction.atomic
def set_opt_out(
    user: User,
    email_type: EmailType,
    *,
    opted_out: bool,
    source: OptOutSource,
    actor: User,
) -> bool:
    """Opt ``user`` out of ``email_type``, or back in; True when that changed anything.

    ``opted_out`` true records an opt-out from ``source`` and false removes it.  A real
    change writes one audit line, ``email.opt_out`` or ``email.opt_in``, naming
    ``actor``, the person as the target, the type as ``email_type`` and ``source``;
    asking for the state the person is already in changes nothing and writes nothing.
    A type that does not allow opting out raises ``DomainValidationError`` on
    ``email_type`` with :data:`OPT_OUT_NOT_ALLOWED` naming it, whichever way
    ``opted_out`` points.
    """
    if not email_type.allow_opt_out:
        raise DomainValidationError("email_type", OPT_OUT_NOT_ALLOWED.format(name=email_type.name))
    if opted_out:
        _row, changed = EmailOptOut.objects.get_or_create(
            user=user, email_type=email_type, defaults={"source": source}
        )
    else:
        deleted, _counts = EmailOptOut.objects.filter(user=user, email_type=email_type).delete()
        changed = deleted > 0
    if changed:
        audit.record(
            audit.EMAIL_OPT_OUT if opted_out else audit.EMAIL_OPT_IN,
            actor=actor,
            target=user,
            email_type=email_type.pk,
            source=source.value,
        )
    return changed


def _check(fields: EmailTypeFields, *, exclude: EmailType | None) -> None:
    """Refuse a name another type holds, or a sender role no type may name.

    ``exclude`` is the type being edited, which may keep its own name.  Raises
    ``DomainValidationError`` on ``name`` with :data:`NAME_NEEDS_LETTERS` or
    :data:`NAME_TAKEN`, or on
    ``sender_roles`` naming the role.
    """
    others = EmailType.objects.all()
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    slug = slugify(fields.name)
    if not slug:
        raise DomainValidationError("name", NAME_NEEDS_LETTERS)
    if others.filter(name__iexact=fields.name).exists() or others.filter(slug=slug).exists():
        raise DomainValidationError("name", NAME_TAKEN)
    for role in fields.sender_roles:
        if role not in SENDER_ROLES:
            raise DomainValidationError("sender_roles", f"{role} cannot send bulk email.")


def _ordered_roles(roles: Iterable[str]) -> list[str]:
    """``roles`` once each, in :data:`SENDER_ROLES` order."""
    held = set(roles)
    return [role for role in SENDER_ROLES if role in held]
