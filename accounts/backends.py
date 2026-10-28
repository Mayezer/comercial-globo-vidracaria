from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from .models import Profile, only_digits
from app.crypto import blind_index


User = get_user_model()


class DocumentBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None

        document = only_digits(username)
        profile = Profile.objects.select_related('user').filter(
            document_hash=blind_index(document, 'profile.document')
        ).first()
        user = profile.user if profile else None

        if user is None:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


class DocumentOrEmailBackend(DocumentBackend):
    """Compatibilidade com sessões antigas; e-mail não é mais aceito no login."""
