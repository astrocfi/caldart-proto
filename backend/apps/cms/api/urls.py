"""CMS API routes (PLAN §6.10).  Owned by ``feat/cms-site``."""

from django.urls import path

from apps.cms.api import views

app_name = "cms"

urlpatterns = [
    path("site/config", views.SiteConfigView.as_view(), name="site-config"),
]
