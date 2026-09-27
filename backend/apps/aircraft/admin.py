"""Django admin for the aircraft register."""

from django.contrib import admin
from django.http import HttpRequest

from apps.aircraft.models import Aircraft, AircraftChange, AircraftType


@admin.register(Aircraft)
# django-stubs types ModelAdmin as generic, but Django's own class is not subscriptable.
# django-stubs-ext patches __class_getitem__ onto it at runtime, and that patch lands only
# once a later app is imported -- well after the admin autodiscovery that imports this
# module -- so writing ModelAdmin[Aircraft] here raises TypeError during django.setup().
class AircraftAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """The Django admin view of the aircraft register."""

    list_display = [
        "n_number",
        "make",
        "model",
        "year",
        "owner_type",
        "owner_name",
        "insurance_expiration",
        "insurance_is_current",
    ]
    list_filter = ["owner_type", "is_active", "type__make"]
    list_select_related = ["type"]
    search_fields = ["n_number", "type__make", "type__model", "owner_name", "insurance_carrier"]
    autocomplete_fields = ["type", "created_by", "updated_by"]
    readonly_fields = ["created_at", "updated_at", "insurance_summary"]
    ordering = ["n_number"]

    @admin.display(boolean=True, description="insurance current")
    def insurance_is_current(self, obj: Aircraft) -> bool:
        """Return whether ``obj`` has a non-expired insurance expiration date."""
        return obj.insurance_is_current


@admin.register(AircraftType)
# The same django-stubs caveat as above: ModelAdmin is not subscriptable at
# admin-autodiscovery time.
class AircraftTypeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """The aircraft types an aircraft is picked from."""

    list_display = ["make", "model", "faa_code", "seats", "engines", "is_custom"]
    list_filter = ["is_custom"]
    search_fields = ["make", "model", "faa_make", "faa_model", "faa_code"]
    readonly_fields = ["created_at"]
    ordering = ["make", "model"]


@admin.register(AircraftChange)
# The same django-stubs caveat as above: ModelAdmin is not subscriptable at
# admin-autodiscovery time.
class AircraftChangeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """The register's change history, which the admin reads and never writes."""

    list_display = ["changed_at", "aircraft", "kind", "changed_by"]
    list_filter = ["kind"]
    search_fields = ["aircraft__n_number"]
    readonly_fields = ["aircraft", "changed_by", "changed_at", "kind", "fields"]
    ordering = ["-changed_at", "-id"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Return ``False``: a change is written by the register, never by hand."""
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: AircraftChange | None = None
    ) -> bool:
        """Return ``False``: the history is a record, so nothing edits it."""
        return False
