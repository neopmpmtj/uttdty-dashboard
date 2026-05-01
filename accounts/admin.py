from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser, UserSecret


class UserSecretInline(admin.StackedInline):
    model = UserSecret
    extra = 0
    readonly_fields = (
        "encrypted_google_access_token",
        "encrypted_google_refresh_token",
        "encrypted_google_token_expiry",
        "google_token_scopes",
        "created_at",
        "updated_at",
    )
    can_delete = False


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_google_account")
    search_fields = ("email", "first_name", "last_name")
    inlines = (UserSecretInline,)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Google", {"fields": ("is_google_account", "is_email_verified")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )


@admin.register(UserSecret)
class UserSecretAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
