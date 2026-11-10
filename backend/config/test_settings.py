"""Configuração exclusiva de testes rápidos: SQLite em memória e hash simplificado. Não usar para execução normal ou produção."""

import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-secret-key-with-at-least-32-characters')
os.environ.setdefault('DATABASE_URL', 'postgresql://unused:unused@localhost/unused')
from .settings import *  # noqa: F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MIGRATION_MODULES = {'maintenance': None}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
