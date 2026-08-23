"""
appointments/models.py
Models for the appointment booking system.
"""

import datetime

from django.conf import settings
from django.db import models
from django.db.models import Q

from doctors.models import DoctorProfile


class Appointment(models.Model):
    """
    A single appointment slot linking a patient to a doctor on a specific
    date/time.

    Lifecycle:  held → confirmed → completed
                held → cancelled  (patient/doctor cancelled, or hold expired)
                confirmed → cancelled
                confirmed/held → leave_cancelled  (doctor filed leave)

    Double-booking prevention
    -------------------------
    Two mechanisms work together:

    1. **Application-level:** ``services.hold_slot()`` uses
       ``select_for_update()`` inside ``transaction.atomic()`` to serialise
       concurrent booking attempts for the same (doctor, date, start_time).

    2. **Database-level:** A partial ``UniqueConstraint`` on
       (doctor, date, start_time) filtered to status ∈ {held, confirmed}
       acts as the backstop.  Even if a race condition somehow bypasses the
       application lock, the DB rejects the second INSERT with an
       ``IntegrityError``, which the service layer catches and converts to
       ``SlotUnavailableError``.
    """

    class Status(models.TextChoices):
        HELD = "held", "Held"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        LEAVE_CANCELLED = "leave_cancelled", "Leave Cancelled"

    # The status values that represent an "active" booking for a slot.
    ACTIVE_STATUSES = [Status.HELD, Status.CONFIRMED]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
        limit_choices_to={"role": "patient"},
    )
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.HELD,
    )
    hold_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Non-null while status is 'held'. After this time the hold "
                  "is considered expired and the slot can be reclaimed.",
    )

    # Google Calendar event IDs — populated by the calendar integration layer
    google_event_id_patient = models.CharField(max_length=255, blank=True)
    google_event_id_doctor = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "appointments"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                condition=Q(status__in=["held", "confirmed"]),
                name="unique_active_slot",
            ),
        ]

    def __str__(self) -> str:
        patient_name = self.patient.get_full_name() or self.patient.username
        return (
            f"{patient_name} → {self.doctor} "
            f"on {self.date} {self.start_time:%H:%M}–{self.end_time:%H:%M} "
            f"[{self.get_status_display()}]"
        )
