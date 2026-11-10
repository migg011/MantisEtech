"""Configuração do Mantis: Django, PostgreSQL e API REST consumida pelo Angular."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Ambiente: a raiz atende também ao Docker Compose. Variáveis do processo têm prioridade.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / '.env')
load_dotenv(BASE_DIR / '.env')


def environment_list(name, default=''):
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]


def environment_boolean(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ('true', '1', 'yes')


# Segurança e execução
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY com pelo menos 32 caracteres no .env.')
DEBUG = environment_boolean('DJANGO_DEBUG')
ALLOWED_HOSTS = environment_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
APPEND_SLASH = False  # O contrato Angular usa /api/orders, sem barra final.

# Aplicações: framework, bibliotecas e domínio separados.
DJANGO_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
]
LOCAL_APPS = ['maintenance.apps.MaintenanceConfig']
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
TEMPLATES = []  # A interface é Angular; documentos usam um Engine isolado nos serviços.

# PostgreSQL: aceita DATABASE_URL existente ou BD_*.
# BD_NOME seleciona explicitamente o formato por campos; sem ele, usa DATABASE_URL.
if os.getenv('BD_NOME'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['BD_NOME'],
        'USER': os.getenv('BD_USUARIO', 'mantis'),
        'PASSWORD': os.getenv('BD_SENHA', ''),
        'HOST': os.getenv('BD_HOST', '127.0.0.1'),
        'PORT': os.getenv('BD_PORT', '5433'),
        'CONN_MAX_AGE': 60,
    }}
else:
    connection = urlparse(os.getenv('DATABASE_URL', ''))
    if connection.scheme not in ('postgres', 'postgresql') or not connection.hostname or not connection.path.strip('/'):
        raise ImproperlyConfigured('Defina DATABASE_URL ou BD_NOME/BD_USUARIO/BD_SENHA/BD_HOST/BD_PORT no .env.')
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(connection.path.lstrip('/')),
        'USER': unquote(connection.username or ''),
        'PASSWORD': unquote(connection.password or ''),
        'HOST': connection.hostname,
        'PORT': connection.port or 5432,
        'CONN_MAX_AGE': 60,
        'OPTIONS': {key: values[-1] for key, values in parse_qs(connection.query).items()
                    if key in ('sslmode', 'connect_timeout')},
    }}

# Identidade: mantém matrícula, perfis e hashes existentes do Mantis.
AUTH_USER_MODEL = 'maintenance.User'
AUTHENTICATION_BACKENDS = ['maintenance.backends.RegistrationBackend']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
API_TOKEN_MAX_AGE = 8 * 60 * 60

# REST Framework: um único fluxo de autenticação para todos os endpoints.
# Bearer assinado preserva o Angular e a invalidação após troca de senha/desativação.
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

# Angular: proxy em desenvolvimento e origens explícitas para chamadas diretas.
CORS_ALLOWED_ORIGINS = environment_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:4200,http://127.0.0.1:4200,http://localhost:4201,http://127.0.0.1:4201',
)
CORS_ALLOW_CREDENTIALS = False  # A API autentica pelo cabeçalho; não por cookie.
CSRF_TRUSTED_ORIGINS = environment_list('CSRF_TRUSTED_ORIGINS')

# Idioma, datas, arquivos e limites já utilizados pelo Mantis.
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Manaus'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SECURE = environment_boolean('DJANGO_COOKIE_SECURE')
CSRF_COOKIE_SECURE = environment_boolean('DJANGO_COOKIE_SECURE')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO')},
}
