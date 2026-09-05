"""Django admin for the aircraft register."""

from django.contrib import admin

from apps.aircraft.models import Aircraft


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
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
        return obj.insurance_is_current
