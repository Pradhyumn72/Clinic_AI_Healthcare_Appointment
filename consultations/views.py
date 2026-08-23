"""
consultations/views.py
Pre-visit symptom form, AI summaries, and post-visit notes.

Error contract: LLM failures are caught and handled gracefully in every
view.  A failed LLM call sets ``llm_status="failed"`` and shows a user-
friendly message — it NEVER produces a 500 or blocks the booking/visit flow.
"""

import json
import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from appointments.models import Appointment
from appointments.services import confirm_appointment

# Will be implemented in the next step — currently a stub that logs.
from notifications_app.services import queue_email

from .llm_service import LLMGenerationError, generate_post_visit_summary, generate_pre_visit_summary
from .models import PostVisitNote, SymptomForm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Symptom form (patient)
# ---------------------------------------------------------------------------

@role_required("patient")
def symptom_form_view(request, appointment_id):
    """
    GET: show the symptom form for a held appointment.
    POST: save symptoms, run pre-visit LLM, confirm the appointment.
    """
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        patient=request.user,
    )

    # Don't allow re-entry on already-confirmed or completed appointments
    if hasattr(appointment, "symptom_form"):
        messages.info(request, "Symptoms already submitted for this appointment.")
        return redirect("appointments:my_appointments")

    if appointment.status != Appointment.Status.HELD:
        messages.warning(
            request,
            "This appointment cannot accept a symptom form "
            f"(status: {appointment.get_status_display()}).",
        )
        return redirect("appointments:my_appointments")

    if request.method == "POST":
        symptoms_text = request.POST.get("symptoms_text", "").strip()
        if not symptoms_text:
            messages.error(request, "Please describe your symptoms.")
            return render(request, "consultations/symptom_form.html", {
                "appointment": appointment,
            })

        # Create the SymptomForm record
        symptom_form = SymptomForm(
            appointment=appointment,
            symptoms_text=symptoms_text,
        )

        # LLM pre-visit summary — wrapped in try/except; failure is OK.
        try:
            result = generate_pre_visit_summary(symptoms_text)
            symptom_form.urgency_level = result.get("urgency_level", "")
            symptom_form.chief_complaint = result.get("chief_complaint", "")
            symptom_form.suggested_questions = result.get("suggested_questions", [])
            symptom_form.raw_llm_response = result
            symptom_form.llm_status = SymptomForm.LLMStatus.SUCCESS
        except LLMGenerationError as exc:
            logger.warning("Pre-visit LLM failed for appointment %s: %s", appointment.pk, exc)
            symptom_form.llm_status = SymptomForm.LLMStatus.FAILED
            messages.warning(
                request,
                "AI-powered symptom summary is temporarily unavailable. "
                "Your symptoms will be reviewed manually by the doctor.",
            )

        symptom_form.save()

        # Confirm the appointment (held → confirmed)
        try:
            confirm_appointment(appointment)
        except ValueError as exc:
            # Shouldn't happen, but handle defensively
            logger.error("Failed to confirm appointment %s: %s", appointment.pk, exc)

        # Queue booking confirmation emails
        # (notifications_app.services.queue_email — stub for now,
        #  real EmailLog model/sending is built in the next step)
        doctor_name = (
            appointment.doctor.user.get_full_name()
            or appointment.doctor.user.username
        )
        queue_email(
            to_email=request.user.email,
            subject=f"Appointment confirmed with Dr. {doctor_name}",
            body=(
                f"Your appointment with Dr. {doctor_name} on "
                f"{appointment.date} at {appointment.start_time:%H:%M} "
                f"has been confirmed."
            ),
            related_appointment_id=appointment.pk,
        )
        queue_email(
            to_email=appointment.doctor.user.email,
            subject=f"New appointment: {request.user.get_full_name() or request.user.username}",
            body=(
                f"A new appointment has been confirmed with "
                f"{request.user.get_full_name() or request.user.username} on "
                f"{appointment.date} at {appointment.start_time:%H:%M}."
            ),
            related_appointment_id=appointment.pk,
        )

        messages.success(request, "Appointment confirmed! Your symptoms have been recorded.")
        return redirect("appointments:my_appointments")

    # GET
    return render(request, "consultations/symptom_form.html", {
        "appointment": appointment,
    })


# ---------------------------------------------------------------------------
# 2. Pre-visit summary (doctor)
# ---------------------------------------------------------------------------

