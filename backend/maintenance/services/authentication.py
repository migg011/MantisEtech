"""Casos de uso de autenticacao do Mantis, separados do transporte HTTP."""

import hashlib

from django.contrib.auth import authenticate
from django.core.cache import cache

from .base import operation, request_body
from ..exceptions import ApiError
from ..authentication import issue_token
from .common import user_data


@operation(['GET'], public=True)
def health_check(context):
    """Identifica o processo da API para testar disponibilidade e encaminhamento pelo proxy Angular."""
    return {'service': 'MANTIS Django API', 'status': 'ok'}


@operation(['POST'], public=True)
def login(context):
    """Valida matrícula e senha, limita tentativas por origem e devolve token e usuário à tela de entrada."""
    data = request_body(context)
    # The API keeps the existing keys; the local variables are only for reading.
    registration, password = data.get('registration'), data.get('password')
    if not isinstance(registration, str) or not registration.strip() or not isinstance(password, str) or not password:
        raise ApiError('Informe matrícula e senha.')
    attempt_key = 'login:' + hashlib.sha256(context.source.encode()).hexdigest()
    cache.add(attempt_key, 0, 900)
    if cache.incr(attempt_key) > 10:
        raise ApiError('Muitas tentativas. Aguarde 15 minutos.', 429)
    user = authenticate(None, username=registration.strip(), password=password)
    if user is None:
        raise ApiError('Matrícula ou senha inválida.', 401)
    cache.delete(attempt_key)
    return {'token': issue_token(user), 'user': user_data(user, login=True)}


@operation(['GET'])
def current_user(context):
    """Devolve a conta conferida pelo token, permitindo consultar a identidade atual no backend."""
    return user_data(context.user, login=True)
