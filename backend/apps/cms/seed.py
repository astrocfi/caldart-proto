"""Ensure a Wagtail site root and a ``SiteSettings`` row exist.

The full example site comes from ``manage.py seed_content``; this only
guarantees the chrome the rest of the system reads.
"""

from __future__ import annotations

from wagtail.models import Page, Site

from apps.cms.models import DEFAULT_THEME, HomePage, SiteSettings


def ensure_site_root() -> Site:
    """Return the default site, creating a ``HomePage`` root if needed."""
    site = Site.objects.filter(is_default_site=True).first()
    home = HomePage.objects.first()

    if home is None:
        root = Page.get_first_root_node()
        home = HomePage(
            title="Home",
            slug="home",
            hero_heading="Volunteer air transportation when California needs it",
            hero_lede=(
                "CalDART organises pilots and ground personnel across the state so "
                "relief supplies, personnel and information move when roads do not."
            ),
            primary_cta_label="Join CalDART",
            primary_cta_url="/portal/join",
        )
        root.add_child(instance=home)
        home.save_revision().publish()

    if site is None:
        site = Site.objects.create(
            hostname="localhost",
            port=80,
            site_name="CalDART",
            root_page=home,
            is_default_site=True,
        )
    elif site.root_page_id != home.pk:
        site.root_page = home
        site.save(update_fields=["root_page"])
    return site


def run(ctx: dict, stdout=None) -> dict:
    site = ensure_site_root()
    settings_obj, created = SiteSettings.objects.get_or_create(
        site=site, defaults={"theme": DEFAULT_THEME}
    )
    if not settings_obj.theme:
        settings_obj.theme = DEFAULT_THEME
        settings_obj.save(update_fields=["theme"])

    ctx["site"] = site
    ctx["site_settings"] = settings_obj
    if stdout is not None:
        verb = "created" if created else "present"
        stdout.write(f"  cms: site root '{site.root_page}' and settings {verb}")
    return ctx