@role_required("doctor")
def pre_visit_summary_view(request, appointment_id):
    """
    Read-only view of the SymptomForm for a given appointment.
    Shown to the doctor before the visit.
    """
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        doctor=request.user.doctor_profile,
    )
    symptom_form = getattr(appointment, "symptom_form", None)

    return render(request, "consultations/pre_visit_summary.html", {
        "appointment": appointment,
        "symptom_form": symptom_form,
    })


# ---------------------------------------------------------------------------
# 3. Post-visit note (doctor)
# ---------------------------------------------------------------------------

@role_required("doctor")
def post_visit_note_view(request, appointment_id):
    """
    GET: show the clinical notes / prescription form.
    POST: save notes, run post-visit LLM, mark appointment completed.
    """
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        doctor=request.user.doctor_profile,
    )

    # Don't allow re-entry if note already exists
    if hasattr(appointment, "post_visit_note"):
        messages.info(request, "Post-visit notes already submitted.")
        return redirect("appointments:doctor_appointments")

    if appointment.status not in (Appointment.Status.CONFIRMED, Appointment.Status.HELD):
        messages.warning(
            request,
            "This appointment cannot accept post-visit notes "
            f"(status: {appointment.get_status_display()}).",
        )
        return redirect("appointments:doctor_appointments")

    if request.method == "POST":
        clinical_notes = request.POST.get("clinical_notes", "").strip()
        prescription_text = request.POST.get("prescription_text", "").strip()

        if not clinical_notes:
            messages.error(request, "Clinical notes are required.")
            return render(request, "consultations/post_visit_note.html", {
                "appointment": appointment,
            })

        # Parse medications from the repeatable form rows
        medications = _parse_medications_from_post(request.POST)

        # Create the PostVisitNote
        note = PostVisitNote(
            appointment=appointment,
            clinical_notes=clinical_notes,
            prescription_text=prescription_text,
            medications=medications,
        )

        # LLM post-visit summary — failure is OK
        try:
            result = generate_post_visit_summary(clinical_notes, prescription_text)
            note.patient_summary = result.get("patient_summary", "")
            note.follow_up_steps = result.get("follow_up_steps", "")
            # If LLM returns medications, merge/replace
            llm_meds = result.get("medications")
            if llm_meds and isinstance(llm_meds, list):
                note.medications = llm_meds
            note.llm_status = PostVisitNote.LLMStatus.SUCCESS
        except LLMGenerationError as exc:
            logger.warning("Post-visit LLM failed for appointment %s: %s", appointment.pk, exc)
            note.llm_status = PostVisitNote.LLMStatus.FAILED
            messages.warning(
                request,
                "AI-powered patient summary is temporarily unavailable. "
                "The notes have been saved as-is.",
            )

        note.save()

        # Mark appointment as completed
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status", "updated_at"])

        messages.success(request, "Post-visit notes saved. Appointment marked as completed.")
        return redirect("appointments:doctor_appointments")

    # GET
    return render(request, "consultations/post_visit_note.html", {
        "appointment": appointment,
    })


def _parse_medications_from_post(post_data) -> list[dict]:
    """
    Parse the repeatable medication rows from POST data.

    The template submits arrays: med_name[], med_dosage[], med_frequency[],
    med_duration[].
    """
    names = post_data.getlist("med_name")
    dosages = post_data.getlist("med_dosage")
    frequencies = post_data.getlist("med_frequency")
    durations = post_data.getlist("med_duration")

    medications = []
    for i, name in enumerate(names):
        name = name.strip()
        if not name:
            continue
        medications.append({
            "name": name,
            "dosage": dosages[i].strip() if i < len(dosages) else "",
            "frequency": frequencies[i].strip() if i < len(frequencies) else "",
            "duration_days": _safe_int(durations[i]) if i < len(durations) else 0,
        })
    return medications


def _safe_int(val: str, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# 4. Patient post-visit summary (patient)
# ---------------------------------------------------------------------------

@role_required("patient")
def patient_post_visit_summary_view(request, appointment_id):
    """
    Read-only view of the patient-friendly summary, medications, and
    follow-up steps for a completed appointment.
    """
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        patient=request.user,
    )
    note = getattr(appointment, "post_visit_note", None)

    return render(request, "consultations/patient_post_visit_summary.html", {
        "appointment": appointment,
        "note": note,
    })
