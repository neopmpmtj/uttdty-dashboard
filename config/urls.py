from django.contrib import admin
from django.urls import include, path

from accounts.views import GoogleCallbackView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "src.accounts/google/callback/",
        GoogleCallbackView.as_view(),
        name="oauth_google_callback",
    ),
    path("accounts/", include("accounts.urls")),
    path("", include("dashboard.urls")),
]
