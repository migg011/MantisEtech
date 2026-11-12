import os
from pathlib import Path

from dotenv import load_dotenv

# Ambiente
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / '.env')



def environment_list(name, default=''):
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]


def environment_boolean(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ('true', '1', 'yes')


# Segurança
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
DEBUG = environment_boolean('DJANGO_DEBUG')
ALLOWED_HOSTS = environment_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Aplicações
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'maintenance.apps.MaintenanceConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
APPEND_SLASH = False  # Rotas do Angular usam /api/orders, sem barra final.

# Banco de dados
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['BD_NOME'],
        'USER': os.getenv('BD_USUARIO', 'mantis'),
        'PASSWORD': os.getenv('BD_SENHA', ''),
        'HOST': os.getenv('BD_HOST', '127.0.0.1'),
        'PORT': os.getenv('BD_PORT', '5433'),
        'CONN_MAX_AGE': 60,
    }
}

# Usuário e senhas
AUTH_USER_MODEL = 'maintenance.User'
AUTHENTICATION_BACKENDS = ['maintenance.backends.RegistrationBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
API_TOKEN_MAX_AGE = 8 * 60 * 60

# API: autenticação Bearer do Mantis
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['maintenance.authentication.BearerAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['maintenance.permissions.ActiveAccount'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_RENDERER_CLASSES': ['maintenance.renderers.MantisJSONRenderer'],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'maintenance.exceptions.handle_exception',
    'DEFAULT_PAGINATION_CLASS': None,
    'COERCE_DECIMAL_TO_STRING': True,
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# CORS e CSRF
CORS_ALLOWED_ORIGINS = environment_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:4200,http://127.0.0.1:4200,http://localhost:4201,http://127.0.0.1:4201',
)
CORS_ALLOW_CREDENTIALS = False  # A API autentica pelo cabeçalho; não por cookie.
CSRF_TRUSTED_ORIGINS = environment_list('CSRF_TRUSTED_ORIGINS')

# Idioma e fuso horário
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Manaus'
USE_I18N = True
USE_TZ = True

# Arquivos estáticos e uploads
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# Segurança HTTP
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SECURE = environment_boolean('DJANGO_COOKIE_SECURE')
CSRF_COOKIE_SECURE = environment_boolean('DJANGO_COOKIE_SECURE')

# Logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO')},
}
