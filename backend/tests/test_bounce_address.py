"""The signed bounce address: the envelope sender that names one email log row.

``caldart.mail.signed_bounce_address`` writes ``BOUNCE_ADDRESS`` with a plus tag of an
email log row's id and a keyed signature over the id and the row's ``Message-ID``;
``bounce_tag`` reads the tag back, and ``bounce_tag_matches`` says whether its
signature was made for a given ``Message-ID``.  The system check
``apps.mail.checks.check_bounce_address`` refuses a setting the address cannot be made
from.  See ``docs/developer/email.rst``, "Bounces".
"""

from __future__ import annotations

import re

import pytest
from django.core import checks
from pytest_django import Settings

from apps.mail.checks import LOCAL_PART_TOO_LONG_ID, NOT_BARE_ID, check_bounce_address
from caldart.mail import (
    BOUNCE_LOCAL_PART_MAX_LENGTH,
    BounceTag,
    bounce_tag,
    bounce_tag_matches,
    signed_bounce_address,
)

#: The configured bounce address every test signs.
BOUNCES = "bounces@caldart.example.org"

#: The ``Message-ID`` of the row every test signs for.
MESSAGE_ID = "<175.42.1@caldart.example.org>"

#: The largest id a signed bounce address carries: 18 digits.
LARGEST_ID = 999_999_999_999_999_999


@pytest.fixture(autouse=True)
def _bounce_address(settings: Settings) -> None:
    """Set ``BOUNCE_ADDRESS`` to :data:`BOUNCES`."""
    settings.BOUNCE_ADDRESS = BOUNCES


def _signature(address: str) -> str:
    """The signature digits of the signed ``address``."""
    return address.partition("@")[0].rpartition(".")[2]


def _verifies(address: str, message_id: str = MESSAGE_ID) -> bool:
    """Whether ``address`` reads as a tag signed for ``message_id``."""
    tag = bounce_tag(address)
    return tag is not None and bounce_tag_matches(tag, message_id)


def test_the_signed_address_tags_the_bounce_address_with_the_id_and_a_signature() -> None:
    """``<local>+<id>.<16 hex digits>@<domain>``, on the configured address."""
    shape = r"bounces\+42\.[0-9a-f]{16}@caldart\.example\.org"

    assert re.fullmatch(shape, signed_bounce_address(42, MESSAGE_ID))


def test_the_tag_reads_back_as_its_id_and_signature() -> None:
    """The tag names the id it was made for, and the signature it carries."""
    address = signed_bounce_address(42, MESSAGE_ID)

    assert bounce_tag(address) == BounceTag(log_id=42, signature=_signature(address))


def test_the_signature_matches_the_message_id_it_was_made_for() -> None:
    """The row's own ``Message-ID`` verifies the tag."""
    assert _verifies(signed_bounce_address(42, MESSAGE_ID))


def test_the_signature_does_not_match_another_message_id() -> None:
    """The same id signed for one message does not verify for another."""
    address = signed_bounce_address(42, MESSAGE_ID)

    assert not _verifies(address, "<another@caldart.example.org>")


def test_each_id_has_its_own_signature() -> None:
    """Two ids are signed differently, so one row's address says nothing of the next."""
    first = _signature(signed_bounce_address(42, MESSAGE_ID))
    second = _signature(signed_bounce_address(43, MESSAGE_ID))

    assert first != second


def test_the_signed_address_ignores_case() -> None:
    """A mail server that folds the address to capitals still verifies."""
    assert _verifies(signed_bounce_address(42, MESSAGE_ID).upper())


def test_the_largest_id_on_the_longest_local_part_fits_an_address(settings: Settings) -> None:
    """An 18-digit id on a 28-character local part leaves the local part at 64."""
    settings.BOUNCE_ADDRESS = f"{'b' * BOUNCE_LOCAL_PART_MAX_LENGTH}@caldart.example.org"

    local = signed_bounce_address(LARGEST_ID, MESSAGE_ID).partition("@")[0]

    assert len(local) == 64


def test_the_largest_id_reads_back() -> None:
    """An 18-digit id is read back whole."""
    tag = bounce_tag(signed_bounce_address(LARGEST_ID, MESSAGE_ID))

    assert tag is not None
    assert tag.log_id == LARGEST_ID


def test_a_display_name_on_the_setting_is_left_out_of_the_address(settings: Settings) -> None:
    """``Name <bounces@...>`` signs the bare address, which still reads back."""
    settings.BOUNCE_ADDRESS = f"CalDART bounces <{BOUNCES}>"

    address = signed_bounce_address(42, MESSAGE_ID)

    assert re.fullmatch(r"bounces\+42\.[0-9a-f]{16}@caldart\.example\.org", address)


def test_a_display_name_on_the_setting_still_verifies(settings: Settings) -> None:
    """The tag on the bare address is read against the bare form of the setting."""
    settings.BOUNCE_ADDRESS = f"CalDART bounces <{BOUNCES}>"

    assert _verifies(signed_bounce_address(42, MESSAGE_ID))


