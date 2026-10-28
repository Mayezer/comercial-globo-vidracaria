from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.utils.crypto import salted_hmac
from django.core.mail import send_mail
from django.urls import reverse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import AccountCreationForm, LoginForm, ProfileForm
from .models import Profile


EMAIL_VERIFICATION_SALT = 'accounts.email-verification'
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24


def email_fingerprint(email):
    return salted_hmac(
        'accounts.email-verification-address',
        email.strip().lower(),
    ).hexdigest()


def authenticated_landing(request):
    """Send administrators to the panel and customers to their profile."""
    if request.user.is_staff:
        return redirect('dashboard:home')

    if Profile.objects.filter(user=request.user).exists():
        return redirect('accounts:profile')

    auth_logout(request)
    messages.error(
        request,
        'Não encontramos os dados do seu perfil. Entre novamente ou crie uma conta.',
    )
    return redirect('accounts:login')


def customer_profile_or_redirect(request):
    """Return the customer profile or a safe response instead of raising a 404."""
    if request.user.is_staff:
        messages.info(request, 'Contas administrativas devem usar o painel de administração.')
        return None, redirect('dashboard:home')

    user_profile = Profile.objects.filter(user=request.user).first()
    if user_profile is not None:
        return user_profile, None

    auth_logout(request)
    messages.error(
        request,
        'Não encontramos os dados do seu perfil. Entre novamente ou crie uma conta.',
    )
    return None, redirect('accounts:login')


def send_email_verification(request, user_profile):
    if not settings.EMAIL_DELIVERY_ENABLED:
        return 0

    token = signing.dumps(
        {
            'profile_id': user_profile.pk,
            'email_fingerprint': email_fingerprint(user_profile.email),
        },
        salt=EMAIL_VERIFICATION_SALT,
    )
    confirmation_url = request.build_absolute_uri(
        reverse('accounts:confirm_email', kwargs={'token': token}),
    )
    return send_mail(
        subject='Confirme seu e-mail',
        message=(
            'Confirme o e-mail da sua conta acessando o link abaixo:\n\n'
            f'{confirmation_url}\n\n'
            'Este link é válido por 24 horas.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_profile.email],
        fail_silently=True,
    )


def register(request):
    if request.user.is_authenticated:
        return authenticated_landing(request)

    form = AccountCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if user is not None:
            send_email_verification(request, user.profile)
        messages.success(
            request,
            'Se os dados informados puderem ser usados, o cadastro será processado e a '
            'confirmação seguirá para o e-mail informado.',
        )
        return redirect('accounts:login')

    return render(request, 'accounts/register.html', {'form': form})


def login(request):
    if request.user.is_authenticated:
        return authenticated_landing(request)

    form = LoginForm(request=request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.user)
        return authenticated_landing(request)

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def profile(request):
    user_profile, redirect_response = customer_profile_or_redirect(request)
    if redirect_response:
        return redirect_response
    return render(request, 'accounts/profile.html', {'profile': user_profile})


@login_required
def edit_profile(request):
    user_profile, redirect_response = customer_profile_or_redirect(request)
    if redirect_response:
        return redirect_response
    completing_for_quote = request.GET.get('next') == 'quote'
    form = ProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=user_profile,
        require_address=completing_for_quote,
    )

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil atualizado com sucesso.')
        if completing_for_quote:
            return redirect('dashboard:request_quote')
        return redirect('accounts:profile')

    return render(
        request,
        'accounts/profile_edit.html',
        {
            'profile': user_profile,
            'form': form,
            'completing_for_quote': completing_for_quote,
        },
    )


@require_POST
@login_required
def resend_email_verification(request):
    user_profile, redirect_response = customer_profile_or_redirect(request)
    if redirect_response:
        return redirect_response

    if not user_profile.is_email_verified:
        send_email_verification(request, user_profile)
    messages.info(
        request,
        'Se a confirmação ainda for necessária, enviaremos instruções ao e-mail da conta.',
    )

    return redirect('accounts:profile')


def confirm_email(request, token):
    try:
        payload = signing.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=EMAIL_VERIFICATION_MAX_AGE,
        )
    except (signing.BadSignature, signing.SignatureExpired):
        messages.error(request, 'O link de confirmação é inválido ou expirou.')
        if request.user.is_authenticated:
            return authenticated_landing(request)
        return redirect('accounts:login')

    user_profile = Profile.objects.filter(pk=payload.get('profile_id')).first()
    if (
        user_profile is None
        or user_profile.is_email_verified
        or payload.get('email_fingerprint') != email_fingerprint(user_profile.email)
    ):
        messages.error(request, 'O link de confirmação é inválido ou expirou.')
        if request.user.is_authenticated:
            return authenticated_landing(request)
        return redirect('accounts:login')

    user_profile.verify_email()
    messages.success(request, 'E-mail confirmado com sucesso.')
    if request.user.is_authenticated:
        return authenticated_landing(request)
    return redirect('accounts:login')


@require_POST
@login_required
def logout(request):
    auth_logout(request)
    return redirect('accounts:login')


@require_POST
@login_required
def delete_account(request):
    _, redirect_response = customer_profile_or_redirect(request)
    if redirect_response:
        return redirect_response

    user = request.user
    auth_logout(request)
    user.delete()
    messages.success(request, 'Sua conta foi excluída.')
    return redirect('accounts:register')
