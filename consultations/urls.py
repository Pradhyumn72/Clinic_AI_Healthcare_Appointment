"""
consultations/urls.py
URL patterns for the consultations app (namespace: "consultations").
"""

from django.urls import path

from . import views

app_name = "consultations"

urlpatterns = [
    # Patient: submit symptoms for a held appointment
    path(
        "symptom-form/<int:appointment_id>/",
        views.symptom_form_view,
        name="symptom_form",
    ),

    # Doctor: view pre-visit AI summary
    path(
        "pre-visit/<int:appointment_id>/",
        views.pre_visit_summary_view,
        name="pre_visit_summary",
    ),

    # Doctor: enter post-visit clinical notes
    path(
        "post-visit/<int:appointment_id>/",
        views.post_visit_note_view,
        name="post_visit_note",
    ),

    # Patient: view their post-visit summary
    path(
        "summary/<int:appointment_id>/",
        views.patient_post_visit_summary_view,
        name="patient_post_visit_summary",
    ),
]
