"""
appointments/urls.py
URL patterns for the appointments app (namespace: "appointments").
"""

from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    # JSON API for the slot picker
    path(
        "api/slots/",
        views.available_slots_view,
        name="available_slots",
    ),

    # Doctor search & detail
    path("doctors/", views.doctor_search_view, name="doctor_search"),
    path(
        "doctors/<int:doctor_id>/",
        views.doctor_detail_view,
        name="doctor_detail",
    ),

    # Book a slot (POST)
    path("book/", views.book_slot_view, name="book_slot"),

    # Patient's appointment list
    path("mine/", views.my_appointments_view, name="my_appointments"),

    # Doctor's appointment list
    path("doctor/", views.doctor_appointments_view, name="doctor_appointments"),

    # Cancel an appointment (POST)
    path(
        "<int:appointment_id>/cancel/",
        views.cancel_appointment_view,
        name="cancel_appointment",
    ),
]
