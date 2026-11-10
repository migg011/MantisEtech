"""Casos de uso de organizacao do Mantis, separados do transporte HTTP."""

import base64
import binascii
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .base import Result, operation, request_body
from ..exceptions import ApiError
from .. import forms
from . import registrations
from ..filters import apply_filters, SectorFilter, LineFilter, EquipmentFilter
from ..models import Equipment, EquipmentAttachment, EquipmentType, Line, Sector
from .common import equipment_data, form_data, visible_equipment, require_role, positive_id, serialize_record, \
    validate_form
from .common import MAINTENANCE_ROLES


@operation(['GET', 'POST', 'PATCH', 'DELETE'], roles=MAINTENANCE_ROLES)
def sectors(context, pk=None):
    """Lista/cria setores e permite edição ou desativação administrativa sem apagar vínculos históricos."""
    if context.method == 'GET':
        return [serialize_record(record) for record in
                apply_filters(SectorFilter, context.filters, Sector.objects.filter(active=True))]
    if context.method != 'POST':
        require_role(context, 'ADMINISTRADOR')
    with transaction.atomic():
        record = get_object_or_404(Sector.objects.select_for_update(), pk=pk, active=True) if pk else Sector(
            code=registrations.generate_internal_code('SET'))
        if context.method == 'DELETE':
            if record.lines.exists() or Equipment.objects.filter(sector=record, active=True).exists():
                raise ApiError('O setor possui linhas ou equipamentos vinculados.', 409)
            record.active = False
            record.save(update_fields=['active'])
            return {'ok': True}
        data = form_data(forms.SectorForm, request_body(context), instance=record if pk else None)
        record = validate_form(forms.SectorForm(data, instance=record)).save()
        return Result(serialize_record(record), status=200 if pk else 201)


@operation(['PATCH'], roles=MAINTENANCE_ROLES)
def edit_line(context, pk):
    """Atualiza apenas nome e descrição, preservando código, setor, equipamentos e OS."""
    with transaction.atomic():
        record = get_object_or_404(Line.objects.select_for_update(), pk=pk, active=True)
        data = form_data(forms.LineEditForm, request_body(context), instance=record)
        form = validate_form(forms.LineEditForm(data, instance=record))
        form.save()
        return serialize_record(record)


@operation(['GET', 'POST'])
def lines(context):
    """Cadastra linhas por setor e calcula quantidade de equipamentos e comprimento para a interface."""
    if context.method == 'POST':
        require_role(context, *MAINTENANCE_ROLES)
        data = form_data(forms.LineForm, request_body(context), aliases={'sectorId': 'sector'})
        record = validate_form(forms.LineForm(data)).save(commit=False)
        record.code = registrations.generate_internal_code('LIN')
        record.save()
        return Result(serialize_record(record), status=201)
    items = Line.objects.filter(active=True).select_related('sector').annotate(
        equipment_count=Count('equipment', filter=Q(equipment__active=True)),
        length_mm=Sum('equipment__length_mm', filter=Q(equipment__active=True)))
    items = apply_filters(LineFilter, context.filters, items)
    if context.user.role == 'OPERADOR':
        items = items.filter(pk=context.user.line_id)
    return [{**serialize_record(record), 'sector_name': record.sector.name if record.sector else None,
             'equipment_count': record.equipment_count, 'length_mm': record.length_mm or 0} for record in items]


@operation(['POST'], roles=MAINTENANCE_ROLES)
def allocate_equipment(context, pk):
    """Valida os dados de montagem e delega alocação e histórico à transação de serviços."""
    data = request_body(context)
    equipment_id, position = positive_id(data.get('equipmentId')), positive_id(
        data.get('position'), 'Posição')
    registrations.allocate_equipment(pk, equipment_id, position, context.user)
    return Result(equipment_data(Equipment.objects.get(pk=equipment_id)), status=201)


@operation(['DELETE'], roles=MAINTENANCE_ROLES)
def remove_equipment(context, pk, equipment_pk):
    """Retira uma máquina da linha e registra sua devolução ao repositório do setor."""
    registrations.remove_equipment(pk, equipment_pk, context.user)
    return {'ok': True}


@operation(['POST'], roles=MAINTENANCE_ROLES)
def dismantle_line(context, pk):
    """Libera os equipamentos da linha e informa a quantidade devolvida, preservando cadastros e OS."""
    return {'ok': True, 'released': registrations.dismantle_line(pk, context.user)}


@operation(['GET'])
def equipment_types(context):
    """Fornece o catálogo de tipos que preenche o seletor do cadastro Angular."""
    return list(EquipmentType.objects.values('id', 'name'))


