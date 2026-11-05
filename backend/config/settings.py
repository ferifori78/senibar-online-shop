from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)
environ.Env.read_env(BASE_DIR / ".env")

# JWT signs with HMAC-SHA256, which wants at least 32 bytes of key.
SECRET_KEY = env(
    "SECRET_KEY", default="dev-only-insecure-key-change-me-before-deploying-anywhere"
)
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# The container healthcheck and the Nginx upstream reach this process by its
# internal name, not by the public domain. Without these, a correctly-set
# ALLOWED_HOSTS makes every probe a 400 and the container never turns healthy.
for _internal in ("localhost", "127.0.0.1", "api"):
    if _internal not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_internal)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "django_celery_beat",
    "corsheaders",
    # Local
    "accounts",
    "catalog",
    "orders",
    "payments",
    "support",
    "notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://senobar:senobar@localhost:5432/senobar"
    )
}

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Uploads --------------------------------------------------------------
# The largest photograph the panel accepts. Camera files run to 25MB, and the
# server shrinks them for the web after they land, so the roaster can upload
# the good file and still get a fast product page.
MAX_IMAGE_UPLOAD_BYTES = env.int("MAX_IMAGE_UPLOAD_BYTES", default=25 * 1024 * 1024)

# Django refuses a request body over this before any view sees it, so it has
# to clear the image ceiling with room for the rest of the multipart form.
# nginx has its own `client_max_body_size` — both have to be raised, or the
# larger of the two is never reached.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_IMAGE_UPLOAD_BYTES + 5 * 1024 * 1024

# Anything above this is spooled to a temporary file instead of being held in
# memory. Keeping it well under the ceiling is what stops several concurrent
# uploads from filling the container's RAM.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Set false to store photographs exactly as uploaded.
IMAGE_SHRINK_ENABLED = env.bool("IMAGE_SHRINK_ENABLED", default=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ------------------------------------------------------------------
REST_FRAMEWORK = {
    # JWT only. SessionAuthentication is the one DRF class that enforces CSRF,
    # and it enforces it on any request carrying a Django session cookie — which
    # a staff member has as soon as they visit /admin/. The SPA sends a bearer
    # token, never a CSRF token, so leaving it enabled turned every POST from a
    # logged-in-to-/admin browser into "CSRF Failed: CSRF token missing",
    # registration included. It is added back under DEBUG for the browsable API.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # Custom so `?page_size=` works: the landing page wants three products, not
    # the full page of 24. Capped so the parameter cannot be used to pull the
    # whole catalogue in one request.
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 24,
    # Per-IP ceiling for the OTP endpoint. The per-number limit in
    # accounts/otp.py stops one customer being spammed; this stops one machine
    # walking through many numbers to spend the shop's SMS credit.
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        "otp": env("OTP_IP_RATE", default="20/hour"),
        # Generous: one real visitor browsing hard is a few hundred an hour,
        # and the point is only to stop the table being filled deliberately.
        "visit": env("VISIT_IP_RATE", default="600/hour"),
    },
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

# Locally, the browsable API is genuinely useful and needs a session to log in
# with. In production it only creates the CSRF trap described above.
if DEBUG:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] += (
        "rest_framework.authentication.SessionAuthentication",
    )

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# --- CORS -----------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --- Security -------------------------------------------------------------
# Nginx terminates TLS and forwards the original scheme; without this Django
# thinks every request is plain HTTP and builds http:// links in emails.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=CORS_ALLOWED_ORIGINS)

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    # Enable once TLS is confirmed working — a wrong HSTS header is hard to
    # undo, because browsers remember it.
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)

# --- Logging --------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "{asctime} {levelname:<8} {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "senobar": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# --- Payments -------------------------------------------------------------
# The default when the client does not pick one. "mock" runs entirely
# in-process; nothing above the gateway layer needs to change to switch.
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="mock")

# What checkout offers the customer, in display order. A gateway listed here
# but missing its credentials is silently dropped from the picker rather than
# offered and then failing mid-payment — see gateways.available_gateways().
PAYMENT_GATEWAYS = env.list("PAYMENT_GATEWAYS", default=[PAYMENT_GATEWAY])

