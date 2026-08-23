"""
accounts/views.py
Authentication and dashboard-routing views.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import PatientRegistrationForm
from .models import User


def register(request):
    """Register a new patient account."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard_redirect")

    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.first_name or user.username}!")
            return redirect("accounts:dashboard_redirect")
    else:
        form = PatientRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard_redirect(request):
    """
    Inspect the authenticated user's role and redirect to the appropriate
    dashboard.  Superusers / admin-role users go to the Django admin site.
    """
    user = request.user

    if user.is_superuser or user.role == User.Role.ADMIN:
        return redirect(reverse("admin:index"))

    if user.role == User.Role.DOCTOR:
        return redirect(reverse("appointments:doctor_appointments"))

    # Default: patient
    return redirect(reverse("appointments:my_appointments"))


# ---------------------------------------------------------------------------
# Placeholder dashboards (replaced in later steps when full apps are built)
# ---------------------------------------------------------------------------

@login_required
def patient_dashboard_placeholder(request):
    """Temporary patient dashboard — replaced in a later step."""
    return render(request, "accounts/patient_dashboard.html")


@login_required
def doctor_dashboard_placeholder(request):
    """Temporary doctor dashboard — replaced in a later step."""
    return render(request, "accounts/doctor_dashboard.html")
