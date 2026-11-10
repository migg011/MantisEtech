"""Testes de integração em PostgreSQL separado do banco operacional mantis."""
from copy import deepcopy
from .settings import *  # noqa: F403

DATABASES = deepcopy(DATABASES)  # noqa: F405
DATABASES['default']['TEST'] = {'NAME': 'test_mantis_rest'}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
