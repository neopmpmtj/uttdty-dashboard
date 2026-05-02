"""Project middleware."""

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseBadRequest, HttpResponsePermanentRedirect


def _scheme(request) -> str:
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        header, secure_value = settings.SECURE_PROXY_SSL_HEADER
        if request.META.get(header) == secure_value:
            return "https"
    return "https" if request.is_secure() else request.scheme


class ApexToCanonicalWwwMiddleware:
    """
    If CANONICAL_SITE_HOST is set (e.g. www.example.com), redirect requests on the
    bare apex domain (example.com) to https://CANONICAL_SITE_HOST, preserving path and query.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request_host = request.get_host()
        except DisallowedHost:
            return HttpResponseBadRequest("Bad Request (Invalid Host header)")

        canonical = getattr(settings, "CANONICAL_SITE_HOST", "") or ""
        canonical = canonical.strip().lower()
        if not canonical or not canonical.startswith("www."):
            return self.get_response(request)

        host = request_host.split(":")[0].lower()
        apex = canonical.removeprefix("www.")
        if host != apex:
            return self.get_response(request)

        full_host = request_host
        port_part = full_host[full_host.index(":") :] if ":" in full_host else ""

        path = request.get_full_path()
        target = f"{_scheme(request)}://{canonical}{port_part}{path}"
        return HttpResponsePermanentRedirect(target)
