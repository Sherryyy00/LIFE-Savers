"""
Shared settings for LIFE Savers.

Anything secret or environment-specific comes from environment variables
(see .env.example). Nothing sensitive should ever be hardcoded here.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# Admin lives at a non-obvious path to cut down on bot noise.
SITE_NAME = "LIFE Savers"
SITE_TAGLINE = "Every Drop Counts. Every Life Matters."

ADMIN_URL = env("ADMIN_URL", default="manage-ls/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # third party
    "phonenumber_field",
    # local
    "apps.accounts",
    "apps.core",
    "apps.donors",
    "apps.blood_requests",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: DATABASE_URL in .env. Local dev can use SQLite, production uses
# Postgres (Neon), e.g. postgres://user:pass@host/dbname?sslmode=require
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Language and time: English + Urdu, Pakistan time.
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ur", "اردو")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

PHONENUMBER_DEFAULT_REGION = "PK"
PHONENUMBER_DB_FORMAT = "E164"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Blood donation rules. Defaults follow common guidance used by blood banks in
# Pakistan; confirm them with a local blood bank before launch.
# ---------------------------------------------------------------------------
DONATION_INTERVAL_DAYS = env.int("DONATION_INTERVAL_DAYS", default=90)
DONOR_MIN_AGE = env.int("DONOR_MIN_AGE", default=18)
DONOR_MAX_AGE = env.int("DONOR_MAX_AGE", default=60)
DONOR_MIN_WEIGHT_KG = env.int("DONOR_MIN_WEIGHT_KG", default=50)
# Donors must re-confirm the eligibility self-check this often.
ELIGIBILITY_CONFIRMATION_VALID_DAYS = env.int("ELIGIBILITY_CONFIRMATION_VALID_DAYS", default=180)
DEFAULT_MATCH_RADIUS_KM = env.int("DEFAULT_MATCH_RADIUS_KM", default=15)

# Map default centre: Wah Cantt.
DEFAULT_MAP_CENTER = (33.7833, 72.7167)

# Bump this when the privacy policy text changes so we know what each donor agreed to.
PRIVACY_POLICY_VERSION = "2026-11"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
