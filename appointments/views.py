"""
appointments/views.py
Views for the appointment booking system.
"""

import datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import role_required
from doctors.models import DoctorProfile

from .models import Appointment
from .services import SlotUnavailableError, get_available_slots, hold_slot


# ---------------------------------------------------------------------------
# JSON API: available slots for the fetch()-based slot picker
# ---------------------------------------------------------------------------

@login_required
@require_GET
def available_slots_view(request):
    """
    GET /appointments/api/slots/?doctor_id=<int>&date=<YYYY-MM-DD>

    Returns a JSON list of available slot-start times:
        {"slots": ["09:00", "09:30", ...]}
    """
    doctor_id = request.GET.get("doctor_id")
    date_str = request.GET.get("date")

    if not doctor_id or not date_str:
        return JsonResponse(
            {"error": "doctor_id and date query parameters are required."},
            status=400,
        )

    try:
        doctor = DoctorProfile.objects.get(pk=doctor_id, is_active=True)
    except DoctorProfile.DoesNotExist:
        return JsonResponse({"error": "Doctor not found."}, status=404)

    try:
        date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse(
            {"error": "Invalid date format. Use YYYY-MM-DD."},
            status=400,
        )

    slots = get_available_slots(doctor, date)
    return JsonResponse({
        "doctor_id": doctor.pk,
        "date": date.isoformat(),
        "slots": [t.strftime("%H:%M") for t in slots],
    })


# ---------------------------------------------------------------------------
# Doctor search
# ---------------------------------------------------------------------------

@role_required("patient")
def doctor_search_view(request):
    """
    GET /appointments/doctors/?q=<specialisation>

    Patient-facing page listing active doctors, optionally filtered by
    specialisation keyword.
    """
    query = request.GET.get("q", "").strip()
    doctors = DoctorProfile.objects.filter(is_active=True).select_related("user")

    if query:
        doctors = doctors.filter(specialisation__icontains=query)

    return render(request, "appointments/doctor_search.html", {
        "doctors": doctors,
        "query": query,
    })


# ---------------------------------------------------------------------------
# Book slot (patient only)
# ---------------------------------------------------------------------------

@role_required("patient")
@require_POST
def book_slot_view(request):
    """
    POST /appointments/book/
    Body: doctor_id, date (YYYY-MM-DD), start_time (HH:MM)

    Holds a slot and redirects to the symptom-form step on success.
    On failure returns a clean error message + redirect back to the doctor page.
    """
    doctor_id = request.POST.get("doctor_id")
    date_str = request.POST.get("date")
    time_str = request.POST.get("start_time")

    if not all([doctor_id, date_str, time_str]):
        messages.error(request, "Missing booking parameters.")
        return redirect("appointments:doctor_search")

    doctor = get_object_or_404(DoctorProfile, pk=doctor_id, is_active=True)

    try:
        date = datetime.date.fromisoformat(date_str)
        start_time = datetime.time.fromisoformat(time_str)
    except ValueError:
        messages.error(request, "Invalid date or time format.")
        return redirect("appointments:doctor_detail", doctor_id=doctor.pk)

    try:
        appointment = hold_slot(
            patient=request.user,
            doctor_profile=doctor,
            date=date,
            start_time=start_time,
        )
    except SlotUnavailableError as exc:
        messages.error(request, str(exc))
        return redirect("appointments:doctor_detail", doctor_id=doctor.pk)

    messages.info(
        request,
        f"Slot held for {appointment.start_time:%H:%M}. "
        f"Please complete the symptom form to confirm your appointment."
    )
    return redirect("consultations:symptom_form", appointment_id=appointment.pk)


# ---------------------------------------------------------------------------
# Doctor detail / slot picker
# ---------------------------------------------------------------------------

@role_required("patient")
def doctor_detail_view(request, doctor_id):
    """
    GET /appointments/doctors/<id>/

    Shows doctor info + a date picker + dynamic slot buttons (loaded via fetch).
    """
    doctor = get_object_or_404(DoctorProfile, pk=doctor_id, is_active=True)
    return render(request, "appointments/doctor_detail.html", {
        "doctor": doctor,
    })


# ---------------------------------------------------------------------------
# My appointments (patient)
# ---------------------------------------------------------------------------

@role_required("patient")
def my_appointments_view(request):
    """
    GET /appointments/mine/

    Lists all appointments for the logged-in patient, split into upcoming
    and past.
    """
    today = datetime.date.today()
    qs = Appointment.objects.filter(patient=request.user).select_related(
        "doctor", "doctor__user"
    )

    upcoming = qs.filter(date__gte=today).exclude(
        status__in=[Appointment.Status.CANCELLED, Appointment.Status.LEAVE_CANCELLED]
    ).order_by("date", "start_time")

    past = qs.filter(date__lt=today).order_by("-date", "-start_time")

    return render(request, "appointments/my_appointments.html", {
        "upcoming": upcoming,
        "past": past,
    })


# ---------------------------------------------------------------------------
# Doctor appointments (doctor)
# ---------------------------------------------------------------------------

@role_required("doctor")
def doctor_appointments_view(request):
    """
    GET /appointments/doctor/

    Lists upcoming appointments for the logged-in doctor.
    """
    today = datetime.date.today()
    profile = get_object_or_404(DoctorProfile, user=request.user)

    appointments = (
        Appointment.objects
        .filter(
            doctor=profile,
            date__gte=today,
        )
        .exclude(
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.LEAVE_CANCELLED]
        )
        .select_related("patient")
        .order_by("date", "start_time")
    )

    return render(request, "appointments/doctor_appointments.html", {
        "appointments": appointments,
    })


# ---------------------------------------------------------------------------
# Cancel appointment
# ---------------------------------------------------------------------------

@login_required
@require_POST
def cancel_appointment_view(request, appointment_id):
    """
    POST /appointments/<id>/cancel/

    Lets the patient or doctor cancel a held or confirmed appointment.
    """
    appointment = get_object_or_404(Appointment, pk=appointment_id)

    # Verify the request user is the patient or the doctor
    is_patient_owner = appointment.patient == request.user
    is_doctor_owner = (
        hasattr(request.user, "doctor_profile")
        and appointment.doctor == request.user.doctor_profile
    )

    if not (is_patient_owner or is_doctor_owner or request.user.is_superuser):
        messages.error(request, "You cannot cancel this appointment.")
        return redirect("accounts:dashboard_redirect")

    if appointment.status not in Appointment.ACTIVE_STATUSES:
        messages.warning(
            request,
            f"This appointment is already {appointment.get_status_display().lower()}."
        )
    else:
        appointment.status = Appointment.Status.CANCELLED
        appointment.hold_expires_at = None
        appointment.save(update_fields=["status", "hold_expires_at", "updated_at"])
        messages.success(request, "Appointment cancelled successfully.")

    # Redirect back to whichever list is appropriate
    if is_doctor_owner:
        return redirect("appointments:doctor_appointments")
    return redirect("appointments:my_appointments")
