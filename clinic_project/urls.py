"""
URL configuration for clinic_project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("appointments/", include("appointments.urls")),
]