# --- ZarinPal -------------------------------------------------------------
# merchant_id is a UUID from the gateway settings page; access_token comes from
# the active-sessions section and is only needed for refunds and transaction
# queries, not for taking payments.
ZARINPAL_MERCHANT_ID = env("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_ACCESS_TOKEN = env("ZARINPAL_ACCESS_TOKEN", default="")
ZARINPAL_SANDBOX = env.bool("ZARINPAL_SANDBOX", default=DEBUG)

# --- BitPay ---------------------------------------------------------------
# A 52-character key from the BitPay panel. In sandbox mode the driver falls
# back to BitPay's published test key, so the flow is exercisable before the
# merchant account is approved.
BITPAY_API_KEY = env("BITPAY_API_KEY", default="")
BITPAY_SANDBOX = env.bool("BITPAY_SANDBOX", default=DEBUG)

# BitPay never reports its commission, so the driver derives it from these.
# They mirror the merchant contract and must be updated when that changes —
# what they produce is an estimate for the invoice, not a figure the gateway
# confirmed. Percent of the transaction, capped in rial (50,000 = 5,000 toman).
BITPAY_FEE_PERCENT = env("BITPAY_FEE_PERCENT", default="1.0")
BITPAY_FEE_CAP = env("BITPAY_FEE_CAP", default="50000")

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
# `or` rather than just a default: compose passes this through as an empty
# string when it is not set in .env, and an empty callback URL would send the
# customer nowhere after paying.
PAYMENT_CALLBACK_URL = (
    env("PAYMENT_CALLBACK_URL", default="") or f"{FRONTEND_URL}/checkout/callback"
)
# Where the mock gateway's stand-in "pay page" lives on the frontend.
MOCK_GATEWAY_URL = env("MOCK_GATEWAY_URL", default=f"{FRONTEND_URL}/checkout/mock-gateway")

# --- Celery / Redis -------------------------------------------------------
# Separate Redis databases: the broker's queues and the result store have very
# different lifetimes, and mixing them makes a FLUSHDB during debugging drop
# in-flight work.
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Acknowledge only after the task finishes, so a worker killed mid-task hands
# the job back to the queue instead of silently losing it. Safe because every
# task here is written to be idempotent.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# A task that hangs on an unresponsive SMS gateway must not hold a worker
# forever: warn at 60s, kill at 120s.
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_TASK_TIME_LIMIT = 120

CELERY_RESULT_EXPIRES = 60 * 60 * 24  # a day is plenty for debugging
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Named queues so a flood of notifications cannot starve the nightly reports.
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "notifications.*": {"queue": "notifications"},
    "reports.*": {"queue": "reports"},
    # The Telegram feed shares the notifications queue, which the worker
    # already consumes — an unrouted task would sit on a queue nobody reads.
    "feed.*": {"queue": "notifications"},
}

# Run tasks inline during tests: no worker, no broker, and failures surface as
# real exceptions instead of vanishing into a queue.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True

# --- Celery Beat ----------------------------------------------------------
# The schedule lives in the database so staff can retime a job without a
# deploy; the entries below are the defaults it starts from.
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "daily-roast-report": {
        "task": "reports.daily_roast_report",
        # 08:00 Asia/Tehran, every day: the roastery's morning briefing.
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "reports", "expires": 60 * 60 * 3},
    },
    "flag-stale-batches": {
        "task": "reports.flag_stale_batches",
        "schedule": crontab(hour=8, minute=15),
        "options": {"queue": "reports", "expires": 60 * 60 * 3},
    },
    "abandoned-payment-sweep": {
        "task": "orders.release_abandoned_payments",
        "schedule": crontab(minute=0),  # hourly
        "options": {"queue": "default", "expires": 60 * 30},
    },
    # Traffic is summarised rather than posted per view: Telegram throttles a
    # bot past roughly 20 messages a minute to one channel.
    "telegram-traffic-digest": {
        "task": "feed.traffic_digest",
        "schedule": crontab(minute=5),  # just after the hour
        # Expires before the next window: a digest delivered late describes an
        # hour nobody is still thinking about.
        "options": {"queue": "notifications", "expires": 60 * 50},
    },
    "telegram-trending-check": {
        "task": "feed.trending_product",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notifications", "expires": 60 * 10},
    },
    "site-visit-sweep": {
        "task": "feed.sweep_visits",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "default", "expires": 60 * 60 * 3},
    },
}

# --- Telegram feed --------------------------------------------------------
# A live feed of shop activity for the roaster, in a private channel. The bot
# token belongs in .env on the server: anyone holding it can post as the shop
# and read whatever the bot can see.
#
# To set up: talk to @BotFather to create a bot, add it to the channel as an
# administrator, then take the channel id (a negative number like
# -1001234567890) from @userinfobot or getUpdates.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")
TELEGRAM_TIMEOUT = env.float("TELEGRAM_TIMEOUT", default=8.0)

