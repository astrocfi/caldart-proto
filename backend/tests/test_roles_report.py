"""The CalDART roles report: who holds each role other than member.

The report has one section per staff role, least privileged first, each present even
when nobody holds that role, and one row per role an active account holds.  It is read
by user administrators and account administrators (and system administrators), and a
subscription can send it to any of them.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_LABELS,
    ROLE_SLUGS,
    STAFF_ROLE_LABELS,
    SYSTEM_ADMIN,
    TREASURER,
    USER_ADMIN,
    VERIFIER,
    WEBSITE_ADMIN,
)
from apps.darts.models import Dart
from apps.members.models import MembershipPlan
from apps.members.roles_report import ROLES_REPORT, ROLES_REPORT_COLUMNS, RoleRow
from caldart.reports import Params, select_columns
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

REPORTS_URL = "/api/v1/reports"
CSV_URL = "/api/v1/reports/roles/export.csv"
PDF_URL = "/api/v1/reports/roles/export.pdf"
SUBSCRIPTIONS_URL = "/api/v1/reports/subscriptions"

#: The seven staff roles' section titles, in the order the report draws them.
SECTION_TITLES = [
    "Verifier",
    "DART leader",
    "User administrator",
    "Treasurer",
    "Account administrator",
    "Website administrator",
    "System administrator",
]

#: The columns the report carries when the caller chooses none.
DEFAULT_COLUMNS = ("role", "name", "email", "phone", "dart", "kind", "membership")

#: The day the dated rows below are worked out for.
TODAY = date(2026, 9, 26)


def rows_for(params: Params | None = None) -> list[RoleRow]:
    """The rows the report's query answers for ``params``, in order."""
    return list(ROLES_REPORT.query(params or {}).rows)


def pairs(rows: list[RoleRow]) -> list[tuple[str, str]]:
    """Each row as its ``(role label, email)``."""
    return [(row.role_label, row.user.email) for row in rows]


def section_titles(params: Params | None = None) -> list[str]:
    """The titles of the report's sections for ``params``, in order."""
    table = ROLES_REPORT.table(params or {}, fmt="csv", today=TODAY)
    return [section.title for section in table.sections]


# --------------------------------------------------------------------------
# The role labels
# --------------------------------------------------------------------------
def test_every_role_is_labeled_as_the_screens_name_it() -> None:
    """``ROLE_LABELS`` names the eight roles in privilege order."""
    assert list(ROLE_LABELS.items()) == [
        (MEMBER, "Member"),
        (VERIFIER, "Verifier"),
        (DART_LEADER, "DART leader"),
        (USER_ADMIN, "User administrator"),
        (TREASURER, "Treasurer"),
        (ACCOUNT_ADMIN, "Account administrator"),
        (WEBSITE_ADMIN, "Website administrator"),
        (SYSTEM_ADMIN, "System administrator"),
    ]


def test_the_role_labels_follow_the_role_slugs() -> None:
    """The labels are keyed in exactly the order ``ROLE_SLUGS`` lists the roles."""
    assert tuple(ROLE_LABELS) == ROLE_SLUGS


def test_the_staff_role_labels_leave_out_the_member() -> None:
    """``STAFF_ROLE_LABELS`` is every label but the member's, in the same order."""
    assert list(STAFF_ROLE_LABELS.values()) == SECTION_TITLES


# --------------------------------------------------------------------------
# The spec
# --------------------------------------------------------------------------
def test_the_report_is_titled_and_named_for_its_file() -> None:
    """The title heads the PDF; the stem begins the file name."""
    assert (ROLES_REPORT.title, ROLES_REPORT.filename_stem) == (
        "CalDART roles report",
        "caldart-roles",
    )


def test_the_report_is_landscape_with_choosable_columns_and_no_period() -> None:
    """``(choosable, landscape, periods)``: a wide table whose columns can be chosen."""
    spec = ROLES_REPORT
    assert (spec.choosable, spec.landscape, spec.periods) == (True, True, False)


