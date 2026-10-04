"""Root URLconf.

Order matters: the Wagtail page serving view is a catch-all and must come
last, and the closed Wagtail account screens must come before the Wagtail admin
they shadow.  ``/portal/`` is itself a catch-all for the SPA's client-side routes, and
``/docs/`` serves the built user guide to signed-in users.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin as django_admin
from django.urls import include, path, re_path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from apps.cms.views import find_dart
from apps.payments.views import apple_pay_domain_association
from caldart.views import (
    portal_shell,
    user_guide,
    wagtail_account_page,
    wagtail_account_screen_closed,
)

urlpatterns = [
    # Accounts and roles are managed in the portal alone (Users and roles, My
    # profile), so Wagtail's own screens for them are closed.
    re_path(
        r"^admin/(?:users|groups|bulk/accounts|bulk/auth|password_reset)/",
        wagtail_account_screen_closed,
    ),
    path("admin/account/", wagtail_account_page),
    path("admin/", include(wagtailadmin_urls)),
    path("django-admin/", django_admin.site.urls),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v1/", include("caldart.api_urls")),
    path(
        ".well-known/apple-developer-merchantid-domain-association",
        apple_pay_domain_association,
        name="apple-pay-domain-association",
    ),
    path("find-dart/", find_dart, name="find-dart"),
    path("", include("apps.mail.urls")),
    path("", include("apps.bulk_email.urls")),
    re_path(r"^docs/(?P<path>.*)$", user_guide, name="user-guide"),
    re_path(r"^portal/(?P<path>.*)$", portal_shell, name="portal"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Wagtail's page serving must stay last: it matches everything else.
urlpatterns += [
    path("", include(wagtail_urls)),
]
