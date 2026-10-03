"""The mail app's public pages: the unsubscribe link a bulk email carries."""

from django.urls import path

from apps.mail import views

urlpatterns = [
    path("mail/unsubscribe/<str:token>", views.unsubscribe, name="mail-unsubscribe"),
]
