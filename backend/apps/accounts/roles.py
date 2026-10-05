"""Role slugs.

Roles are Django ``Group`` rows whose ``name`` is the slug below.  That makes
"add a role later" a data change, and lets Wagtail reuse the same groups for
editor permissions.
"""

MEMBER = "member"
VERIFIER = "verifier"
DART_LEADER = "dart_leader"
USER_ADMIN = "user_admin"
TREASURER = "treasurer"
ACCOUNT_ADMIN = "account_admin"
MANAGEMENT = "management"
WEBSITE_ADMIN = "website_admin"
SYSTEM_ADMIN = "system_admin"

#: Ordered slug -> human description.  Order is least to most privileged and is
#: the order used by ``GET /api/v1/roles``.
ROLE_DESCRIPTIONS: dict[str, str] = {
    MEMBER: "A member or a friend with a portal account.",
    VERIFIER: (
        "Verify a member's pilot certificate, medical, and photo ID, and an "
        "aircraft's insurance, from the member check and the aircraft check."
    ),
    DART_LEADER: (
        "Look up any member and see membership, medical, certificate, and "
        "aircraft insurance currency, and send bulk email to the members and "
        "friends of the DART on their own profile."
    ),
    USER_ADMIN: (
        "List users, assign roles, deactivate or reactivate accounts, and send password "
        "reset emails."
    ),
    TREASURER: (
        "See every payment, fee, refund, and renewal; issue refunds, record "
        "payments taken by hand, and run the financial reports."
    ),
    ACCOUNT_ADMIN: (
        "Create, edit, and delete members and profiles, grant or extend "
        "memberships by hand, manage aircraft, and run payment, membership, "
        "and aircraft reports."
    ),
    MANAGEMENT: (
        "Send bulk email to any members and friends the filters choose, and see "
        "every bulk email any sender has written, with its sender and its DART."
    ),
    WEBSITE_ADMIN: ("Edit the public website: pages, pictures, documents, and site settings."),
    SYSTEM_ADMIN: ("Everything above, plus the server's health, backups, and scheduled jobs."),
}

#: All role slugs, in privilege order.
ROLE_SLUGS: tuple[str, ...] = tuple(ROLE_DESCRIPTIONS)

#: Roles that mean "this person is staff of some kind", i.e. everything except
#: the plain ``member`` role.  Used by ``can_access_members_content``.
STAFF_ROLE_SLUGS: tuple[str, ...] = tuple(s for s in ROLE_SLUGS if s != MEMBER)

#: Ordered slug -> the role's name as every screen and report prints it.
ROLE_LABELS: dict[str, str] = {
    MEMBER: "Member",
    VERIFIER: "Verifier",
    DART_LEADER: "DART leader",
    USER_ADMIN: "User administrator",
    TREASURER: "Treasurer",
    ACCOUNT_ADMIN: "Account administrator",
    MANAGEMENT: "CalDART management",
    WEBSITE_ADMIN: "Website administrator",
    SYSTEM_ADMIN: "System administrator",
}

#: The labels of the staff roles, every role but ``member``, in privilege order.
STAFF_ROLE_LABELS: dict[str, str] = {slug: ROLE_LABELS[slug] for slug in STAFF_ROLE_SLUGS}

#: The roles that may verify a member's pilot certificate, medical, and photo ID, and an
#: aircraft's insurance.  A system administrator and a superuser pass as always.
VERIFY_ROLES: tuple[str, ...] = (VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN)
