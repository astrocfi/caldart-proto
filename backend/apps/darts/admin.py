"""Django admin for DARTs and the people who run them."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.darts.models import Dart, DartContact

if TYPE_CHECKING:
    DartAdminBase = admin.ModelAdmin[Dart]
    ContactInlineBase = admin.TabularInline[DartContact, Dart]
else:
    DartAdminBase = admin.ModelAdmin
    ContactInlineBase = admin.TabularInline


class DartContactInline(ContactInlineBase):
    """The people who run a DART, edited on the DART's own page."""

    model = DartContact
    extra = 0


@admin.register(Dart)
class DartAdmin(DartAdminBase):
    """DARTs, in the order the public catalog lists them."""

    list_display = ["name", "airport_identifiers", "city", "website_url", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "airport_identifiers", "city"]
    ordering = ["name"]
    inlines = [DartContactInline]