@operation(['GET', 'POST', 'PATCH', 'DELETE'])
def equipment(context, pk=None):
    """Consulta o repositório/linha e valida cadastros técnicos; editar ou desativar exige administrador."""
    if context.method == 'GET':
        # The Totem receives complete indicators without depending on the paginated order list.
        items = visible_equipment(context.user).prefetch_related('preventive_schedules').annotate(
            has_photo=Exists(EquipmentAttachment.objects.filter(equipment_id=OuterRef('pk'), kind='PHOTO')),
            open_order_count=Count('orders', filter=Q(orders__status__in=('ABERTA', 'EM_ANDAMENTO')), distinct=True),
            in_progress_order_count=Count('orders', filter=Q(orders__status='EM_ANDAMENTO'), distinct=True))
        if context.user.role != 'OPERADOR':
            items = apply_filters(EquipmentFilter, context.filters, items)
            for query, field in [('lineId', 'line_id'), ('sectorId', 'sector_id')]:
                if context.filters.get(query):
                    items = items.filter(**{field: positive_id(context.filters[query])})
            if context.filters.get('available') == 'true':
                items = items.filter(line=None)
        return [equipment_data(record) for record in items]
    require_role(context, *(MAINTENANCE_ROLES if context.method == 'POST' else ('ADMINISTRADOR',)))
    with transaction.atomic():
        record = get_object_or_404(Equipment.objects.select_for_update(), pk=pk,
                                   active=True) if pk else Equipment()
        if context.method == 'DELETE':
            if record.line_id or record.orders.exists():
                raise ApiError('Somente equipamentos disponíveis e sem OS podem ser excluídos.', 409)
            record.active = False
            record.save(update_fields=['active'])
            return {'ok': True}
        received_data = request_body(context)
        from .preventive_schedule import validate_schedules, sync_schedules
        # Missing in PATCH preserves the schedule; an empty list means uncheck the periodicities.
        selections = validate_schedules(
            received_data['preventiveSchedules']) if 'preventiveSchedules' in received_data else None
        data = form_data(forms.EquipmentForm, received_data, instance=record if pk else None,
                         aliases={'equipmentTypeId': 'equipment_type', 'sectorId': 'sector'})
        record = validate_form(forms.EquipmentForm(data, instance=record)).save()
        if selections is not None:
            sync_schedules(record, selections)
        return Result(equipment_data(record), status=200 if pk else 201)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def movements(context, pk):
    """Expõe o histórico de alocações e retiradas com nomes das linhas e do responsável."""
    record = get_object_or_404(Equipment, pk=pk)
    return [{**serialize_record(movement), 'from_line': movement.from_line.name if movement.from_line else None,
             'to_line': movement.to_line.name if movement.to_line else None,
             'performed_by_name': movement.performed_by.name,
             'from_sector_name': movement.from_sector.name if movement.from_sector else None,
             'to_sector_name': movement.to_sector.name if movement.to_sector else None}
            for movement in
            record.movements.select_related('from_line', 'to_line', 'from_sector', 'to_sector', 'performed_by')]


@operation(['POST'], roles=('ADMINISTRADOR',))
def transfer_equipment(context, pk):
    """Somente administrador transfere máquinas livres; mantém ID, anexos, agendas e OS."""
    data = request_body(context)
    equipment_record = registrations.transfer_equipment(pk, positive_id(data.get('originSectorId')),
                                                        positive_id(data.get('destinationSectorId')),
                                                        data.get('reason'), context.user)
    return equipment_data(equipment_record)


@operation(['GET', 'PUT'])
def attachments(context, pk, kind=None, download=False):
    """Lista metadados, baixa arquivos ou valida o base64 enviado pelo Angular antes de substituir o anexo."""
    record = get_object_or_404(visible_equipment(context.user), pk=pk)
    if kind and kind not in ('PHOTO', 'MANUAL'):
        raise ApiError('Categoria de anexo inválida.')
    if context.method == 'GET':
        if download:
            attachment = get_object_or_404(EquipmentAttachment, equipment=record, kind=kind)
            return FileResponse(io.BytesIO(bytes(attachment.content)), as_attachment=True,
                                filename=attachment.filename, content_type=attachment.mime_type)
        return [serialize_record(attachment) for attachment in record.attachments.defer('content')]
    require_role(context, *MAINTENANCE_ROLES)
    data = request_body(context)
    encoded, filename = data.get('base64'), data.get('filename')
    if not isinstance(filename, str) or not 1 <= len(filename.strip()) <= 180:
        raise ApiError('Nome de arquivo inválido.')
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError, TypeError):
        raise ApiError('Arquivo base64 inválido.')
    form = validate_form(
        forms.AttachmentForm({'kind': kind}, {'file': SimpleUploadedFile(filename, content)}))
    if data.get('mimeType') != form.cleaned_data['mime_type']:
        raise ApiError('Conteúdo do arquivo não corresponde ao tipo informado.')
    attachment, _ = EquipmentAttachment.objects.update_or_create(equipment=record, kind=kind, defaults={
        'filename': filename, 'content': content, 'mime_type': form.cleaned_data['mime_type'],
        'size_bytes': len(content), 'uploaded_by': context.user, 'created_at': timezone.now()})
    return serialize_record(attachment)
