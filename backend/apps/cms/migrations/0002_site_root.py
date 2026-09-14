"""Make a ``HomePage`` the Wagtail site root and drop the stock welcome page."""

from django.db import migrations


def create_site_root(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    Site = apps.get_model("wagtailcore", "Site")
    HomePage = apps.get_model("cms", "HomePage")

    home_type, _ = ContentType.objects.get_or_create(app_label="cms", model="homepage")

    root = Page.objects.filter(depth=1).first()
    if root is None:  # pragma: no cover - wagtail always creates this
        return

    home = HomePage.objects.first()
    if home is None:
        # Reuse the slot left by Wagtail's stock "Welcome" page if it is there.
        Page.objects.filter(depth=2, slug="home").exclude(content_type=home_type).delete()
        siblings = Page.objects.filter(depth=2).count()
        home = HomePage.objects.create(
            title="Home",
            draft_title="Home",
            slug="home",
            content_type=home_type,
            path=root.path + f"{siblings + 1:04d}",
            depth=2,
            numchild=0,
            url_path="/home/",
            live=True,
            has_unpublished_changes=False,
            show_in_menus=False,
            locale_id=root.locale_id,
            hero_heading="Volunteer air transportation when California needs it",
            hero_lede=(
                "CalDART organizes pilots and ground personnel across the state so "
                "relief supplies, personnel and information move when roads do not."
            ),
            primary_cta_label="Join CalDART",
            primary_cta_url="/portal/join",
            secondary_cta_label="About us",
            secondary_cta_url="/about/",
        )
        root.numchild = Page.objects.filter(depth=2).count()
        root.save(update_fields=["numchild"])

    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        Site.objects.create(
            hostname="localhost",
            port=80,
            site_name="CalDART",
            root_page_id=home.page_ptr_id,
            is_default_site=True,
        )
    else:
        site.root_page_id = home.page_ptr_id
        site.site_name = "CalDART"
        site.save(update_fields=["root_page_id", "site_name"])


def noop(apps, schema_editor):
    """Leaving the site root in place on reverse is harmless."""


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0001_initial"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.RunPython(create_site_root, noop),
    ]
