from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from app.crypto import blind_index

from .models import AuthenticationThrottle, only_digits, normalize_text


GENERIC_LOGIN_ERROR = 'Identificador ou senha inválidos. Tente novamente mais tarde.'


def normalize_login_identifier(identifier, scope):
    value = (identifier or '').strip()
    if scope == AuthenticationThrottle.Scope.CUSTOMER:
        digits = only_digits(value)
        return digits if digits else normalize_text(value)
    digits = only_digits(value)
    return digits if len(digits) in {11, 14} else normalize_text(value)


def identifier_digest(identifier, scope):
    normalized = normalize_login_identifier(identifier, scope)
    return blind_index(normalized or '<empty>', f'auth-throttle.{scope}')


@transaction.atomic
def login_attempt_allowed(identifier, scope, now=None):
    now = now or timezone.now()
    digest = identifier_digest(identifier, scope)
    throttle = (
        AuthenticationThrottle.objects.select_for_update()
        .filter(scope=scope, identifier_digest=digest)
        .first()
    )
    if throttle is None:
        return True
    if (
        throttle.last_failed_at
        and throttle.last_failed_at
        < now - timedelta(seconds=settings.AUTH_LOCKOUT_RESET_SECONDS)
    ):
        throttle.delete()
        return True
    if throttle.blocked_until and throttle.blocked_until > now:
        return False
    if throttle.blocked_until:
        throttle.blocked_until = None
        throttle.save(update_fields=('blocked_until', 'updated_at'))
    return True


@transaction.atomic
def record_login_failure(identifier, scope, now=None):
    now = now or timezone.now()
    digest = identifier_digest(identifier, scope)
    throttle, _ = AuthenticationThrottle.objects.select_for_update().get_or_create(
        scope=scope,
        identifier_digest=digest,
    )
    if (
        throttle.last_failed_at
        and throttle.last_failed_at
        < now - timedelta(seconds=settings.AUTH_LOCKOUT_RESET_SECONDS)
    ):
        throttle.failed_attempts = 0
        throttle.blocked_until = None
    throttle.failed_attempts += 1
    throttle.last_failed_at = now
    if throttle.failed_attempts >= settings.AUTH_LOCKOUT_THRESHOLD:
        exponent = min(throttle.failed_attempts - settings.AUTH_LOCKOUT_THRESHOLD, 8)
        duration = min(
            settings.AUTH_LOCKOUT_BASE_SECONDS * (2**exponent),
            settings.AUTH_LOCKOUT_MAX_SECONDS,
        )
        throttle.blocked_until = now + timedelta(seconds=duration)
    throttle.save()
    return throttle


def record_login_success(identifier, scope):
    AuthenticationThrottle.objects.filter(
        scope=scope,
        identifier_digest=identifier_digest(identifier, scope),
    ).delete()
