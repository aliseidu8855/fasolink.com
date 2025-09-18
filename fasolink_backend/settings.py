from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _
import cloudinary
import cloudinary.uploader
import cloudinary.api

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

## --- CORE DJANGO SETTINGS ---
SECRET_KEY = os.environ.get("SECRET_KEY")
ROOT_URLCONF = "fasolink_backend.urls"
WSGI_APPLICATION = "fasolink_backend.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ASGI_APPLICATION = "fasolink_backend.asgi.application"

## --- DEPLOYMENT & SECURITY ---
DEBUG = os.environ.get("DEBUG", "").lower() in {"1","true","yes"} or ("RENDER" not in os.environ and "HEROKU" not in os.environ)
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
if HEROKU_APP_NAME:
    ALLOWED_HOSTS.extend([
        f"{HEROKU_APP_NAME}.herokuapp.com",
        "localhost",
        "127.0.0.1",
    ])

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://fasolink-web.onrender.com",
    "https://fasolink.vercel.app",
    "http://192.168.11.108:5173",
    "http://172.26.144.1:5173",
    "https://fasolinkapi-c1c106ebe031.herokuapp.com",
]

# Allow additional CORS origins via environment variables (comma-separated)
_extra_cors = os.environ.get("CORS_ALLOWED_ORIGINS")
if _extra_cors:
    for origin in [o.strip() for o in _extra_cors.split(",") if o.strip()]:
        if origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)

## --- INSTALLED APPS ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "cloudinary_storage",
    "cloudinary",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "channels",
    "api",
]

## --- MIDDLEWARE ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

## --- DATABASE ---
# Only require SSL for Postgres; sqlite does not accept ssl params
_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'db.sqlite3')}" )
_db_url_lower = _db_url.lower()
_ssl_require = _db_url_lower.startswith("postgres://") or _db_url_lower.startswith("postgresql://")
DATABASES = {
    "default": dj_database_url.parse(
        _db_url,
        conn_max_age=600,
        ssl_require=_ssl_require,
    )
}

# --- CHANNELS / WEBSOCKETS ---
# Use Redis if available; fall back to in-memory for dev if REDIS_URL not set.
_redis_url = os.environ.get("REDIS_URL")
if _redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_redis_url]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
## --- FILE STORAGE (CLOUDINARY) ---
# This is the only file storage configuration that should exist.
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get("CLOUDINARY_NAME"),
    'API_KEY': os.environ.get("CLOUDINARY_API_KEY"),
    'API_SECRET': os.environ.get("CLOUDINARY_API_SECRET_KEY"),
}
# Configure cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET_KEY"),
    secure=True
)
MEDIA_URL = ""  # Explicitly disable old media URL
MEDIA_ROOT = ""  # Explicitly disable old media root

## --- STATIC FILES (WHITENOISE) ---
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
 # Trust X-Forwarded-Proto from Heroku/Proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = []
if os.environ.get('HEROKU_APP_NAME'):
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['HEROKU_APP_NAME']}.herokuapp.com")
## --- OTHER SETTINGS ---
# (Templates, Auth Validators, i18n, DRF, Spectacular, etc. remain the same)
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
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "FasoLink API",
    "DESCRIPTION": "API documentation for the FasoLink classifieds platform.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
