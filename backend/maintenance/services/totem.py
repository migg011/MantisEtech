"""Caso de uso de sessão de operador no totem."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .base import Result, operation, request_body
from .common import positive_id
from ..exceptions import ApiError
from ..models import Line, OperatorSession


def _session_data(session):
    """Serializa a sessão de operador para a tela do totem."""
    return {
        'id': str(session.pk),
        'userId': session.user_id,
        'lineId': session.line_id,
        'openedAt': session.opened_at.isoformat(),
        'expiresAt': session.expires_at.isoformat(),
    }


@operation(['GET', 'POST'], roles=('OPERADOR', 'TECNICO', 'ADMINISTRADOR'))
def operator_sessions(context):
    """Abre uma sessão de operador no totem ou lista as sessões ativas do próprio usuário."""
    now = timezone.now()
    if context.method == 'GET':
        active = OperatorSession.objects.filter(user=context.user, expires_at__gt=now).select_related('line')
        return [_session_data(session) for session in active]
    data = request_body(context)
    line_id = data.get('lineId')
    line = None
    if line_id is not None:
        line = get_object_or_404(Line, pk=positive_id(line_id, 'Linha'), active=True)
    with transaction.atomic():
        OperatorSession.objects.filter(user=context.user, expires_at__lte=now).delete()
        OperatorSession.objects.filter(user=context.user, expires_at__gt=now).delete()
        duration = int(getattr(settings, 'API_TOKEN_MAX_AGE', 3600))
        session = OperatorSession.objects.create(
            user=context.user, line=line, expires_at=now + timedelta(seconds=duration))
    return Result(_session_data(session), status=201)


@operation(['DELETE'], roles=('OPERADOR', 'TECNICO', 'ADMINISTRADOR'))
def close_operator_session(context, pk):
    """Encerra a sessão de operador, invalidando o vínculo com a linha."""
    session = get_object_or_404(OperatorSession, pk=pk)
    if session.user_id != context.user.pk and not context.user.is_admin:
        raise PermissionDenied
    session.delete()
    return {'message': 'Sessão encerrada.'}
