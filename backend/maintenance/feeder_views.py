"""Cadastro de feeders e histórico de manutenção por setor."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .api import APIErrorCode, STAFFCode, body_value, endpoint_value, positive_id_value, record_value, sector_scope
from .models import Feeder, FeederMaintenanceType, FeederPlatform, FeederTape, Line, Sector
from .schedule_rules import parse_date_value


def feeder_text(data, field, label, limit, *, optional=False):
    value = data.get(field, '')
    if not isinstance(value, str) or '\x00' in value or len(value.strip()) > limit or (not optional and not value.strip()):
        raise APIErrorCode(f'{label}: informe um texto de até {limit} caracteres.')
    return value.strip()


def feeder_data(feeder):
    return {**record_value(feeder), 'line_name': feeder.line.name if feeder.line else None}


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def sector_feeders(request, sector_id):
    if not request.user.is_admin and request.user.sector_id != sector_id:
        raise PermissionDenied
    if request.method == 'GET':
        sector = get_object_or_404(Sector, pk=sector_id, active=True)
        lines = list(Line.objects.filter(sector=sector, active=True).values('id', 'name'))
        for line in lines:
            line['platforms'] = FeederPlatform.values
        feeders = Feeder.objects.filter(sector=sector).select_related('line')
        return {
            'sector_name': sector.name,
            'lines': lines,
            'sector_platforms': [] if lines else FeederPlatform.values,
            'feeders': [feeder_data(feeder) for feeder in feeders],
        }

    data = body_value(request)
    with transaction.atomic():
        sector = get_object_or_404(Sector.objects.select_for_update(), pk=sector_id, active=True)
        lines = Line.objects.filter(sector=sector, active=True)
        line_id = data.get('line_id')
        if line_id is not None:
            line_id = positive_id_value(line_id, 'Linha')
            if not lines.filter(pk=line_id).exists():
                raise APIErrorCode('Selecione uma linha deste setor.')
        elif lines.exists():
            raise APIErrorCode('Selecione uma linha deste setor.')

        platform = data.get('platform')
        if platform not in FeederPlatform.values:
            raise APIErrorCode('Selecione NXT ou NPM para este cadastro.')

        details = {}
        if platform == FeederPlatform.NPM:
            tape_type = data.get('tape_type', '')
            if tape_type not in ['', *FeederTape.values]:
                raise APIErrorCode('Selecione um tipo de fita válido.')
            details = {
                'model_number': feeder_text(data, 'model_number', 'Modelo', 100, optional=True),
                'serial_number': feeder_text(data, 'serial_number', 'Número de série', 100, optional=True),
                'tape_type': tape_type,
                'manufacturing_code': feeder_text(data, 'manufacturing_code', 'Código de fabricação', 40, optional=True),
            }

        feeder = Feeder.objects.create(
            sector=sector,
            line_id=line_id,
            platform=platform,
            part_number=feeder_text(data, 'part_number', 'Part Number', 100),
            width=feeder_text(data, 'width', 'Largura', 40),
            **details,
        )
    return JsonResponse(feeder_data(feeder), status=201)


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def feeder_maintenance(request, sector_id, feeder_id, preventives_only=False):
    feeder = get_object_or_404(sector_scope(Feeder.objects.all(), request.user), pk=feeder_id, sector_id=sector_id, sector__active=True)
    if request.method == 'GET':
        entries = feeder.maintenance_records.all()
        if preventives_only:
            return list(entries.filter(kind=FeederMaintenanceType.PREVENTIVE).values('id', 'date', 'description'))
        return list(entries.values('id', 'kind', 'date', 'description'))

    data = body_value(request)
    kind = FeederMaintenanceType.PREVENTIVE if preventives_only else data.get('kind')
    if kind not in FeederMaintenanceType.values:
        raise APIErrorCode('Selecione preventiva ou conserto.')
    entry = feeder.maintenance_records.create(
        kind=kind,
        date=parse_date_value(data.get('date'), 'Data da manutenção'),
        description=feeder_text(data, 'description', 'Descrição', 4000),
    )
    excluded = ('feeder', 'kind') if preventives_only else ('feeder',)
    return JsonResponse(record_value(entry, excluded), status=201)
