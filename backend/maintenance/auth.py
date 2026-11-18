"""Compatibilidade de autenticação com as contas existentes na implementação anterior."""

import bcrypt
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from .models import UserCode as UserCode

class RegistrationBackendCode(BaseBackend):
    """Autentica por matrícula e migra hashes bcrypt legados para o padrão Django após um login válido."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        """Procura conta ativa por matrícula; confere senha e converte o hash bcrypt antigo após um login válido."""
        registration_number = username or kwargs.get('registration')
        try:
            user_value = UserCode.objects.get(registration=registration_number, active=True)
        except UserCode.DoesNotExist:
            make_password(password)
            return None
        if user_value.password.startswith(('$2a$', '$2b$', '$2y$')):
            try:
                valid_password = bcrypt.checkpw(password.encode()[:72], user_value.password.encode())
            except (ValueError, TypeError):
                valid_password = False
            if valid_password:
                user_value.set_password(password)
                user_value.save(update_fields=['password'])
                return user_value
        elif user_value.check_password(password):
            return user_value
        return None

    def get_user(self, user_id):
        """Recupera uma conta ativa pelo ID para integração com a infraestrutura de autenticação Django."""
        return UserCode.objects.filter(pk=user_id, active=True).first()

# O caminho antigo continua aceito pelas configurações existentes.
RegistrationBackend = RegistrationBackendCode
