"""
doctors/admin.py

Admin configuration for the doctors app.

Key design: DoctorProfileAdmin uses a custom ModelForm that embeds User
fields (username, first/last name, email, password) so an admin can create
both the User account (role="doctor") and the DoctorProfile in a single
form.  On the edit page those fields are hidden — the User itself can be
edited via the Accounts section of the admin.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils.html import format_html

from .models import DoctorProfile, Leave

User = get_user_model()


# ---------------------------------------------------------------------------
# Custom ModelForm — creates a User+Profile in one step
# ---------------------------------------------------------------------------

class DoctorProfileAdminForm(forms.ModelForm):
    """
    On the *add* page the form surfaces extra User fields so the admin can
    create the linked User account without leaving the page.
    On the *change* page those fields are suppressed (the user already exists
    and is editable via Accounts > Users).
    """

    # Extra User fields (only shown on creation)
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Required when creating a new doctor.",
    )
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text=(
            "Required when creating a new doctor. "
            "Leave blank on the edit page — change the password via "
            "Accounts → Users if needed."
        ),
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label="Confirm password",
    )

    class Meta:
        model = DoctorProfile
        fields = "__all__"
        help_texts = {
            "working_days": (
                "Comma-separated weekday numbers. "
                "0 = Monday, 1 = Tuesday, …, 6 = Sunday. "
                'Example: "0,1,2,3,4" for Mon–Fri.'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # Edit mode — hide user-creation fields, make `user` read-only
            for field in ("username", "first_name", "last_name", "email",
                          "password", "password_confirm"):
                self.fields[field].widget = forms.HiddenInput()
                self.fields[field].required = False
            self.fields["user"].help_text = (
                "To change user details go to Accounts → Users."
            )
        else:
            # Add mode — hide the FK picker; we create the User ourselves
            self.fields["user"].widget = forms.HiddenInput()
            self.fields["user"].required = False
            # Username is required in add mode
            self.fields["username"].required = True
            self.fields["password"].required = True
            self.fields["password_confirm"].required = True

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            # Validate password match on creation
            pw1 = cleaned.get("password", "")
            pw2 = cleaned.get("password_confirm", "")
            if pw1 and pw2 and pw1 != pw2:
                self.add_error("password_confirm", "Passwords do not match.")

            username = cleaned.get("username", "")
            if username and User.objects.filter(username=username).exists():
                self.add_error("username", "A user with that username already exists.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)

        if not self.instance.pk:
            # Create the User account with role="doctor"
            user = User(
                username=self.cleaned_data["username"],
                first_name=self.cleaned_data.get("first_name", ""),
                last_name=self.cleaned_data.get("last_name", ""),
                email=self.cleaned_data.get("email", ""),
                role=User.Role.DOCTOR,
                is_staff=False,
            )
            user.password = make_password(self.cleaned_data["password"])
            user.save()
            profile.user = user

        if commit:
            profile.save()
        return profile


# ---------------------------------------------------------------------------
# Inline: Leave days shown inside DoctorProfile change page
# ---------------------------------------------------------------------------

class LeaveInline(admin.TabularInline):
    model = Leave
    extra = 1
    fields = ("date", "reason")
    ordering = ("date",)


# ---------------------------------------------------------------------------
# DoctorProfileAdmin
# ---------------------------------------------------------------------------

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    form = DoctorProfileAdminForm
    inlines = [LeaveInline]

    list_display = (
        "doctor_full_name",
        "specialisation",
        "working_hours_display",
        "slot_duration_minutes",
        "working_days",
        "is_active",
    )
    list_filter = ("is_active", "specialisation")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "specialisation",
    )
    list_editable = ("is_active",)

    # Field layout on the add/change form
    fieldsets = (
        (
            "👤 New Doctor User Account",
            {
                "fields": (
                    "username",
                    ("first_name", "last_name"),
                    "email",
                    ("password", "password_confirm"),
                ),
                "description": (
                    "<strong>Fill these fields only when creating a new doctor.</strong> "
                    "On the edit page these are hidden — manage the user account "
                    "via <em>Accounts → Users</em>."
                ),
                "classes": ("wide",),
            },
        ),
        (
            "🔗 Linked Account (edit mode)",
            {
                "fields": ("user",),
                "classes": ("wide",),
            },
        ),
        (
            "📋 Professional Details",
            {
                "fields": ("specialisation", "bio", "is_active"),
                "classes": ("wide",),
            },
        ),
        (
            "🕐 Scheduling",
            {
                "fields": (
                    ("working_hours_start", "working_hours_end"),
                    "slot_duration_minutes",
                    "working_days",
                ),
                "classes": ("wide",),
            },
        ),
    )

    # ------------------------------------------------------------------
    # Custom list_display helpers
    # ------------------------------------------------------------------

    @admin.display(description="Doctor", ordering="user__last_name")
    def doctor_full_name(self, obj: DoctorProfile) -> str:
        name = obj.user.get_full_name() or obj.user.username
        return f"Dr. {name}"

    @admin.display(description="Working hours")
    def working_hours_display(self, obj: DoctorProfile) -> str:
        return format_html(
            "{} – {}",
            obj.working_hours_start.strftime("%H:%M"),
            obj.working_hours_end.strftime("%H:%M"),
        )


# ---------------------------------------------------------------------------
# LeaveAdmin
# ---------------------------------------------------------------------------

@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "reason", "created_at")
    list_filter = ("doctor",)
    search_fields = (
        "doctor__user__username",
        "doctor__user__first_name",
        "doctor__user__last_name",
        "reason",
    )
    date_hierarchy = "date"
    ordering = ("-date",)
