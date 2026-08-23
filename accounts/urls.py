"""
accounts/urls.py
URL patterns for the accounts app (namespace: "accounts").
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Registration
    path("register/", views.register, name="register"),

    # Login / Logout (Django built-in auth views)
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # Role-based dashboard redirect
    path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),

    # Placeholder dashboards (replaced in later steps)
    path(
        "dashboard/patient/",
        views.patient_dashboard_placeholder,
        name="patient_dashboard",
    ),
    path(
        "dashboard/doctor/",
        views.doctor_dashboard_placeholder,
        name="doctor_dashboard",
    ),
]
