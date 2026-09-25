"""Members-admin routes.  Included from ``members/api/urls.py``.

No ``app_name`` here on purpose: these names live in the ``members`` namespace
the parent module declares.
"""

from django.urls import path

from apps.members.api import admin_views

urlpatterns = [
    path(
        "admin/members",
        admin_views.MemberAdminListCreateView.as_view(),
        name="admin-members",
    ),
    path(
        "admin/members/<int:pk>",
        admin_views.MemberAdminDetailView.as_view(),
        name="admin-member-detail",
    ),
    path(
        "admin/members/<int:pk>/memberships",
        admin_views.MemberMembershipGrantView.as_view(),
        name="admin-member-memberships",
    ),
    path(
        "admin/memberships/<int:pk>",
        admin_views.MembershipAdminDetailView.as_view(),
        name="admin-membership-detail",
    ),
]
