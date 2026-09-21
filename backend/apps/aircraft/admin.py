"""Django admin for the aircraft register."""

from django.contrib import admin

from apps.aircraft.models import Aircraft


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
    list_filter = ["owner_type", "is_active", "make"]
    search_fields = ["n_number", "make", "model", "owner_name", "insurance_carrier"]
    autocomplete_fields = ["created_by"]
    readonly_fields = ["created_at", "updated_at", "insurance_summary"]
    ordering = ["n_number"]

    @admin.display(boolean=True, description="insurance current")
    def insurance_is_current(self, obj: Aircraft) -> bool:
        """Return whether ``obj`` has a non-expired insurance expiration date."""
        return obj.insurance_is_current
