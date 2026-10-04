"""The bulk email app's public page: the answer page a mission callout's buttons open."""

from django.urls import path

from apps.bulk_email import views

urlpatterns = [
    path("mail/callout/<str:token>", views.callout_answer, name="callout-answer"),
]
