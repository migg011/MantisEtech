"""Casos de uso de feeders: cadastro, listagem e histórico de preventivas/consertos."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from .base import Result, operation, request_body
from .common import MAINTENANCE_ROLES, form_data, require_role, serialize_record, validate_form
from ..exceptions import ApiError
from .. import forms
from ..filters import FeederFilter, apply_filters
from ..models import Feeder, FeederMaintenance


def visible_feeders(user):
    """Restringe técnicos e operadores ao setor próprio; o administrador vê todos os feeders."""
    items = Feeder.objects.select_related('sector', 'line')
    if user.is_admin:
        return items
    if user.sector_id:
        return items.filter(sector_id=user.sector_id)
    return items.none()


def feeder_data(record):
    """Serializa o feeder adicionando o setor e a linha para uso na tela."""
    data = serialize_record(record)
    data['sector_name'] = record.sector.name if record.sector else None
    data['line_name'] = record.line.name if record.line else None
    return data


def maintenance_data(record):
    """Serializa a entrada de preventiva/conserto do feeder."""
    return serialize_record(record)


@operation(['GET', 'POST', 'PATCH'])
def feeders(context, pk=None):
    """Lista, cria ou atualiza feeders respeitando o setor do usuário."""
    if context.method == 'GET':
        if pk:
            record = get_object_or_404(visible_feeders(context.user), pk=pk)
            return feeder_data(record)
        records = apply_filters(FeederFilter, context.filters, visible_feeders(context.user))
        return [feeder_data(feeder) for feeder in records[:500]]
    require_role(context, *MAINTENANCE_ROLES)
    with transaction.atomic():
        record = get_object_or_404(Feeder.objects.select_for_update(), pk=pk) if pk else Feeder()
        data = form_data(forms.FeederForm, request_body(context), instance=record if pk else None,
                         aliases={'sectorId': 'sector', 'lineId': 'line'})
        form = validate_form(forms.FeederForm(data, instance=record))
        if not context.user.is_admin and form.cleaned_data['sector'].pk != context.user.sector_id:
            raise PermissionDenied
        record = form.save()
    return Result(feeder_data(record), status=200 if pk else 201)


@operation(['GET', 'POST'])
def feeder_maintenance(context, pk):
    """Lista o histórico ou registra uma nova preventiva/conserto do feeder."""
    feeder = get_object_or_404(visible_feeders(context.user), pk=pk)
    if context.method == 'GET':
        return [maintenance_data(entry) for entry in feeder.maintenance_records.all()]
    require_role(context, *MAINTENANCE_ROLES)
    data = form_data(forms.FeederMaintenanceForm, request_body(context),
                     aliases={'feederId': 'feeder'})
    data['feeder'] = feeder.pk
    form = validate_form(forms.FeederMaintenanceForm(data))
    record = form.save()
    return Result(maintenance_data(record), status=201)
