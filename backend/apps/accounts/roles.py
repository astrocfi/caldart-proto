"""Role slugs.

Roles are Django ``Group`` rows whose ``name`` is the slug below.  That makes
"add a role later" a data change, and lets Wagtail reuse the same groups for
editor permissions.
"""

MEMBER = "member"
DART_LEADER = "dart_leader"
USER_ADMIN = "user_admin"
TREASURER = "treasurer"
ACCOUNT_ADMIN = "account_admin"
WEBSITE_ADMIN = "website_admin"
SYSTEM_ADMIN = "system_admin"

#: Ordered slug -> human description.  Order is least to most privileged and is
#: the order used by ``GET /api/v1/roles``.
ROLE_DESCRIPTIONS: dict[str, str] = {
    MEMBER: "A member or a friend with a portal account.",
    DART_LEADER: (
        "Look up any member and see membership, medical, certificate, and "
        "aircraft insurance currency."
    ),
    USER_ADMIN: (
        "List users, assign roles, activate or deactivate accounts, and trigger password resets."
    ),
    TREASURER: (
        "See every payment, fee, refund, and renewal; issue refunds, record "
        "payments taken by hand, reconcile periods, and run the financial reports."
    ),
    ACCOUNT_ADMIN: (
        "Create, edit, and delete members and profiles, grant or extend "
        "memberships manually, manage aircraft, and run payment, membership "
        "and aircraft reports."
    ),
    WEBSITE_ADMIN: (
        "Wagtail admin: create, edit, delete, and publish pages, images, "
        "documents, redirects, and site settings."
    ),
    SYSTEM_ADMIN: (
        "Everything above plus backups, health, reminder runs and Django superuser access."
    ),
}

#: All role slugs, in privilege order.
ROLE_SLUGS: tuple[str, ...] = tuple(ROLE_DESCRIPTIONS)

#: Roles that mean "this person is staff of some kind", i.e. everything except
#: the plain ``member`` role.  Used by ``can_access_members_content``.
STAFF_ROLE_SLUGS: tuple[str, ...] = tuple(s for s in ROLE_SLUGS if s != MEMBER)
