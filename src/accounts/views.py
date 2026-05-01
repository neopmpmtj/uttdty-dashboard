from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from .google_oauth import (
    GoogleAuthError,
    create_authorization_url,
    exchange_code_for_tokens,
    get_google_user_info,
    store_user_tokens,
)
from .models import CustomUser


class LoginView(View):
    """Landing page with explicit control to start Google OAuth (no auto-redirect)."""

    template_name = "accounts/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, self.template_name)


class GoogleLoginView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        try:
            auth_url, state = create_authorization_url(request=request)
        except GoogleAuthError:
            messages.error(
                request,
                "Google sign-in is not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
            )
            return render(request, "accounts/login_error.html", status=500)
        request.session["oauth_state"] = state
        return redirect(auth_url)


class GoogleCallbackView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            error = request.GET.get("error")
            if error:
                messages.error(request, "Google sign-in was cancelled or failed.")
                return redirect("accounts:login")

            state = request.GET.get("state")
            stored = request.session.get("oauth_state")
            if not state or state != stored:
                messages.error(
                    request, "Invalid authentication request. Please try again."
                )
                return redirect("accounts:login")

            code = request.GET.get("code")
            if not code:
                messages.error(
                    request, "Invalid authentication response. Please try again."
                )
                return redirect("accounts:login")

            try:
                tokens = exchange_code_for_tokens(code, request)
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                expires_in = tokens.get("expires_in")
                scope_raw = tokens.get("scope") or ""
                scopes = [s for s in scope_raw.replace(",", " ").split() if s]

                if not access_token:
                    raise GoogleAuthError("No access token in response")

                user_info = get_google_user_info(access_token)
                google_email = (user_info.get("email") or "").lower()
                if not google_email:
                    raise GoogleAuthError("No email in user info")

                if not user_info.get("email_verified", False):
                    messages.error(
                        request,
                        "Please verify your Google account email before signing in.",
                    )
                    return redirect("accounts:login")

                user, created = CustomUser.objects.get_or_create(
                    email=google_email,
                    defaults={
                        "first_name": user_info.get("given_name") or "",
                        "last_name": user_info.get("family_name") or "",
                    },
                )
                # Google login path: no local password; strip any existing usable password.
                if user.has_usable_password() or created:
                    user.set_unusable_password()
                user.is_google_account = True
                user.is_email_verified = True
                if user_info.get("given_name") and not user.first_name:
                    user.first_name = user_info.get("given_name") or ""
                if user_info.get("family_name") and not user.last_name:
                    user.last_name = user_info.get("family_name") or ""
                user.save()

                store_user_tokens(
                    user,
                    access_token,
                    refresh_token,
                    expires_in,
                    scopes,
                )
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                messages.success(request, "Signed in with Google.")
                return redirect(settings.LOGIN_REDIRECT_URL)
            except GoogleAuthError:
                messages.error(request, "Google sign-in failed. Please try again.")
                return redirect("accounts:login")
        finally:
            request.session.pop("oauth_state", None)


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)
