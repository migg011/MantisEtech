"""Dados de entrada/saída dos casos de uso, sem dependência de Request do DRF."""
from dataclasses import dataclass, field
from typing import Any, Callable

from django.core.exceptions import PermissionDenied

from ..exceptions import ApiError


@dataclass
class OperationContext:
    user: Any = None
    method: str = 'GET'
    filters: Any = field(default_factory=dict)
    data: Any = field(default_factory=dict)
    source: str = ''


@dataclass
class Result:
    data: Any
    status: int = 200


def request_body(context):
    """O parsing HTTP pertence à view; serviços recebem apenas objetos JSON."""
    if not isinstance(context.data, dict):
        raise ApiError('O corpo deve ser um objeto JSON.')
    return context.data


def operation(methods, *, roles=None, public=False):
    """Declara o contrato do caso de uso e protege também chamadas internas."""

    def decorate(function: Callable):
        from functools import wraps

        @wraps(function)
        def execute(context, *args, **kwargs):
            if context.method not in methods:
                raise ApiError('Método não permitido.', 405)
            if not public:
                if context.user is None or not context.user.is_active:
                    raise ApiError('Autenticação necessária.', 401)
                if roles and context.user.role not in roles:
                    raise PermissionDenied
            return function(context, *args, **kwargs)

        execute.methods = tuple(methods)
        execute.roles = tuple(roles or ())
        execute.public = public
        return execute

    return decorate
