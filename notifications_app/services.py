"""
notifications_app/services.py
Email queueing service — STUB.

The real EmailLog model and send logic will be built in the next step.
This module exposes ``queue_email()`` so that other apps (consultations,
appointments) can call it now without import errors.
"""

import logging

logger = logging.getLogger(__name__)


def queue_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    related_appointment_id: int | None = None,
) -> None:
    """
    Queue an email for delivery.

    TODO (next step): persist to EmailLog and trigger actual sending.
    For now, logs the email to the console.
    """
    logger.info(
        "[STUB] queue_email → to=%s subject='%s' appointment=%s",
        to_email,
        subject,
        related_appointment_id,
    )
