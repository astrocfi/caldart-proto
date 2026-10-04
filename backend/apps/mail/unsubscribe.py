"""The unsubscribe link in a bulk email, and the headers and footer that carry it.

Every copy of a bulk email whose type allows opting out carries a link, signed for its
recipient and its type, that turns that one type off without signing in:
:func:`unsubscribe_url` builds it on ``SITE_URL`` and :func:`read_token` reads it back.
The token is ``django.core.signing`` with the salt ``mail.unsubscribe`` over the
account's id and the type's id, and expires after ``UNSUBSCRIBE_TOKEN_MAX_AGE``
seconds.

:func:`headers_for` gives the copy the ``List-Unsubscribe`` and
``List-Unsubscribe-Post`` headers mail programs read for their own unsubscribe button
(RFC 2369 and RFC 8058), and :func:`footer_for` the line the copy's footer shows.  A
type that does not allow opting out gets no headers, and a footer saying why the
recipient receives it.  Transactional mail never passes through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from django.conf import settings
from django.core import signing

from apps.accounts.models import User
from apps.mail.models import EmailType
from caldart.mail import contact_email, org_name

#: Keeps an unsubscribe token from being read as any other signed value.
UNSUBSCRIBE_SALT = "mail.unsubscribe"

#: The unsubscribe page's path, before the token, below the site's own root.
UNSUBSCRIBE_PATH = "/mail/unsubscribe/"


class UnsubscribeLinkError(Exception):
    """An unsubscribe token that was tampered with, has expired, or names nobody.

    The message is for the log; the page the visitor sees says only that the link no
    longer works.
    """


@dataclass(frozen=True)
class Footer:
    """The footer line of one bulk email copy.

    ``text`` is the sentence the footer shows.  ``url`` is the unsubscribe link that
    follows it, or ``""`` for a type that does not allow opting out, whose ``text``
    says why the recipient receives it instead.
    """

    text: str
    url: str


def make_token(user: User, email_type: EmailType) -> str:
    """A signed, timestamped token that names ``user`` and ``email_type``."""
    return signing.dumps({"u": user.pk, "t": email_type.pk}, salt=UNSUBSCRIBE_SALT)


def read_token(token: str) -> tuple[User, EmailType]:
    """The account and the type ``token`` names.

    Raises :class:`UnsubscribeLinkError` when the signature does not match, when the
    token is older than ``UNSUBSCRIBE_TOKEN_MAX_AGE`` seconds, when its payload is not
    the shape :func:`make_token` writes, or when the account or the type it names has
    since been deleted.
    """
    try:
        payload = signing.loads(
            token, salt=UNSUBSCRIBE_SALT, max_age=settings.UNSUBSCRIBE_TOKEN_MAX_AGE
        )
    except signing.SignatureExpired as error:
        raise UnsubscribeLinkError("The unsubscribe token has expired.") from error
    except signing.BadSignature as error:
        raise UnsubscribeLinkError("The unsubscribe token is not one this site signed.") from error
    if not isinstance(payload, dict):
        raise UnsubscribeLinkError("The unsubscribe token carries no account and type.")
    user_id = payload.get("u")
    type_id = payload.get("t")
    if not isinstance(user_id, int) or not isinstance(type_id, int):
        raise UnsubscribeLinkError("The unsubscribe token carries no account and type.")
    user = User.objects.filter(pk=user_id).first()
    email_type = EmailType.objects.filter(pk=type_id).first()
    if user is None or email_type is None:
        raise UnsubscribeLinkError("The unsubscribe token names an account or type now gone.")
    return user, email_type


def unsubscribe_url(user: User, email_type: EmailType) -> str:
    """The absolute link that turns ``email_type`` off for ``user``.

    Built on ``SITE_URL``, which carries the path the site is served under, with the
    unsubscribe page's own path after it: ``<SITE_URL>/mail/unsubscribe/<token>``.  A host
    with non-ASCII letters is given in its IDNA form (``xn--...``), so the link can sit in
    a mail header, which must be ASCII.
    """
    parts = urlsplit(settings.SITE_URL.rstrip("/"))
    site = urlunsplit(parts._replace(netloc=_ascii_host(parts.netloc)))
    return f"{site}{UNSUBSCRIBE_PATH}{make_token(user, email_type)}"


def _ascii_host(host: str) -> str:
    """``host`` (a domain, with or without a ``:port``) with each label in its IDNA form.

    An ASCII host comes back unchanged; ``caldärt.example.org`` becomes
    ``xn--caldrt-eua.example.org``.
    """
    return host.encode("idna").decode("ascii")


def headers_for(user: User, email_type: EmailType) -> dict[str, str]:
    """The unsubscribe headers for ``user``'s copy of an email of ``email_type``.

    For a type that allows opting out: ``List-Unsubscribe`` holding the HTTPS link from
    :func:`unsubscribe_url` and, when the site's contact address is set, a ``mailto:``
    to it with the subject ``unsubscribe`` (its domain in IDNA form, like the link's
    host); and ``List-Unsubscribe-Post: List-Unsubscribe=One-Click``, which tells a mail
    program it may POST to the link without showing the page.  For a type that does not,
    an empty dictionary.
    """
    if not email_type.allow_opt_out:
        return {}
    targets = [f"<{unsubscribe_url(user, email_type)}>"]
    address = contact_email()
    if address:
        local, _, domain = address.rpartition("@")
        mailbox = f"{quote(local)}@{_ascii_host(domain)}"
        targets.append(f"<mailto:{mailbox}?subject=unsubscribe>")
    return {
        "List-Unsubscribe": ", ".join(targets),
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def footer_for(user: User, email_type: EmailType) -> Footer:
    """The footer line of ``user``'s copy of an email of ``email_type``.

    For a type that allows opting out: *You receive <type> email from <organization>
    because you have not turned it off. To stop it, unsubscribe here:* with the link
    from :func:`unsubscribe_url`.  For a type that does not: *<organization> sends
    <type> email to everyone it writes to, so it cannot be turned off.* with no link.
    """
    org = org_name()
    if not email_type.allow_opt_out:
        return Footer(
            text=(
                f"{org} sends {email_type.name} email to everyone it writes to, "
                "so it cannot be turned off."
            ),
            url="",
        )
    return Footer(
        text=(
            f"You receive {email_type.name} email from {org} because you have not "
            "turned it off. To stop it, unsubscribe here:"
        ),
        url=unsubscribe_url(user, email_type),
    )
