from urllib.parse import urlsplit
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.crypto import blind_index
from app.storage import R2WorkerStorage
from app.validators import MAX_IMAGE_UPLOAD_SIZE, validate_image_upload

from .models import AuthenticationThrottle, Profile, validate_cnpj, validate_cpf
from .views import EMAIL_VERIFICATION_SALT


User = get_user_model()


class DocumentValidationTests(TestCase):
    def test_valid_documents(self):
        validate_cpf('529.982.247-25')
        validate_cnpj('11.222.333/0001-81')

    def test_invalid_documents(self):
        with self.assertRaises(ValidationError):
            validate_cpf('111.111.111-11')
        with self.assertRaises(ValidationError):
            validate_cnpj('11.111.111/1111-11')


class UploadSecurityTests(TestCase):
    def test_rejects_non_image_even_with_allowed_name_and_mime_type(self):
        upload = SimpleUploadedFile(
            'avatar.jpg',
            b'<html><script>alert(1)</script></html>',
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            validate_image_upload(upload)

    def test_rejects_oversized_image_before_processing_it(self):
        upload = SimpleUploadedFile(
            'avatar.jpg',
            b'x' * (MAX_IMAGE_UPLOAD_SIZE + 1),
            content_type='image/jpeg',
        )

        with self.assertRaisesMessage(ValidationError, 'no máximo 5 MB'):
            validate_image_upload(upload)

    def test_media_storage_only_accepts_private_worker_endpoint(self):
        self.assertEqual(
            R2WorkerStorage('http://media.internal').endpoint,
            'http://media.internal',
        )
        for unsafe_endpoint in (
            'file:///etc/passwd',
            'https://media.internal',
            'http://media.internal.example.com',
            'http://user:password@media.internal',
        ):
            with self.subTest(endpoint=unsafe_endpoint), self.assertRaises(ValueError):
                R2WorkerStorage(unsafe_endpoint)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_DELIVERY_ENABLED=True,
)
class AccountViewsTests(TestCase):
    password = 'Senha-Forte-2026'

    def create_account(self, account_type='PF', document='52998224725', email='cliente@example.com'):
        user = User.objects.create_user(
            username=f'test-account-{User.objects.count()}',
            email='',
            password=self.password,
        )
        profile = Profile.objects.create(
            user=user,
            account_type=account_type,
            document=document,
            email=email,
        )
        return user, profile

    def test_register_creates_account_with_hashed_password(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'account_type': 'PF',
                'document': '529.982.247-25',
                'email': 'CLIENTE@example.com',
                'password': self.password,
                'password_confirmation': self.password,
            },
        )

        self.assertRedirects(response, reverse('accounts:login'))
        profile = Profile.objects.get(
            document_hash=blind_index('52998224725', 'profile.document')
        )
        self.assertEqual(profile.email, 'cliente@example.com')
        self.assertNotEqual(profile.user.username, profile.document)
        self.assertEqual(profile.user.email, '')
        self.assertTrue(profile.user.check_password(self.password))
        self.assertFalse(profile.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_register_rejects_different_password_confirmation(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'account_type': 'PF',
                'document': '529.982.247-25',
                'email': 'cliente@example.com',
                'password': self.password,
                'password_confirmation': 'Outra-Senha-2026',
            },
        )

        self.assertContains(response, 'As senhas não coincidem.')
        self.assertFalse(Profile.objects.exists())

    def test_rejects_document_that_does_not_match_account_type(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'account_type': 'PJ',
                'document': '529.982.247-25',
                'email': 'cliente@example.com',
                'password': self.password,
                'password_confirmation': self.password,
            },
        )

        self.assertContains(response, 'Informe um CNPJ válido.')
        self.assertFalse(Profile.objects.exists())

    def test_login_with_cpf_or_cnpj_and_rejects_email(self):
        self.create_account()

        email_response = self.client.post(
            reverse('accounts:login'),
            {'identifier': 'cliente@example.com', 'password': self.password},
        )
        self.assertEqual(email_response.status_code, 200)
        self.assertContains(
            email_response,
            'E-mail não é aceito no login. Use seu CPF ou CNPJ.',
        )
        self.assertNotIn('_auth_user_id', self.client.session)

        cpf_response = self.client.post(
            reverse('accounts:login'),
            {'identifier': '529.982.247-25', 'password': self.password},
        )
        self.assertRedirects(cpf_response, reverse('accounts:profile'))
        self.client.post(reverse('accounts:logout'))

        self.create_account('PJ', '11222333000181', 'empresa@example.com')
        response = self.client.post(
            reverse('accounts:login'),
            {'identifier': '11.222.333/0001-81', 'password': self.password},
        )
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_admin_can_authenticate_with_username(self):
        admin = User.objects.create_superuser(
            username='MayezerS',
            email='admin@example.com',
            password=self.password,
        )

        authenticated_user = authenticate(
            username='MayezerS',
            password=self.password,
        )

        self.assertEqual(authenticated_user, admin)
        self.assertTrue(authenticated_user.is_staff)

    def test_admin_without_customer_profile_is_sent_to_admin_panel(self):
        admin = User.objects.create_superuser(
            username='admin-without-profile',
            email='admin-without-profile@example.com',
            password=self.password,
        )
        self.client.force_login(admin)

        profile_response = self.client.get(reverse('accounts:profile'))
        register_response = self.client.get(reverse('accounts:register'))

        self.assertRedirects(profile_response, reverse('dashboard:home'))
        self.assertRedirects(register_response, reverse('dashboard:home'))

    def test_admin_login_from_customer_page_is_sent_to_admin_panel(self):
        User.objects.create_superuser(
            username='admin-login-redirect',
            email='admin-login-redirect@example.com',
            password=self.password,
        )

        response = self.client.post(
            reverse('accounts:login'),
            {
                'identifier': 'admin-login-redirect',
                'password': self.password,
            },
        )

        self.assertRedirects(response, reverse('dashboard:home'))

    def test_regular_user_without_profile_is_logged_out_safely(self):
        user = User.objects.create_user(
            username='orphan-customer',
            email='orphan@example.com',
            password=self.password,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:profile'), follow=True)

        self.assertRedirects(response, reverse('accounts:login'))
        self.assertContains(response, 'Não encontramos os dados do seu perfil.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
        )

    def test_user_can_edit_profile(self):
        user, profile = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')

        response = self.client.post(
            reverse('accounts:edit_profile'),
            {
                'full_name': 'Maria da Silva',
                'corporate_name': 'Não deve permanecer',
                'street': 'Rua das Flores',
                'neighborhood': 'Centro',
                'house_number': '10A',
                'reference_point': 'Próximo à praça',
                'phone': '(11) 99999-9999',
            },
        )

        self.assertRedirects(response, reverse('accounts:profile'))
        profile.refresh_from_db()
        self.assertEqual(profile.full_name, 'Maria da Silva')
        self.assertEqual(profile.phone, '11999999999')
        self.assertEqual(profile.formatted_phone, '(11) 99999 - 9999')
        self.assertEqual(profile.corporate_name, '')

        profile_response = self.client.get(reverse('accounts:profile'))
        self.assertContains(profile_response, 'CPF:')
        self.assertNotContains(profile_response, 'CPF ou CNPJ')
        self.assertContains(profile_response, '***.982.247-**')
        self.assertContains(profile_response, '(11) 99999 - 9999')
        self.assertContains(profile_response, '<a class="brand" href="/">', html=False)
        self.assertNotContains(profile_response, 'aria-label="Meu perfil"')
        self.assertNotContains(profile_response, 'aria-label="Sair da conta"')
        self.assertEqual(
            profile_response.content.decode().count(
                f'href="{reverse("dashboard:request_quote")}"'
            ),
            1,
        )
        self.assertEqual(
            profile_response.content.decode().count(
                f'action="{reverse("accounts:logout")}"'
            ),
            1,
        )

    def test_profile_can_resend_and_confirm_email(self):
        user, profile = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')

        profile_response = self.client.get(reverse('accounts:profile'))
        self.assertContains(profile_response, 'E-mail não confirmado.')

        resend_response = self.client.post(reverse('accounts:resend_email_verification'))
        self.assertRedirects(resend_response, reverse('accounts:profile'))
        self.assertEqual(len(mail.outbox), 1)

        confirmation_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith('http')
        )
        confirmation_path = urlsplit(confirmation_url).path
        token = confirmation_path.rstrip('/').split('/')[-1]
        token_payload = signing.loads(token, salt=EMAIL_VERIFICATION_SALT)
        self.assertEqual(token_payload['profile_id'], profile.pk)
        self.assertNotIn('email', token_payload)

        confirmation_response = self.client.get(confirmation_path)

        self.assertRedirects(confirmation_response, reverse('accounts:profile'))
        profile.refresh_from_db()
        self.assertTrue(profile.is_email_verified)

    def test_email_confirmation_token_is_invalid_after_address_change(self):
        user, profile = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')
        self.client.post(reverse('accounts:resend_email_verification'))
        confirmation_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith('http')
        )

        profile.email = 'novo-endereco@example.com'
        profile.save(update_fields=('email',))
        response = self.client.get(urlsplit(confirmation_url).path)

        self.assertRedirects(response, reverse('accounts:profile'))
        profile.refresh_from_db()
        self.assertFalse(profile.is_email_verified)

    def test_email_confirmation_token_cannot_be_reused(self):
        user, profile = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')
        self.client.post(reverse('accounts:resend_email_verification'))
        confirmation_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith('http')
        )
        confirmation_path = urlsplit(confirmation_url).path

        first = self.client.get(confirmation_path)
        second = self.client.get(confirmation_path, follow=True)

        self.assertRedirects(first, reverse('accounts:profile'))
        self.assertContains(second, 'inválido ou expirou')
        profile.refresh_from_db()
        self.assertTrue(profile.is_email_verified)

    def test_expired_and_tampered_email_tokens_are_rejected_generically(self):
        user, _ = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')
        self.client.post(reverse('accounts:resend_email_verification'))
        confirmation_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith('http')
        )
        confirmation_path = urlsplit(confirmation_url).path

        with patch('accounts.views.EMAIL_VERIFICATION_MAX_AGE', -1):
            expired = self.client.get(confirmation_path, follow=True)
        token_path = confirmation_path.rstrip('/')
        replacement = 'a' if token_path[-1] != 'a' else 'b'
        tampered = self.client.get(f'{token_path[:-1]}{replacement}/', follow=True)

        self.assertContains(expired, 'inválido ou expirou')
        self.assertContains(tampered, 'inválido ou expirou')

    def test_resend_email_verification_only_accepts_post(self):
        user, _ = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')

        response = self.client.get(reverse('accounts:resend_email_verification'))

        self.assertEqual(response.status_code, 405)

    def test_logout_and_delete_only_accept_post(self):
        user, _ = self.create_account()
        self.client.force_login(user, backend='accounts.backends.DocumentBackend')

        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        self.assertEqual(self.client.get(reverse('accounts:delete_account')).status_code, 405)
        response = self.client.post(reverse('accounts:delete_account'))

        self.assertRedirects(response, reverse('accounts:register'))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EnumerationAndThrottleTests(TestCase):
    password = 'Senha-Forte-2026'

    def registration_payload(self, document='52998224725', email='cliente@example.com'):
        return {
            'account_type': 'PF',
            'document': document,
            'email': email,
            'password': self.password,
            'password_confirmation': self.password,
        }

    def test_registration_uses_same_public_result_for_existing_identity(self):
        first = self.client.post(reverse('accounts:register'), self.registration_payload())
        first_message = list(first.wsgi_request._messages)[0].message
        count = Profile.objects.count()

        duplicate = self.client.post(
            reverse('accounts:register'),
            self.registration_payload(email='outro@example.com'),
        )
        duplicate_message = list(duplicate.wsgi_request._messages)[0].message

        self.assertRedirects(first, reverse('accounts:login'))
        self.assertRedirects(duplicate, reverse('accounts:login'))
        self.assertEqual(first_message, duplicate_message)
        self.assertEqual(Profile.objects.count(), count)
        self.assertNotIn('já existe', duplicate_message.casefold())

    @override_settings(
        AUTH_LOCKOUT_THRESHOLD=3,
        AUTH_LOCKOUT_BASE_SECONDS=30,
        AUTH_LOCKOUT_MAX_SECONDS=120,
        AUTH_LOCKOUT_RESET_SECONDS=3600,
    )
    def test_account_lockout_survives_ip_changes_expires_and_success_resets(self):
        self.client.post(reverse('accounts:register'), self.registration_payload())
        base_time = timezone.now()
        for index in range(3):
            with patch('accounts.security.timezone.now', return_value=base_time):
                response = self.client.post(
                    reverse('accounts:login'),
                    {'identifier': '52998224725', 'password': 'senha-incorreta'},
                    REMOTE_ADDR=f'203.0.113.{index + 1}',
                )
            self.assertEqual(response.status_code, 200)

        throttle = AuthenticationThrottle.objects.get(
            scope=AuthenticationThrottle.Scope.CUSTOMER
        )
        self.assertGreater(throttle.blocked_until, base_time)

        with patch(
            'accounts.security.timezone.now',
            return_value=base_time + timedelta(seconds=31),
        ):
            success = self.client.post(
                reverse('accounts:login'),
                {'identifier': '52998224725', 'password': self.password},
                REMOTE_ADDR='198.51.100.50',
            )
        self.assertRedirects(success, reverse('accounts:profile'))
        self.assertFalse(AuthenticationThrottle.objects.exists())

    def test_customer_and_admin_throttles_use_separate_scopes(self):
        admin = User.objects.create_superuser(
            username='gestor-seguro', email='gestor@example.com', password=self.password
        )
        self.client.post(
            reverse('accounts:login'),
            {'identifier': 'gestor-seguro', 'password': 'incorreta'},
        )
        self.client.post(
            reverse('admin:login'),
            {'username': admin.username, 'password': 'incorreta', 'next': reverse('admin:index')},
        )
        self.assertEqual(
            set(AuthenticationThrottle.objects.values_list('scope', flat=True)),
            {
                AuthenticationThrottle.Scope.CUSTOMER,
                AuthenticationThrottle.Scope.ADMIN,
            },
        )
