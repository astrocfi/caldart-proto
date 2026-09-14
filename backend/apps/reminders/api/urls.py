"""Reminder API routes."""

from django.urls import path

from apps.reminders.api import views

app_name = "reminders"

urlpatterns = [
    path("admin/reminders/log", views.ReminderLogListView.as_view(), name="log"),
    path("system/reminders/run", views.ReminderRunView.as_view(), name="run"),
]
