"""The signed bounce address: the envelope sender that names one email log row.

``caldart.mail.signed_bounce_address`` writes ``BOUNCE_ADDRESS`` with a plus tag of an
email log row's id and a keyed signature over it, and ``signed_log_id`` reads the id
back only from an address carrying a signature the site made.  See
``docs/developer/email.rst``, "Bounces".
"""

from __future__ import annotations

import re

import pytest
from pytest_django import Settings

from caldart.mail import signed_bounce_address, signed_log_id

#: The configured bounce address every test signs.
BOUNCES = "bounces@caldart.example.org"


@pytest.fixture(autouse=True)
def _bounce_address(settings: Settings) -> None:
    """Set ``BOUNCE_ADDRESS`` to :data:`BOUNCES`."""
    settings.BOUNCE_ADDRESS = BOUNCES


def test_the_signed_address_tags_the_bounce_address_with_the_id_and_a_signature() -> None:
    """``<local>+<id>.<16 hex digits>@<domain>``, on the configured address."""
    shape = r"bounces\+42\.[0-9a-f]{16}@caldart\.example\.org"

    assert re.fullmatch(shape, signed_bounce_address(42))


def test_the_signed_address_reads_back_as_its_id() -> None:
    """The id a signed address was made for is the one it answers."""
    assert signed_log_id(signed_bounce_address(42)) == 42


def test_each_id_has_its_own_signature() -> None:
    """Two ids are signed differently, so one row's address says nothing of the next."""
    first = signed_bounce_address(42).split(".")[1]
    second = signed_bounce_address(43).split(".")[1]

    assert first != second


def test_the_signed_address_ignores_case() -> None:
    """A mail server that folds the address to capitals still reads as the same id."""
    assert signed_log_id(signed_bounce_address(42).upper()) == 42


def test_the_signed_local_part_fits_an_address() -> None:
    """A twelve-digit id still leaves the local part within 64 characters."""
    local = signed_bounce_address(999_999_999_999).partition("@")[0]

    assert len(local) <= 64


def _with_last_digit_changed(address: str) -> str:
    """``address`` with the last character of its signature changed."""
    local, _at, domain = address.partition("@")
    last = "0" if local[-1] != "0" else "1"
    return f"{local[:-1]}{last}@{domain}"


@pytest.mark.parametrize(
    "address",
    [
        BOUNCES,
        "bounces+42@caldart.example.org",
        "bounces+42.@caldart.example.org",
        "bounces+42.0123456789abcdef@caldart.example.org",
        "",
        "not an address",
    ],
    ids=["bare", "no-signature", "empty-signature", "made-up-signature", "empty", "no-at"],
)
def test_an_address_without_a_valid_signature_reads_as_no_id(address: str) -> None:
    """The bare address, an unsigned tag, and a guessed signature name no row."""
    assert signed_log_id(address) is None


def test_a_changed_signature_reads_as_no_id() -> None:
    """One character of the signature changed and the address names nothing."""
    assert signed_log_id(_with_last_digit_changed(signed_bounce_address(42))) is None


def test_a_signature_moved_to_another_id_reads_as_no_id() -> None:
    """Row 42's signature on row 43's id is no signature for 43."""
    signature = signed_bounce_address(42).split(".", 1)[1].partition("@")[0]

    assert signed_log_id(f"bounces+43.{signature}@caldart.example.org") is None


@pytest.mark.parametrize(
    "change",
    [("bounces+", "other+"), ("@caldart.example.org", "@elsewhere.example.org")],
    ids=["other-local-part", "other-domain"],
)
def test_a_signed_tag_on_another_address_reads_as_no_id(change: tuple[str, str]) -> None:
    """The tag only counts on the configured bounce address itself."""
    assert signed_log_id(signed_bounce_address(42).replace(*change)) is None


def test_an_address_signed_under_another_key_reads_as_no_id(settings: Settings) -> None:
    """A signature made with a secret key the site does not hold is refused."""
    settings.SECRET_KEY = "another-site-key-entirely-" + "x" * 40
    foreign = signed_bounce_address(42)
    settings.SECRET_KEY = "this-site-key-" + "y" * 50

    assert signed_log_id(foreign) is None


def test_an_address_signed_under_a_fallback_key_still_reads(settings: Settings) -> None:
    """A report of mail sent before the key was rotated still names its row."""
    old_key = "the-key-before-rotation-" + "z" * 40
    settings.SECRET_KEY = old_key
    before = signed_bounce_address(42)
    settings.SECRET_KEY = "the-key-after-rotation-" + "w" * 40
    settings.SECRET_KEY_FALLBACKS = [old_key]

    assert signed_log_id(before) == 42


def test_without_a_bounce_address_nothing_reads_as_an_id(settings: Settings) -> None:
    """With ``BOUNCE_ADDRESS`` empty no address names a row, a signed one included."""
    signed = signed_bounce_address(42)
    settings.BOUNCE_ADDRESS = ""

    assert signed_log_id(signed) is None
