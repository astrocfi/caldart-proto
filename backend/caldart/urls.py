"""Root URLconf.

Order matters: the Wagtail page serving view is a catch-all and must come
last.  ``/portal/`` is itself a catch-all for the SPA's client-side routes.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin as django_admin
from django.urls import include, path, re_path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from caldart.views import apple_pay_domain_association, portal_shell

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("django-admin/", django_admin.site.urls),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v1/", include("caldart.api_urls")),
    path(
        ".well-known/apple-developer-merchantid-domain-association",
        apple_pay_domain_association,
        name="apple-pay-domain-association",
    ),
    re_path(r"^portal/(?P<path>.*)$", portal_shell, name="portal"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Wagtail's page serving must stay last: it matches everything else.
urlpatterns += [
    path("", include(wagtail_urls)),
]
