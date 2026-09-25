"""Django admin for the members domain."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.members.models import MemberProfile, Membership, MembershipPlan

if TYPE_CHECKING:
    # ``ModelAdmin`` carries the model it manages for the type checker, but it is
    # a plain class at runtime and cannot be subscripted, so each base is named
    # here and falls back to the bare class when the module is imported.
    ProfileAdminBase = admin.ModelAdmin[MemberProfile]
    PlanAdminBase = admin.ModelAdmin[MembershipPlan]
    MembershipAdminBase = admin.ModelAdmin[Membership]
else:
    ProfileAdminBase = admin.ModelAdmin
    PlanAdminBase = admin.ModelAdmin
    MembershipAdminBase = admin.ModelAdmin


@admin.register(MemberProfile)
class MemberProfileAdmin(ProfileAdminBase):
    """Member profiles, searchable by account and certificate number."""

    list_display = [
        "display_name",
        "dart",
        "pilot_certificate_type",
        "medical_type",
        "medical_expiration",
        "medical_is_current",
    ]
    list_filter = ["dart", "pilot_certificate_type", "medical_type", "ifr_rated"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "certificate_number"]
    autocomplete_fields = ["user", "dart", "aircraft"]
    readonly_fields = ["created_at", "updated_at", "profile_updated_at"]

    @admin.display(boolean=True, description="medical current")
    def medical_is_current(self, obj: MemberProfile) -> bool:
        """True when the member holds a medical that has not expired."""
        return obj.medical_is_current


@admin.register(MembershipPlan)
class MembershipPlanAdmin(PlanAdminBase):
    """Membership plans, with the slug prepopulated from the name."""

    list_display = ["name", "slug", "price_cents", "duration_days", "is_active", "sort_order"]
    list_filter = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(MembershipAdminBase):
    """Membership terms, browsable by start date."""

    list_display = ["user", "plan", "starts_on", "ends_on", "status", "source"]
    list_filter = ["status", "source", "plan"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "granted_by"]
    date_hierarchy = "starts_on"
    readonly_fields = ["created_at", "updated_at"]
