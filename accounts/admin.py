from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Extends the built-in UserAdmin to expose the clinic-specific fields
    in the Django admin interface.
    """

    # Add clinic fields to the detail view
    fieldsets = UserAdmin.fieldsets + (
        (
            "Clinic Profile",
            {
                "fields": ("role", "phone_number", "date_of_birth"),
            },
        ),
    )

    # Also show them when creating a new user via admin
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Clinic Profile",
            {
                "classes": ("wide",),
                "fields": ("role", "phone_number", "date_of_birth"),
            },
        ),
    )

    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)
    search_fields = UserAdmin.search_fields + ("phone_number",)
