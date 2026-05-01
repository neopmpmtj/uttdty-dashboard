import json

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("Email address is required"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True"))
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True, max_length=255)
    is_email_verified = models.BooleanField(default=False)
    is_google_account = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        db_table = "accounts_customuser"

    def __str__(self):
        return self.email


class UserSecret(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="secrets",
    )
    encrypted_google_access_token = models.TextField(blank=True, null=True)
    encrypted_google_refresh_token = models.TextField(blank=True, null=True)
    encrypted_google_token_expiry = models.TextField(blank=True, null=True)
    google_token_scopes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_usersecret"

    def __str__(self):
        return f"Secrets for {self.user.email}"

    def get_scopes_list(self) -> list:
        if not self.google_token_scopes:
            return []
        try:
            return json.loads(self.google_token_scopes)
        except json.JSONDecodeError:
            return []

    def set_scopes_list(self, scopes: list) -> None:
        self.google_token_scopes = json.dumps(scopes) if scopes else None
