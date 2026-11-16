"""Caso de uso do registro de atividades: listagem paginada para o administrador."""
from django.db.models import Q

from .base import operation
from ..exceptions import ApiError
from ..models import ActivityLog


@operation(['GET'], roles=('ADMINISTRADOR',))
def activity_log(context):
    """Lista o registro de atividades com filtros por autor e método, paginado em 50 linhas."""
    entries = ActivityLog.objects.all()
    actor = (context.filters.get('actor') or '').strip()[:160]
    if actor:
        entries = entries.filter(Q(actor_name__icontains=actor) | Q(actor_registration__icontains=actor))
    method = context.filters.get('method')
    if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        entries = entries.filter(method=method)
    try:
        page = int(context.filters.get('page', '1'))
    except (TypeError, ValueError):
        raise ApiError('Página inválida.')
    if not 1 <= page <= 100000:
        raise ApiError('Página inválida.')
    start = (page - 1) * 50
    rows = list(entries.values()[start:start + 51])
    return {'items': rows[:50], 'has_next': len(rows) > 50}
