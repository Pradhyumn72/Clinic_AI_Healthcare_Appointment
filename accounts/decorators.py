"""
accounts/decorators.py
Role-based access control decorator for the clinic platform.
"""

import functools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """
    Decorator factory that restricts a view to users whose ``role`` is in
    *roles*.

    Usage::

        @role_required("doctor", "admin")
        def my_view(request):
            ...

    Behaviour:
    - Unauthenticated users are bounced to LOGIN_URL (via ``login_required``).
    - Django superusers are always allowed through, regardless of role.
    - Users with a matching role are allowed through.
    - Everyone else is redirected to the dashboard redirect with an error
      message.
    """

    def decorator(view_func):
        @login_required
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user

            # Superusers bypass all role checks
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            if user.role in roles:
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                "You do not have permission to access that page.",
            )
            return redirect("accounts:dashboard_redirect")

        return _wrapped

    return decorator
