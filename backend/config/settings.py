"""Configura a API Django: ambiente, PostgreSQL, autenticação por matrícula, idioma, fuso e limites de upload."""

import os
from pathlib import Path
from urllib.parse import quote
from urllib.parse import unquote, urlparse, parse_qs

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Carrega a configuração local sem substituir variáveis fornecidas pelo ambiente de execução.
local_env = BASE_DIR / '.env'
load_dotenv(local_env if local_env.is_file() else BASE_DIR.parent / '.env')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY com pelo menos 32 caracteres no .env.')
DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'maintenance',
]
MIDDLEWARE = [
    # A API autentica por Authorization: Bearer; não utiliza sessão ou cookie para conceder acesso.
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = []
# O Angular serve a interface. Este processo publica a API e não procura templates ou arquivos de frontend.
APPEND_SLASH = False
WSGI_APPLICATION = 'config.wsgi.application'
# A URL é convertida nos parâmetros usados pelo driver psycopg; o navegador nunca recebe a senha do banco.
database_url = os.getenv('DATABASE_URL')
if not database_url and os.getenv('BD_NOME'):
    # Compatibilidade com o .env das instalações anteriores.
    db_user = quote(os.getenv('BD_USUARIO', 'mantis'), safe='')
    db_password = quote(os.getenv('BD_SENHA', ''), safe='')
    db_host = os.getenv('BD_HOST', '127.0.0.1')
    db_port = os.getenv('BD_PORT', '5433')
    db_name = quote(os.environ['BD_NOME'], safe='')
    database_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
database = urlparse(database_url or '')
if database.scheme not in ('postgres', 'postgresql') or not database.hostname or not database.path.strip('/'):
    raise ImproperlyConfigured('Defina DATABASE_URL com uma conexão PostgreSQL válida.')
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(database.path.lstrip('/')),
    'USER': unquote(database.username or ''), 'PASSWORD': unquote(database.password or ''),
    'HOST': database.hostname, 'PORT': database.port or 5432, 'CONN_MAX_AGE': 60,
    'OPTIONS': {key: values[-1] for key, values in parse_qs(database.query).items() if key in ('sslmode', 'connect_timeout')},
}}
AUTH_USER_MODEL = 'maintenance.User'
# Permite login por matrícula e atualização de hashes bcrypt da implementação anterior.
AUTHENTICATION_BACKENDS = ['maintenance.auth.RegistrationBackendCode']
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Manaus'
USE_I18N = True
# Armazena instantes com fuso; a interface formata os horários para o usuário.
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
API_TOKEN_MAX_AGE = 8 * 60 * 60
# A idade acima é conferida na assinatura do token, independentemente do estado salvo no navegador.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
