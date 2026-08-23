"""
appointments/services.py
Core booking-engine logic for the clinic platform.

How two simultaneous booking requests for the same slot are handled
====================================================================

Imagine Patient A and Patient B both click "Book" for Dr. Smith's 10:00 slot
at nearly the same instant.  Two safety nets prevent a double-booking:

1. **Pessimistic row-level lock (``select_for_update``)**

   ``hold_slot()`` runs inside ``transaction.atomic()``.  Before creating the
   new ``Appointment`` row it executes a SELECT … FOR UPDATE against any
   *existing* active appointments for that (doctor, date, start_time).
   Whichever request's transaction hits the database first acquires an
   exclusive row-level lock (or, if no rows exist yet, the serialised
   transaction ordering ensures only one proceeds at a time on databases that
   support predicate locks — SQLite serialises anyway since it is
   single-writer).  The second transaction blocks until the first commits.

   When the second request's transaction finally acquires the lock it re-checks
   availability.  If the first request already inserted a row, the second sees
   it and raises ``SlotUnavailableError`` *without* attempting an INSERT.

2. **Partial unique constraint (database backstop)**

   ``Appointment.Meta.constraints`` includes a ``UniqueConstraint`` on
   (doctor, date, start_time) filtered to ``status ∈ {held, confirmed}``.
   Even if a bug or an exotic race condition somehow bypasses the
   application-level lock, the database will reject the second INSERT with an
   ``IntegrityError``.  ``hold_slot()`` catches this specific error and
   re-raises it as ``SlotUnavailableError`` so callers never see a raw 500.

Together these two layers provide both *correctness* (no double-booking is
possible) and *good user experience* (the second patient gets a clean error
message rather than a 500 page).
"""

import datetime
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from doctors.models import DoctorProfile, Leave

from .models import Appointment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class SlotUnavailableError(Exception):
    """Raised when a slot is already taken or no longer available."""


class DoctorOnLeaveError(SlotUnavailableError):
    """Raised when the doctor is on leave for the requested date."""


# ---------------------------------------------------------------------------
# Expired-hold cleanup
# ---------------------------------------------------------------------------

def release_expired_holds() -> int:
    """
    Delete Appointment rows whose hold has expired (status='held' and
    hold_expires_at < now).  Returns the count of released rows.

    Called at the top of ``get_available_slots()`` so stale holds don't block
    slots from appearing as available, and can also be invoked from a periodic
    management command / celery beat task.
    """
    now = timezone.now()
    expired = Appointment.objects.filter(
        status=Appointment.Status.HELD,
        hold_expires_at__lt=now,
    )
    count, _ = expired.delete()
    if count:
        logger.info("Released %d expired slot hold(s).", count)
    return count


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def get_available_slots(
    doctor_profile: DoctorProfile,
    date: datetime.date,
) -> list[datetime.time]:
    """
    Return a list of genuinely free slot-start times for *doctor_profile* on
    *date*.

    Steps:
    1. Release any expired holds so they don't block slots.
    2. If the doctor has a Leave record for *date* → return [].
    3. Generate all possible slots from the doctor's schedule.
    4. Subtract slots that already have an active (held/confirmed) Appointment.
    """
    # 1. Housekeeping
    release_expired_holds()

    # 2. Leave check
    if Leave.objects.filter(doctor=doctor_profile, date=date).exists():
        return []

    # 3. All possible slots from the doctor's timetable
    all_slots = doctor_profile.generate_slots(date)
    if not all_slots:
        return []

    # 4. Subtract booked/held slots
    booked_times = set(
        Appointment.objects.filter(
            doctor=doctor_profile,
            date=date,
            status__in=Appointment.ACTIVE_STATUSES,
        ).values_list("start_time", flat=True)
    )

    return [t for t in all_slots if t not in booked_times]


# ---------------------------------------------------------------------------
# Slot hold (the critical concurrency section)
# ---------------------------------------------------------------------------

def hold_slot(
    patient,
    doctor_profile: DoctorProfile,
    date: datetime.date,
    start_time: datetime.time,
) -> Appointment:
    """
    Atomically create a held appointment for *patient* on the given slot.

    Raises ``SlotUnavailableError`` if the slot is already taken or the
    doctor is on leave.
    """
    # Quick pre-checks (no lock yet, just for fast-fail UX)
    if Leave.objects.filter(doctor=doctor_profile, date=date).exists():
        raise DoctorOnLeaveError(
            f"Dr. {doctor_profile.user.get_full_name()} is on leave on {date}."
        )

    # Compute end_time from the doctor's slot duration
    start_dt = datetime.datetime.combine(date, start_time)
    end_dt = start_dt + datetime.timedelta(minutes=doctor_profile.slot_duration_minutes)
    end_time = end_dt.time()

    hold_minutes = getattr(settings, "SLOT_HOLD_MINUTES", 5)

    try:
        with transaction.atomic():
            # Acquire an exclusive lock on any existing active row for this
            # slot.  On PostgreSQL this is a true row-level lock; on SQLite
            # the entire database is locked for the duration of the write
            # transaction, which gives us the same serialisation guarantee.
            existing = (
                Appointment.objects
                .select_for_update()
                .filter(
                    doctor=doctor_profile,
                    date=date,
                    start_time=start_time,
                    status__in=Appointment.ACTIVE_STATUSES,
                )
            )

            # Release any expired holds we find under the lock
            now = timezone.now()
            expired = existing.filter(
                status=Appointment.Status.HELD,
                hold_expires_at__lt=now,
            )
            expired.delete()

            # Re-check: is there still an active booking?
            if existing.filter(status__in=Appointment.ACTIVE_STATUSES).exists():
                raise SlotUnavailableError(
                    f"The {start_time:%H:%M} slot with "
                    f"Dr. {doctor_profile.user.get_full_name()} on {date} "
                    f"is no longer available."
                )

            # Verify the slot is actually valid for this doctor's schedule
            valid_slots = doctor_profile.generate_slots(date)
            if start_time not in valid_slots:
                raise SlotUnavailableError(
                    f"{start_time:%H:%M} is not a valid appointment slot for "
                    f"Dr. {doctor_profile.user.get_full_name()} on {date}."
                )

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor_profile,
                date=date,
                start_time=start_time,
                end_time=end_time,
                status=Appointment.Status.HELD,
                hold_expires_at=now + datetime.timedelta(minutes=hold_minutes),
            )

    except IntegrityError:
        # The partial unique constraint caught a race we didn't prevent at
        # the application level — convert to a clean error.
        logger.warning(
            "UniqueConstraint backstop caught a double-book attempt for "
            "doctor=%s date=%s start_time=%s",
            doctor_profile.pk,
            date,
            start_time,
        )
        raise SlotUnavailableError(
            f"The {start_time:%H:%M} slot with "
            f"Dr. {doctor_profile.user.get_full_name()} on {date} "
            f"was just booked by another patient."
        )

    return appointment


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

def confirm_appointment(appointment: Appointment) -> Appointment:
    """
    Transition an appointment from 'held' → 'confirmed'.

    Called by the consultations app after the patient submits the symptom form.
    """
    if appointment.status != Appointment.Status.HELD:
        raise ValueError(
            f"Cannot confirm appointment {appointment.pk}: "
            f"current status is '{appointment.get_status_display()}', expected 'Held'."
        )
    appointment.status = Appointment.Status.CONFIRMED
    appointment.hold_expires_at = None
    appointment.save(update_fields=["status", "hold_expires_at", "updated_at"])
    return appointment