def test_the_default_columns_are_the_everyday_seven() -> None:
    """Role, name, email, phone, DART, kind, and membership are on by default."""
    chosen = select_columns(ROLES_REPORT_COLUMNS, None)
    assert tuple(column.key for column in chosen) == DEFAULT_COLUMNS


def test_every_column_is_registered_in_export_order() -> None:
    """The ten columns, the three off by default at the end."""
    assert [(column.key, column.label) for column in ROLES_REPORT_COLUMNS] == [
        ("role", "Role"),
        ("name", "Name"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("dart", "DART"),
        ("kind", "Kind"),
        ("membership", "Membership"),
        ("city", "City"),
        ("county", "County"),
        ("home_airport", "Home airport"),
    ]


# --------------------------------------------------------------------------
# Rows and sections
# --------------------------------------------------------------------------
def test_every_staff_role_is_a_section_even_when_nobody_holds_it() -> None:
    """The seven staff roles are the sections, in privilege order, with no rows at all."""
    assert section_titles() == SECTION_TITLES


def test_an_account_is_listed_once_per_staff_role_it_holds() -> None:
    """A system administrator who is also an account administrator is in both sections."""
    both = UserFactory(email="both@example.test", roles=[MEMBER, ACCOUNT_ADMIN, SYSTEM_ADMIN])
    assert pairs(rows_for()) == [
        ("Account administrator", both.email),
        ("System administrator", both.email),
    ]


def test_a_plain_member_is_not_listed() -> None:
    """The member role alone is no section, so a member with no other role is absent."""
    UserFactory(email="plain@example.test", roles=[MEMBER])
    assert rows_for() == []


def test_a_deactivated_account_is_never_listed() -> None:
    """An account that is not active is left out, whatever roles it holds."""
    UserFactory(email="gone@example.test", roles=[MEMBER, TREASURER], is_active=False)
    assert rows_for() == []


def test_rows_in_a_section_are_ordered_by_last_name_first_name_then_email() -> None:
    """Within one role, surname, then forename, then address settles the order."""
    for email, first, last in [
        ("c@example.test", "Ann", "Zed"),
        ("b@example.test", "Bea", "Abe"),
        ("z@example.test", "Ann", "Abe"),
        ("a@example.test", "Ann", "Abe"),
    ]:
        UserFactory(email=email, first_name=first, last_name=last, roles=[TREASURER])
    assert [row.user.email for row in rows_for()] == [
        "a@example.test",
        "z@example.test",
        "b@example.test",
        "c@example.test",
    ]


def test_rows_come_section_by_section_in_privilege_order() -> None:
    """The flat rows run through the sections in the order the report draws them."""
    UserFactory(email="sys@example.test", last_name="Aaron", roles=[SYSTEM_ADMIN])
    UserFactory(email="lead@example.test", last_name="Zola", roles=[DART_LEADER])
    assert pairs(rows_for()) == [
        ("DART leader", "lead@example.test"),
        ("System administrator", "sys@example.test"),
    ]


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------
def cells_for(email: str, columns: str) -> list[str]:
    """The cells of the first row for ``email`` in the report, for ``columns``."""
    table = ROLES_REPORT.table({"columns": f"email,{columns}"}, fmt="csv", today=TODAY)
    return next(row[1:] for row in table.rows if row[0] == email)


def test_a_row_reads_the_profile_and_the_dart(dart: Dart) -> None:
    """Phone, DART, city, county, and home airport come from the member's profile."""
    person = UserFactory(email="p@example.test", roles=[TREASURER])
    MemberProfileFactory(
        user=person,
        dart=dart,
        phone="415-555-0100",
        city="Novato",
        county="Marin",
        home_airport_identifier="DVO",
    )
    assert cells_for(person.email, "phone,dart,city,county,home_airport") == [
        "415-555-0100",
        dart.name,
        "Novato",
        "Marin",
        "DVO",
    ]


def test_an_account_without_a_profile_leaves_the_profile_cells_blank() -> None:
    """No profile row: the phone, DART, city, county, and airport cells are empty."""
    UserFactory(email="bare@example.test", roles=[USER_ADMIN])
    assert cells_for("bare@example.test", "phone,dart,city,county,home_airport") == [""] * 5


def test_a_current_member_reads_member_and_current(annual_plan: MembershipPlan) -> None:
    """A member whose term covers today is Kind Member, Membership Current."""
    person = UserFactory(email="cur@example.test", roles=[TREASURER])
    MembershipFactory(user=person, plan=annual_plan)
    assert cells_for(person.email, "kind,membership") == ["Member", "Current"]


def test_a_friend_reads_friend_twice() -> None:
    """A friend of CalDART is Kind Friend and Membership Friend."""
    UserFactory(email="fr@example.test", kind=AccountKind.FRIEND, roles=[WEBSITE_ADMIN])
    assert cells_for("fr@example.test", "kind,membership") == ["Friend", "Friend"]


def test_the_role_cell_is_the_section_s_label() -> None:
    """The Role column carries the role, so the flat CSV loses no section."""
    UserFactory(email="r@example.test", roles=[DART_LEADER])
    assert cells_for("r@example.test", "role") == ["DART leader"]


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
@pytest.fixture
def staff(annual_plan: MembershipPlan) -> list[User]:
    """Three staff accounts: a member treasurer, a friend treasurer, a DART leader."""
    member_treasurer = UserFactory(
        email="mt@example.test", first_name="Maya", last_name="Ortiz", roles=[TREASURER]
    )
    MembershipFactory(user=member_treasurer, plan=annual_plan)
    friend_treasurer = UserFactory(
        email="ft@example.test",
        first_name="Finn",
        last_name="Ortiz",
        kind=AccountKind.FRIEND,
        roles=[TREASURER],
    )
    leader = UserFactory(
        email="dl@example.test", first_name="Dana", last_name="Lamb", roles=[DART_LEADER]
    )
    return [member_treasurer, friend_treasurer, leader]


def test_role_narrows_the_report_to_that_one_section(staff: list[User]) -> None:
    """``?role=treasurer`` draws the Treasurer section alone."""
    assert section_titles({"role": TREASURER}) == ["Treasurer"]


def test_role_lists_only_that_role_s_holders(staff: list[User]) -> None:
    """``?role=treasurer`` lists the two treasurers, and nobody else."""
    assert pairs(rows_for({"role": TREASURER})) == [
        ("Treasurer", "ft@example.test"),
        ("Treasurer", "mt@example.test"),
    ]


def test_a_role_filter_keeps_only_that_role_of_an_account_holding_several() -> None:
    """A treasurer who is also a leader is listed under Treasurer alone."""
    UserFactory(email="two@example.test", roles=[DART_LEADER, TREASURER])
    assert pairs(rows_for({"role": TREASURER})) == [("Treasurer", "two@example.test")]


@pytest.mark.parametrize("role", [MEMBER, "pilot"], ids=["member", "unknown"])
def test_role_refuses_anything_but_a_staff_role(role: str) -> None:
    """The member role and an unknown slug are refused, keyed by ``role``."""
    with pytest.raises(ValidationError) as caught:
        ROLES_REPORT.query({"role": role})
    assert caught.value.detail == {
        "role": [f"Select a valid choice. {role} is not one of the available choices."]
    }


def test_search_matches_every_word_against_name_or_email(staff: list[User]) -> None:
    """Each word must match the first name, the last name, or the address."""
    assert pairs(rows_for({"search": "ortiz maya"})) == [("Treasurer", "mt@example.test")]


def test_search_matches_part_of_the_address(staff: list[User]) -> None:
    """A fragment of the address is enough."""
    assert pairs(rows_for({"search": "dl@"})) == [("DART leader", "dl@example.test")]


def test_kind_member_lists_members_alone(staff: list[User]) -> None:
    """``?kind=member`` keeps the treasurer who holds a current term only."""
    assert pairs(rows_for({"kind": "member"})) == [("Treasurer", "mt@example.test")]


def test_kind_friend_lists_friends_alone(staff: list[User]) -> None:
    """``?kind=friend`` keeps the friend treasurer and the leader, who holds no term."""
    assert pairs(rows_for({"kind": "friend"})) == [
        ("DART leader", "dl@example.test"),
        ("Treasurer", "ft@example.test"),
    ]


def test_kind_refuses_a_donor(staff: list[User]) -> None:
    """A donor never holds a role, so ``kind=donor`` is refused, keyed by ``kind``."""
    with pytest.raises(ValidationError) as caught:
        ROLES_REPORT.query({"kind": "donor"})
    assert caught.value.detail == {
        "kind": ["Select a valid choice. donor is not one of the available choices."]
    }


def test_the_report_names_the_filters_it_applied(staff: list[User]) -> None:
    """Only the filters given a value are named, in the order search, role, kind."""
    query = ROLES_REPORT.query({"kind": "member", "role": TREASURER, "search": "", "page": "2"})
    assert query.filters == {"role": TREASURER, "kind": "member"}


# --------------------------------------------------------------------------
# The endpoints
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_report_list_offers_the_roles_report_to_its_readers(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """User and account administrators, and system administrators, see ``roles``."""
    api_client.force_login(all_role_users[role])
    slugs = [entry["slug"] for entry in api_client.get(REPORTS_URL).json()]
    assert ("roles" in slugs) is allowed


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_export_is_for_the_report_s_readers(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Anybody else is refused with a 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(CSV_URL).status_code == (200 if allowed else 403)


def test_the_csv_download_is_named_for_the_day(account_admin_client: APIClient) -> None:
    """The file is ``caldart-roles-<YYYY-MM-DD>.csv``."""
    response = account_admin_client.get(CSV_URL)
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-roles-{timezone.localdate().isoformat()}.csv"'
    )


def test_the_csv_filtered_by_role_lists_that_role_alone(
    account_admin_client: APIClient, all_role_users: dict[str, User]
) -> None:
    """``?role=treasurer`` exports the treasurer's row and nobody else's."""
    table = read_csv(
        account_admin_client.get(CSV_URL, {"role": TREASURER, "columns": "role,email"})
    )
    assert table == [["Role", "Email"], ["Treasurer", "treasurer@example.test"]]


def test_the_csv_refuses_the_member_role(account_admin_client: APIClient) -> None:
    """A role the report has no section for is a 400 keyed by ``role``."""
    response = account_admin_client.get(CSV_URL, {"role": MEMBER})
    assert response.status_code == 400
    assert response.json() == {
        "role": ["Select a valid choice. member is not one of the available choices."]
    }


def test_the_pdf_heads_each_role_s_section(
    account_admin_client: APIClient, all_role_users: dict[str, User], pdf_text: PdfText
) -> None:
    """Every section title appears on the page, in privilege order."""
    strings = pdf_text(account_admin_client.get(PDF_URL, {"columns": "email"}).content)[0]
    assert [text for text in strings if text in SECTION_TITLES] == SECTION_TITLES


def test_the_pdf_says_so_under_a_role_nobody_holds(
    account_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """With only the account administrator signed in, the verifier's section is empty."""
    strings = pdf_text(account_admin_client.get(PDF_URL).content)[0]
    assert strings[2:4] == ["Verifier", "Nobody holds this role."]


def test_an_account_administrator_can_send_the_report_to_a_user_administrator(
    account_admin_client: APIClient, user_admin: User
) -> None:
    """A subscription to ``roles`` for a user administrator is set up."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {
            "report": "roles",
            "recipient_email": user_admin.email,
            "filters": {"role": TREASURER},
            "columns": [],
            "formats": "pdf",
            "cadence": "monthly",
            "weekday": 0,
        },
        format="json",
    )
    assert response.status_code == 201


def test_the_report_cannot_be_sent_to_a_treasurer(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """A treasurer does not read the roles report, so sending it to one is refused."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {
            "report": "roles",
            "recipient_email": treasurer.email,
            "filters": {},
            "columns": [],
            "formats": "pdf",
            "cadence": "monthly",
            "weekday": 0,
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {
        "recipient_email": [
            f"{treasurer.display_name} does not hold a role that may read this report."
        ]
    }
