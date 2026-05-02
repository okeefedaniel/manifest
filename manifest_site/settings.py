"""
Manifest — Standalone Document Signing Platform
Django settings for standalone deployment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
DEMO_MODE = os.environ.get('DEMO_MODE', 'False').lower() in ('true', '1', 'yes')
DEMO_ROLES = ['admin', 'staff', 'signer']

import secrets as _secrets

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = _secrets.token_hex(25)
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set in production')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Railway provides RAILWAY_PUBLIC_DOMAIN automatically
RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    ALLOWED_HOSTS.append('.railway.app')

# CSRF trusted origins (required for POST forms behind HTTPS proxy)
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
if RAILWAY_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_DOMAIN}')
CSRF_TRUSTED_ORIGINS = [o for o in CSRF_TRUSTED_ORIGINS if o]  # filter blanks

MANIFEST_SITE_URL = os.environ.get('SITE_URL', 'https://manifest.docklabs.ai')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    # Keel (DockLabs shared platform)
    'keel.accounts',
    'keel.core',
    'keel.security',
    'keel.notifications',
    'keel.requests',
    'keel.settings',
    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',
    # Allauth (SSO / MFA)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.microsoft',
    'allauth.socialaccount.providers.openid_connect',  # Phase 2b: Keel as IdP
    'allauth.mfa',
    # Manifest
    'signatures.apps.SignaturesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'keel.security.middleware.SecurityHeadersMiddleware',
    'keel.security.middleware.AdminIPAllowlistMiddleware',
    'keel.security.middleware.FailedLoginMonitor',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'keel.accounts.middleware.AutoOIDCLoginMiddleware',
    'keel.accounts.middleware.ProductAccessMiddleware',
    'keel.accounts.middleware.SessionFreshnessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'keel.core.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'manifest_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'signatures.context_processors.manifest_context',
                'keel.core.context_processors.site_context',
                'keel.core.context_processors.fleet_context',
                'keel.core.context_processors.breadcrumb_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'manifest_site.wsgi.application'

# Database — uses DATABASE_URL (provided automatically by Railway Postgres)
import dj_database_url

_db_url = os.environ.get('DATABASE_URL', '').strip().lstrip('= ')
if not _db_url:
    # Railway sometimes stores variable names with trailing whitespace;
    # fall back to scanning env vars if the exact key isn't found.
    for _key, _val in os.environ.items():
        if _key.strip() == 'DATABASE_URL' and _val.strip():
            _db_url = _val.strip().lstrip('= ')
            break
if _db_url and '://' in _db_url:
    # Use parse() with the value we already read, NOT config() which
    # re-reads from os.environ and can get a stale/empty value.
    DATABASES = {
        'default': dj_database_url.parse(_db_url, conn_max_age=600)
    }
else:
    if _db_url:
        import warnings
        warnings.warn(
            f'DATABASE_URL is set but looks invalid (no scheme): '
            f'{_db_url[:20]}...',
            stacklevel=1,
        )
    import warnings
    warnings.warn(
        'DATABASE_URL not found — using SQLite fallback. '
        'Set DATABASE_URL for production use.',
        stacklevel=1,
    )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_manifest.sqlite3',
        }
    }

AUTH_USER_MODEL = 'keel_accounts.KeelUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_manifest'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# ---------------------------------------------------------------------------
# Allauth
# ---------------------------------------------------------------------------
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_ADAPTER = 'keel.core.sso.KeelAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'keel.core.sso.KeelSocialAccountAdapter'

SOCIALACCOUNT_LOGIN_ON_GET = True

_MSFT_TENANT = os.environ.get('MICROSOFT_TENANT_ID', 'common')
SOCIALACCOUNT_PROVIDERS = {
    'microsoft': {
        'APP': {
            'client_id': os.environ.get('MICROSOFT_CLIENT_ID', ''),
            'secret': os.environ.get('MICROSOFT_CLIENT_SECRET', ''),
        },
        'SCOPE': ['openid', 'email', 'profile', 'User.Read'],
        'AUTH_PARAMS': {'prompt': 'select_account'},
        'TENANT': _MSFT_TENANT,
    },
}

# ---------------------------------------------------------------------------
# Keel OIDC (Phase 2b) — Keel is the identity provider for the DockLabs suite
# ---------------------------------------------------------------------------
# When KEEL_OIDC_CLIENT_ID is set, this product federates authentication to
# Keel via standard OAuth2/OIDC. When unset, the product falls back to local
# Django auth (+ optional direct Microsoft SSO), so standalone deployments
# continue to work without any Keel dependency.
KEEL_OIDC_CLIENT_ID = os.environ.get('KEEL_OIDC_CLIENT_ID', '')
KEEL_OIDC_CLIENT_SECRET = os.environ.get('KEEL_OIDC_CLIENT_SECRET', '')
KEEL_OIDC_ISSUER = os.environ.get('KEEL_OIDC_ISSUER', 'https://keel.docklabs.ai')

if KEEL_OIDC_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS['openid_connect'] = {
        'APPS': [
            {
                'provider_id': 'keel',
                'name': 'Sign in with DockLabs',
                'client_id': KEEL_OIDC_CLIENT_ID,
                'secret': KEEL_OIDC_CLIENT_SECRET,
                'settings': {
                    'server_url': f'{KEEL_OIDC_ISSUER}/oauth/.well-known/openid-configuration',
                    'token_auth_method': 'client_secret_post',
                    'oauth_pkce_enabled': True,  # Keel requires PKCE
                    'scope': ['openid', 'email', 'profile', 'product_access', 'organization'],
                },
            },
        ],
    }

MFA_ADAPTER = 'allauth.mfa.adapter.DefaultMFAAdapter'
MFA_SUPPORTED_TYPES = ['totp', 'webauthn', 'recovery_codes']
MFA_TOTP_ISSUER = 'Manifest'
MFA_PASSKEY_LOGIN_ENABLED = True

# Email — Resend HTTP API for transactional emails (Railway blocks outbound SMTP)
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'keel.notifications.backends.resend_backend.ResendEmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'DockLabs <info@docklabs.ai>')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'signatures': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Security Settings
# ---------------------------------------------------------------------------

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days (pre-gov-launch; tighten before go-live)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

if not DEBUG:
    # HTTPS / SSL settings (Railway handles SSL at the proxy)
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HTTP Strict Transport Security
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Content Security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# Use separate migrations directory for standalone mode
# (avoids the grants app dependency in the default migration)
MIGRATION_MODULES = {
    'signatures': 'manifest_site.migrations.signatures',
}

# ---------------------------------------------------------------------------
# Keel (DockLabs Shared Platform)
# ---------------------------------------------------------------------------
KEEL_GATE_ACCESS = True
KEEL_PRODUCT_CODE = 'manifest'
from keel.core.fleet import FLEET as KEEL_FLEET_PRODUCTS  # noqa: E402,F401
KEEL_PRODUCT_NAME = 'Manifest'
KEEL_PRODUCT_ICON = 'bi-pen-fill'
KEEL_PRODUCT_SUBTITLE = 'Document Signing Platform'
KEEL_AUDIT_LOG_MODEL = 'signatures.AuditLog'
KEEL_NOTIFICATION_MODEL = 'signatures.Notification'
KEEL_NOTIFICATION_PREFERENCE_MODEL = 'signatures.NotificationPreference'
HELM_FEED_API_KEY = os.environ.get('HELM_FEED_API_KEY', '')
KEEL_CSP_POLICY = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self'"  # Start permissive, tighten later

# --- Admin allowlist + trusted-proxy config (keel.security) ---
# KEEL_ADMIN_ALLOWED_IPS: list of CIDR / IPs allowed to hit /admin/.
#   Empty list = no-op (dev). Set via env on every Railway service in prod.
# KEEL_TRUSTED_PROXY_COUNT: number of trusted proxies between the client and
#   Django. Railway = 1. If 0, X-Forwarded-For is ignored (client spoof-safe).
KEEL_ADMIN_ALLOWED_IPS = [
    ip.strip() for ip in os.environ.get('KEEL_ADMIN_ALLOWED_IPS', '').split(',')
    if ip.strip()
]
KEEL_TRUSTED_PROXY_COUNT = int(os.environ.get('KEEL_TRUSTED_PROXY_COUNT', '1'))
