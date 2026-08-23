from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for the clinic platform.

    Extends AbstractUser with a role field and healthcare-specific fields.
    Doctors are created by admins only; patients self-register.
    """

    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.PATIENT,
    )
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "accounts"

    # ------------------------------------------------------------------
    # Convenience role-check properties
    # ------------------------------------------------------------------

    @property
    def is_patient(self) -> bool:
        return self.role == self.Role.PATIENT

    @property
    def is_doctor_role(self) -> bool:
        return self.role == self.Role.DOCTOR

    @property
    def is_admin_role(self) -> bool:
        """True for users with the admin role *and* for Django superusers."""
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.role})"
