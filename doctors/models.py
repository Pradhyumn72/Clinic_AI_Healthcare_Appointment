"""
doctors/models.py
Models for doctor profile management.
"""

import datetime

from django.conf import settings
from django.db import models


class DoctorProfile(models.Model):
    """
    Extended profile for a user with role='doctor'.

    Working days are stored as a comma-separated string of weekday integers
    (0 = Monday … 6 = Sunday) to keep the schema simple and avoid a
    junction table for a small, rarely-changing value.
    """

    WEEKDAY_CHOICES = [
        ("0", "Monday"),
        ("1", "Tuesday"),
        ("2", "Wednesday"),
        ("3", "Thursday"),
        ("4", "Friday"),
        ("5", "Saturday"),
        ("6", "Sunday"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_profile",
        limit_choices_to={"role": "doctor"},
        verbose_name="Doctor user account",
    )
    specialisation = models.CharField(max_length=120)
    working_hours_start = models.TimeField(
        default=datetime.time(9, 0),
        verbose_name="Working hours start",
    )
    working_hours_end = models.TimeField(
        default=datetime.time(17, 0),
        verbose_name="Working hours end",
    )
    slot_duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Duration of each appointment slot in minutes.",
    )
    # e.g. "0,1,2,3,4" = Mon-Fri
    working_days = models.CharField(
        max_length=20,
        default="0,1,2,3,4",
        help_text="Comma-separated weekday numbers: 0=Mon, 1=Tue, …, 6=Sun.",
    )
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive doctors won't appear in the booking flow.",
    )

    class Meta:
        app_label = "doctors"
        verbose_name = "Doctor Profile"
        verbose_name_plural = "Doctor Profiles"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def working_day_list(self) -> list[int]:
        """Return working_days as a list of ints, e.g. [0, 1, 2, 3, 4]."""
        return [
            int(d.strip())
            for d in self.working_days.split(",")
            if d.strip().isdigit()
        ]

    def generate_slots(self, date: datetime.date) -> list[datetime.time]:
        """
        Return a list of slot-start times for *date* based on working hours
        and slot_duration_minutes.

        Returns an empty list if *date* falls on a non-working weekday.

        NOTE: this method does NOT subtract already-booked slots — that
        filtering is intentionally deferred to the appointments app.
        """
        if date.weekday() not in self.working_day_list():
            return []

        slots: list[datetime.time] = []
        current = datetime.datetime.combine(date, self.working_hours_start)
        end = datetime.datetime.combine(date, self.working_hours_end)
        delta = datetime.timedelta(minutes=self.slot_duration_minutes)

        while current + delta <= end:
            slots.append(current.time())
            current += delta

        return slots

    def __str__(self) -> str:
        name = self.user.get_full_name() or self.user.username
        return f"Dr. {name} — {self.specialisation}"


class Leave(models.Model):
    """
    A single day of leave for a doctor.

    The appointments app will attach a signal to this model (in a later step)
    to cancel / notify patients for any bookings on that date.
    """

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="leaves",
    )
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "doctors"
        verbose_name = "Leave Day"
        verbose_name_plural = "Leave Days"
        unique_together = [("doctor", "date")]
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.doctor} — {self.date}"
