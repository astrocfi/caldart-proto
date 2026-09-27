"""Notification API routes."""

from django.urls import path

from apps.notifications.api import views

app_name = "notifications"

urlpatterns = [
    path("notifications/events", views.EventListView.as_view(), name="events"),
    path(
        "notifications/subscriptions",
        views.SubscriptionListView.as_view(),
        name="subscriptions",
    ),
    path(
        "notifications/subscriptions/<int:pk>",
        views.SubscriptionDetailView.as_view(),
        name="subscription",
    ),
]
