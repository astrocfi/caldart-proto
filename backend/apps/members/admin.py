"""Django admin for the members domain."""

from django.contrib import admin

from apps.members.models import Dart, MemberProfile, Membership, MembershipPlan


@admin.register(Dart)
class DartAdmin(admin.ModelAdmin):
    list_display = ["name", "airport_identifier", "city", "is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["name", "airport_identifier", "city"]
    ordering = ["sort_order", "name"]


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
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
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(boolean=True, description="medical current")
    def medical_is_current(self, obj: MemberProfile) -> bool:
        return obj.medical_is_current


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "price_cents", "duration_days", "is_active", "sort_order"]
    list_filter = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "starts_on", "ends_on", "status", "source"]
    list_filter = ["status", "source", "plan"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "granted_by"]
    date_hierarchy = "starts_on"
    readonly_fields = ["created_at", "updated_at"]
