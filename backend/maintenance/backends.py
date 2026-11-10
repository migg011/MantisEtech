"""Authentication backend compatible with the accounts created by the previous implementation."""

import bcrypt
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password

from .models import User


class RegistrationBackend(BaseBackend):
    """Authenticate by registration and migrate legacy bcrypt hashes after a valid login."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Find an active account by registration, check the password, and upgrade an old hash."""
        registration = username or kwargs.get('registration')
        try:
            user = User.objects.get(registration=registration, active=True)
        except User.DoesNotExist:
            make_password(password)
            return None
        if user.password.startswith(('$2a$', '$2b$', '$2y$')):
            try:
                password_valid = bcrypt.checkpw(password.encode()[:72], user.password.encode())
            except (ValueError, TypeError):
                password_valid = False
            if password_valid:
                user.set_password(password)
                user.save(update_fields=['password'])
                return user
        elif user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        """Recover an active account by ID for the Django authentication infrastructure."""
        return User.objects.filter(pk=user_id, active=True).first()


def authenticate_by_registration(registration: str, password: str) -> User | None:
    """Authenticate directly by registration and password, returning the user or ``None``."""
    try:
        user = User.objects.get(registration=registration, active=True)
    except User.DoesNotExist:
        return None
    if user.password.startswith(('$2a$', '$2b$', '$2y$')):
        try:
            if bcrypt.checkpw(password.encode()[:72], user.password.encode()):
                user.set_password(password)
                user.save(update_fields=['password'])
                return user
        except (ValueError, TypeError):
            return None
    elif user.check_password(password):
        return user
    return None


def get_user_from_request(request) -> User | None:
    """Return the authenticated user from the request, or ``None`` when unauthenticated."""
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user
    django_request = getattr(request, '_request', request)
    user_id = django_request.session.get('user_id') if hasattr(django_request, 'session') else None
    if user_id:
        try:
            return User.objects.get(pk=user_id, active=True)
        except User.DoesNotExist:
            pass
    return None
