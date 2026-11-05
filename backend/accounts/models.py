from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(DjangoUserManager):
    """Email is the login credential; username is dropped entirely."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address must be set.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)

    def staff(self):
        return self.get_queryset().filter(is_staff=True, is_active=True)


class CustomUser(AbstractUser):
    """Senobar account.

    Extends AbstractUser but authenticates on email. ``username`` is removed
    rather than left nullable, so nothing downstream can quietly depend on it.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", _("Customer")
        ROASTER = "roaster", _("Roaster")
        ADMIN = "admin", _("Admin")

    username = None

    email = models.EmailField(_("email address"), unique=True, db_index=True)
    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    role = models.CharField(
        _("role"), max_length=16, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )

    # Preferences that shape what we recommend and how we roast for them.
    preferred_grind = models.CharField(_("preferred grind"), max_length=20, blank=True)
    accepts_marketing = models.BooleanField(_("accepts marketing"), default=False)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("-created_at",)

    def __str__(self):
        return self.email

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full or self.email.split("@")[0]

    @property
    def is_roaster(self):
        return self.role in (self.Role.ROASTER, self.Role.ADMIN) or self.is_staff


class Address(models.Model):
    """A shipping address. Orders snapshot these rather than referencing them,
    so editing an address never rewrites the history of a shipped order."""

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="addresses", verbose_name=_("user")
    )
    label = models.CharField(_("label"), max_length=50, blank=True)
    recipient_name = models.CharField(_("recipient name"), max_length=120)
    phone = models.CharField(_("phone number"), max_length=20)
    province = models.CharField(_("province"), max_length=60)
    city = models.CharField(_("city"), max_length=60)
    street_address = models.TextField(_("street address"))
    postal_code = models.CharField(_("postal code"), max_length=20)
    is_default = models.BooleanField(_("default address"), default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("address")
        verbose_name_plural = _("addresses")
        ordering = ("-is_default", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="unique_default_address_per_user",
            )
        ]

    def __str__(self):
        return f"{self.recipient_name} — {self.city}"

    def as_snapshot(self):
        """Flatten to the dict an Order stores at checkout."""
        return {
            "recipient_name": self.recipient_name,
            "phone": self.phone,
            "province": self.province,
            "city": self.city,
            "street_address": self.street_address,
            "postal_code": self.postal_code,
        }


class PhoneOTP(models.Model):
    """A one-time code sent to a phone number.

    Security decisions worth stating, because each is load-bearing:

    * The code is stored as a hash, never in clear. A database dump — or a
      glance at the admin — must not let anyone sign in as a customer.
    * A row is created per request and burned on first successful use, so a
      code cannot be replayed even within its lifetime.
    * Wrong guesses are counted on the row. Five bad attempts destroy the
      code rather than the account, so an attacker guessing at one number
      cannot lock a real customer out of their own login.
    * Rate limiting is per phone number and per hour, which is what stops the
      endpoint being used to spend the shop's SMS credit.
    """

    class Purpose(models.TextChoices):
        LOGIN = "login", _("Login or registration")

    phone = models.CharField(_("phone number"), max_length=20, db_index=True)
    code_hash = models.CharField(_("code hash"), max_length=128)
    purpose = models.CharField(
        _("purpose"), max_length=16, choices=Purpose.choices, default=Purpose.LOGIN
    )

    attempts = models.PositiveSmallIntegerField(_("failed attempts"), default=0)
    is_used = models.BooleanField(_("used"), default=False)

    # Kept for the audit trail: which address asked for this code.
    requested_ip = models.GenericIPAddressField(_("requested from"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(_("expires at"))

    class Meta:
        verbose_name = _("phone code")
        verbose_name_plural = _("phone codes")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["phone", "-created_at"])]

    def __str__(self):
        return f"{self.phone} — {self.created_at:%Y-%m-%d %H:%M}"

    # --- Lifecycle --------------------------------------------------------

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_live(self):
        """Usable right now: not spent, not expired, not guessed to death."""
        from django.conf import settings

        return (
            not self.is_used
            and not self.is_expired
            and self.attempts < settings.OTP_MAX_ATTEMPTS
        )

    def check_code(self, raw):
        """Verify a submitted code, counting the attempt either way.

        Returns True only for a live row with a matching code. The attempt is
        recorded before the answer is returned, so a caller that forgets to
        save cannot accidentally give away unlimited guesses.
        """
        from django.contrib.auth.hashers import check_password

        if not self.is_live:
            return False

        if check_password(str(raw), self.code_hash):
            self.is_used = True
            self.save(update_fields=["is_used"])
            return True

        self.attempts += 1
        self.save(update_fields=["attempts"])
        return False