@pytest.mark.parametrize(
    "address",
    [
        BOUNCES,
        "bounces+42@caldart.example.org",
        "bounces+42.@caldart.example.org",
        "bounces+0.0123456789abcdef@caldart.example.org",
        "bounces+1234567890123456789.0123456789abcdef@caldart.example.org",
        "",
        "not an address",
    ],
    ids=["bare", "no-signature", "empty-signature", "zero-id", "19-digit-id", "empty", "no-at"],
)
def test_an_address_without_a_signed_tag_reads_as_no_tag(address: str) -> None:
    """The bare address, an unsigned tag, and an id out of range carry no tag."""
    assert bounce_tag(address) is None


def test_a_made_up_signature_does_not_verify() -> None:
    """A well-shaped tag the site did not sign reads, but does not match."""
    assert not _verifies("bounces+42.0123456789abcdef@caldart.example.org")


def test_a_signature_moved_to_another_id_does_not_verify() -> None:
    """Row 42's signature on row 43's id is no signature for 43."""
    signature = _signature(signed_bounce_address(42, MESSAGE_ID))

    assert not _verifies(f"bounces+43.{signature}@caldart.example.org")


@pytest.mark.parametrize(
    "change",
    [("bounces+", "other+"), ("@caldart.example.org", "@elsewhere.example.org")],
    ids=["other-local-part", "other-domain"],
)
def test_a_signed_tag_on_another_address_reads_as_no_tag(change: tuple[str, str]) -> None:
    """The tag only counts on the configured bounce address itself."""
    assert bounce_tag(signed_bounce_address(42, MESSAGE_ID).replace(*change)) is None


def test_an_address_signed_under_another_key_does_not_verify(settings: Settings) -> None:
    """A signature made with a secret key the site does not hold is refused."""
    settings.SECRET_KEY = "another-site-key-entirely-" + "x" * 40
    foreign = signed_bounce_address(42, MESSAGE_ID)
    settings.SECRET_KEY = "this-site-key-" + "y" * 50

    assert not _verifies(foreign)


def test_an_address_signed_under_a_fallback_key_still_verifies(settings: Settings) -> None:
    """A report of mail sent before the key was rotated still names its row."""
    old_key = "the-key-before-rotation-" + "z" * 40
    settings.SECRET_KEY = old_key
    before = signed_bounce_address(42, MESSAGE_ID)
    settings.SECRET_KEY = "the-key-after-rotation-" + "w" * 40
    settings.SECRET_KEY_FALLBACKS = [old_key]

    assert _verifies(before)


def test_without_a_bounce_address_nothing_reads_as_a_tag(settings: Settings) -> None:
    """With ``BOUNCE_ADDRESS`` empty no address carries a tag, a signed one included."""
    signed = signed_bounce_address(42, MESSAGE_ID)
    settings.BOUNCE_ADDRESS = ""

    assert bounce_tag(signed) is None


# --------------------------------------------------------------------------
# The system check
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "configured",
    ["", BOUNCES, f"{'b' * BOUNCE_LOCAL_PART_MAX_LENGTH}@caldart.example.org"],
    ids=["unset", "bare", "longest-local-part"],
)
def test_the_check_passes_an_unset_or_usable_bounce_address(
    configured: str, settings: Settings
) -> None:
    """No setting, a bare address, and a 28-character local part raise nothing."""
    settings.BOUNCE_ADDRESS = configured

    assert check_bounce_address() == []


@pytest.mark.parametrize(
    "configured",
    [
        f"CalDART bounces <{BOUNCES}>",
        f"<{BOUNCES}>",
        "bounces",
        "@caldart.example.org",
        "bounces@",
        "bad bounces@caldart.example.org",
    ],
    ids=["display-name", "angle-brackets", "no-at", "no-local-part", "no-domain", "space"],
)
def test_the_check_refuses_an_address_that_is_not_bare(configured: str, settings: Settings) -> None:
    """Anything but ``local@domain`` is error ``mail.E001``."""
    settings.BOUNCE_ADDRESS = configured

    assert [message.id for message in check_bounce_address()] == [NOT_BARE_ID]


def test_the_check_refuses_a_local_part_with_no_room_for_the_tag(settings: Settings) -> None:
    """A 29-character local part is error ``mail.E002``."""
    settings.BOUNCE_ADDRESS = f"{'b' * (BOUNCE_LOCAL_PART_MAX_LENGTH + 1)}@caldart.example.org"

    assert [message.id for message in check_bounce_address()] == [LOCAL_PART_TOO_LONG_ID]


def test_the_check_is_registered_with_django(settings: Settings) -> None:
    """``manage.py check`` runs it: the registry's run reports the same error."""
    settings.BOUNCE_ADDRESS = "bounces"

    assert NOT_BARE_ID in [message.id for message in checks.run_checks()]
