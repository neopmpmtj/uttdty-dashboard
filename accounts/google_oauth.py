import json
import logging
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from django.conf import settings

from .encryption import encrypt_value
from .models import UserSecret

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v3/userinfo"

OPENID_SCOPE = "openid"
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
PROFILE_SCOPE = "https://www.googleapis.com/auth/userinfo.profile"
LOGIN_SCOPES = [OPENID_SCOPE, EMAIL_SCOPE, PROFILE_SCOPE]


class GoogleAuthError(Exception):
    pass


def _client_config() -> Dict[str, str]:
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
    if not client_id or not client_secret:
        raise GoogleAuthError(
            "Google OAuth credentials not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)."
        )
    return {"client_id": client_id, "client_secret": client_secret}


def get_redirect_uri(request=None) -> str:
    redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", None)
    if redirect_uri:
        return redirect_uri.strip()
    if request:
        from django.urls import reverse

        return request.build_absolute_uri(reverse("accounts:google_callback"))
    raise GoogleAuthError(
        "GOOGLE_OAUTH_REDIRECT_URI must be set to match Google Cloud Console."
    )


def create_authorization_url(
    request=None,
    scopes: Optional[list] = None,
    state: Optional[str] = None,
) -> Tuple[str, str]:
    client_config = _client_config()
    redirect_uri = get_redirect_uri(request)
    request_scopes = scopes or LOGIN_SCOPES
    if state is None:
        state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(request_scopes),
        "state": state,
        "access_type": "offline",
        # select_account: always show Google account picker (avoid silent session reuse).
        # consent: helps obtain/refresh offline refresh tokens when combined with access_type=offline.
        "prompt": "select_account consent",
    }
    authorization_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"
    return authorization_url, state


def exchange_code_for_tokens(code: str, request=None) -> Dict[str, Any]:
    client_config = _client_config()
    redirect_uri = get_redirect_uri(request)
    token_data = {
        "code": code,
        "client_id": client_config["client_id"],
        "client_secret": client_config["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        data = urlencode(token_data).encode("utf-8")
        req = URLRequest(GOOGLE_TOKEN_URI, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlopen(req, timeout=30) as response:
            token_response = json.loads(response.read().decode("utf-8"))
        return token_response
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        logger.error("Token exchange failed HTTP %s: %s", e.code, error_body)
        raise GoogleAuthError(f"Failed to exchange code for tokens: {error_body}") from e
    except (URLError, TimeoutError) as e:
        logger.error("Token exchange network error: %s", e)
        raise GoogleAuthError(f"Network error during token exchange: {e}") from e
    except json.JSONDecodeError as e:
        raise GoogleAuthError("Invalid response from Google token endpoint") from e


def get_google_user_info(access_token: str) -> Dict[str, Any]:
    try:
        req = URLRequest(GOOGLE_USERINFO_URI)
        req.add_header("Authorization", f"Bearer {access_token}")
        with urlopen(req, timeout=30) as response:
            user_info = json.loads(response.read().decode("utf-8"))
        return user_info
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        logger.error("User info fetch failed HTTP %s: %s", e.code, error_body)
        raise GoogleAuthError(f"Failed to fetch user info: {error_body}") from e
    except (URLError, TimeoutError) as e:
        raise GoogleAuthError(f"Network error fetching user info: {e}") from e
    except json.JSONDecodeError as e:
        raise GoogleAuthError("Invalid response from Google userinfo endpoint") from e


def store_user_tokens(
    user,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: Optional[int],
    scopes: list,
) -> None:
    user_secret, _created = UserSecret.objects.get_or_create(user=user)
    user_secret.encrypted_google_access_token = encrypt_value(access_token)
    if refresh_token:
        user_secret.encrypted_google_refresh_token = encrypt_value(refresh_token)
    if expires_in:
        expiry = datetime.now(dt_timezone.utc) + timedelta(seconds=int(expires_in))
        expiry_naive = expiry.replace(tzinfo=None)
        user_secret.encrypted_google_token_expiry = encrypt_value(expiry_naive.isoformat())
    user_secret.set_scopes_list([s for s in scopes if s])
    user_secret.save()
