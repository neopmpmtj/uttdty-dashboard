from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from accounts.views import GoogleCallbackView


def robots_txt(_request):
    return HttpResponse(
        "User-agent: *\nDisallow: /\n",
        content_type="text/plain",
    )


urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("admin/", admin.site.urls),
    path(
        "src.accounts/google/callback/",
        GoogleCallbackView.as_view(),
        name="oauth_google_callback",
    ),
    path("accounts/", include("accounts.urls")),
    path("", include("dashboard.urls")),
]
