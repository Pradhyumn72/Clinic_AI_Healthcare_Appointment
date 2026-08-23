"""
accounts/forms.py
Forms for the accounts app.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


def _text_input(placeholder="", **extra):
    attrs = {"placeholder": placeholder, **extra}
    return forms.TextInput(attrs=attrs)


def _email_input(placeholder=""):
    return forms.EmailInput(attrs={"placeholder": placeholder})


def _password_input(placeholder=""):
    return forms.PasswordInput(attrs={"placeholder": placeholder})


class PatientRegistrationForm(UserCreationForm):
    """
    Registration form for new patients.

    The role is forced to 'patient' — doctors are created by admins only.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="First name",
        widget=_text_input("Jane"),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Last name",
        widget=_text_input("Doe"),
    )
    email = forms.EmailField(
        required=True,
        label="Email address",
        widget=_email_input("you@example.com"),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        label="Phone number",
        widget=_text_input("+1 555 000 0000"),
        help_text="Optional",
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "password1",
            "password2",
        )
        widgets = {
            "username": _text_input("your_username"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style the password fields added by UserCreationForm
        self.fields["password1"].widget = _password_input("••••••••")
        self.fields["password2"].widget = _password_input("••••••••")

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = User.Role.PATIENT  # force patient role regardless of POST data
        user.phone_number = self.cleaned_data.get("phone_number", "")
        user.date_of_birth = self.cleaned_data.get("date_of_birth")
        if commit:
            user.save()
        return user
