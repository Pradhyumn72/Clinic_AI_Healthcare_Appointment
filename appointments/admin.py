"""
appointments/admin.py
Admin configuration for the appointments app.
"""

from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "doctor",
        "date",
        "start_time",
        "end_time",
        "status",
        "hold_expires_at",
        "created_at",
    )
    list_filter = ("status", "date", "doctor")
    search_fields = (
        "patient__username",
        "patient__first_name",
        "patient__last_name",
        "doctor__user__username",
        "doctor__user__first_name",
        "doctor__user__last_name",
    )
    date_hierarchy = "date"
    ordering = ("-date", "-start_time")
    readonly_fields = ("created_at", "updated_at")