# Page views are summarised on this cadence rather than posted one by one:
# Telegram throttles a bot past roughly 20 messages a minute to one channel.
TELEGRAM_DIGEST_MINUTES = env.int("TELEGRAM_DIGEST_MINUTES", default=60)
# A product page crossing this many views inside one digest window is worth
# saying out loud between digests.
TELEGRAM_TRENDING_VIEWS = env.int("TELEGRAM_TRENDING_VIEWS", default=25)
# How long raw visit rows are kept. They exist to be counted, not stored.
SITE_VISIT_RETENTION_DAYS = env.int("SITE_VISIT_RETENTION_DAYS", default=7)

# --- Notifications --------------------------------------------------------
# "console" prints to the log; swap to a real provider by pointing this at
# another driver in notifications/providers.py.
SMS_BACKEND = env("SMS_BACKEND", default="console")
SMS_SENDER = env("SMS_SENDER", default="Senobar")
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", default="")

# --- SMS.ir ---------------------------------------------------------------
# The key belongs in .env on the server, never in the repo or the database:
# anyone holding it can send messages billed to this account.
SMSIR_API_KEY = env("SMSIR_API_KEY", default="")
SMSIR_LINE_NUMBER = env("SMSIR_LINE_NUMBER", default="")
# How long to wait for the provider to accept a message. The OTP request sends
# inline, so this is time the customer spends watching a spinner: the provider
# either accepts in about a second or is not going to.
SMSIR_TIMEOUT = env.float("SMSIR_TIMEOUT", default=8.0)

# Templates are registered in the SMS.ir panel; only their ids live here, so a
# change of wording never needs a deploy. The sandbox template is 123456 with
# the parameter "Code".
SMSIR_VERIFY_TEMPLATE_ID = env("SMSIR_VERIFY_TEMPLATE_ID", default="")
SMSIR_VERIFY_PARAM = env("SMSIR_VERIFY_PARAM", default="CODE")
# Welcome greeting: «#CONTACT# عزیز، به خانواده صنوبر خوش آمدید.»
SMSIR_WELCOME_TEMPLATE_ID = env("SMSIR_WELCOME_TEMPLATE_ID", default="")
SMSIR_WELCOME_PARAM = env("SMSIR_WELCOME_PARAM", default="CONTACT")

# «سفارش #ORDER_CODE# در مرحله #ORDER_STATUS# است.»
SMSIR_ORDER_TEMPLATE_ID = env("SMSIR_ORDER_TEMPLATE_ID", default="")
SMSIR_ORDER_PARAM = env("SMSIR_ORDER_PARAM", default="ORDER_STATUS")
SMSIR_ORDER_CODE_PARAM = env("SMSIR_ORDER_CODE_PARAM", default="ORDER_CODE")

# «سفارش #ORDER_CODE# پرداختش تایید شده و اماده سفر شده.»
SMSIR_PAYMENT_TEMPLATE_ID = env("SMSIR_PAYMENT_TEMPLATE_ID", default="")

# «تیکت شما به کد #TICKET_CODE# پاسخ گرفت.»
SMSIR_TICKET_REPLY_TEMPLATE_ID = env("SMSIR_TICKET_REPLY_TEMPLATE_ID", default="")
SMSIR_TICKET_CODE_PARAM = env("SMSIR_TICKET_CODE_PARAM", default="TICKET_CODE")

# «تیکت #TICKET_CODE# به وضعیت #TICKET_STATUS# تغییر کرد.»
SMSIR_TICKET_STATUS_TEMPLATE_ID = env("SMSIR_TICKET_STATUS_TEMPLATE_ID", default="")
SMSIR_TICKET_STATUS_PARAM = env("SMSIR_TICKET_STATUS_PARAM", default="TICKET_STATUS")

# --- One-time codes -------------------------------------------------------
OTP_CODE_LENGTH = env.int("OTP_CODE_LENGTH", default=5)
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=120)
# How many codes one number may request per hour, and how many wrong guesses
# a single code tolerates before it is burned.
OTP_MAX_PER_HOUR = env.int("OTP_MAX_PER_HOUR", default=5)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
# A new code cannot be requested until this many seconds have passed, so the
# "resend" button cannot be used to spend the shop's SMS credit.
OTP_RESEND_SECONDS = env.int("OTP_RESEND_SECONDS", default=60)

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Senobar <hello@senobar.coffee>")
# Where the daily roast report is sent.
ROASTERY_REPORT_EMAILS = env.list("ROASTERY_REPORT_EMAILS", default=["roastery@senobar.coffee"])
