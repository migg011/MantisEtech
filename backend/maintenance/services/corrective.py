"""Casos de uso de corretivas do Mantis, separados do transporte HTTP."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .base import Result, operation, request_body
from ..exceptions import ApiError
from ..filters import WorkOrderFilter, LinePendencyFilter, apply_filters
from .. import forms
from ..models import Equipment, Line, LinePendency, PartRequisition, PRIORITIES, ProblemType, PurchaseRequest, \
    SparePart, SparePartCompatibility, WorkOrder
from .purchases import purchase_data, save_purchase
from .common import form_data, visible_equipment, require_role, positive_id, visible_orders, serialize_record, \
    validate_form
from .common import MAINTENANCE_ROLES


@operation(['GET', 'POST', 'PATCH', 'DELETE'])
def problem_types(context, pk=None):
    """Permite consultar problemas ativos; manutenção do catálogo é exclusiva da equipe técnica."""
    if context.method == 'GET':
        items = ProblemType.objects.select_related('equipment_type')
        if context.filters.get('includeInactive') == 'true':
            require_role(context, *MAINTENANCE_ROLES)
        else:
            items = items.filter(active=True)
        if context.filters.get('equipmentTypeId'):
            kind_id = positive_id(context.filters['equipmentTypeId'])
            items = items.filter(Q(equipment_type=None) | Q(equipment_type_id=kind_id))
        return [{**serialize_record(record),
                 'type_name': record.equipment_type.name if record.equipment_type else None}
                for record in items]
    require_role(context, *MAINTENANCE_ROLES)
    with transaction.atomic():
        record = get_object_or_404(ProblemType.objects.select_for_update(), pk=pk) if pk else ProblemType()
        if context.method == 'DELETE':
            record.active = False
            record.save(update_fields=['active'])
            return {'ok': True}
        data = form_data(forms.ProblemTypeForm, request_body(context),
                         instance=record if pk else None,
                         aliases={'equipmentTypeId': 'equipment_type'})
        if not pk:
            data.setdefault('active', True)
            data.setdefault('priority', 'MEDIA')
        record = validate_form(forms.ProblemTypeForm(data, instance=record)).save()
        return Result(serialize_record(record), status=200 if pk else 201)


@operation(['GET', 'POST', 'PATCH'])
def work_orders(context, pk=None):
    """Abre OS no equipamento autorizado e registra atendimento, responsável e horários de execução."""
    if context.method == 'GET':
        if pk:
            return order_data(get_object_or_404(visible_orders(context.user), pk=pk))
        records = apply_filters(WorkOrderFilter, context.filters, visible_orders(context.user))
        if context.filters.get('lineId'):
            items = records.filter(equipment__line_id=positive_id(context.filters['lineId']))
            return [order_data(order) for order in items.exclude(status='CONCLUIDA')] + [
                order_data(order) for order in items.filter(status='CONCLUIDA')[:20]]
        return [order_data(order) for order in records[:200]]
    if context.method == 'POST':
        # Integration boundary: turn camelCase JSON into fields accepted by the ModelForm.
        received = request_body(context)
        report = received.get('occurrenceDescription', received.get('occurrence_description', ''))
        if not isinstance(report, str):
            raise ApiError('A descrição do ocorrido deve ser um texto.')
        data = form_data(forms.WorkOrderForm, received,
                         aliases={'equipmentId': 'equipment', 'problemTypeId': 'problem_type'})
        form = validate_form(forms.WorkOrderForm(data, user=context.user))
        if not visible_equipment(context.user).filter(pk=form.cleaned_data['equipment'].pk).exists():
            raise PermissionDenied
        record = form.save(commit=False)
        # Freeze the chosen option description even if the catalog is renamed later.
        record.problem = form.cleaned_data['problem_type'].name
        record.opened_by = context.user
        record.save()
        return Result(order_data(record), status=201)
    require_role(context, *MAINTENANCE_ROLES)
    with transaction.atomic():
        record = get_object_or_404(WorkOrder.objects.select_for_update(), pk=pk)
        if record.status == 'CONCLUIDA':
            raise ApiError('Esta OS já foi concluída.', 409)
        if not record.started_at or record.assigned_to_id != context.user.pk:
            raise ApiError('Inicie o atendimento com sua matrícula e senha antes de alterar esta OS.', 409)
        data = form_data(forms.WorkOrderUpdateForm, request_body(context), instance=record)
        record = validate_form(forms.WorkOrderUpdateForm(data, instance=record)).save(commit=False)
        if record.status not in ('EM_ANDAMENTO', 'CONCLUIDA'):
            raise ApiError('O atendimento iniciado deve permanecer em andamento ou ser concluído.', 409)
        # The server clock fixes the end and total; refreshing the screen later does not extend a finished stop.
        if record.status == 'CONCLUIDA' and not record.finished_at:
            record.finished_at = timezone.now()
            record.downtime_seconds = max(0, int((record.finished_at - record.created_at).total_seconds()))
        record.save()
        return order_data(record)


@operation(['GET'])
def line_status(context):
    """GET /api/line-status: entrega linhas visíveis, todas as OS ativas e as últimas 100 concluídas para o painel Angular."""
    lines = Line.objects.filter(active=True).select_related('sector').order_by('name')
    if context.user.role == 'OPERADOR':
        lines = lines.filter(pk=context.user.line_id)
    lines = list(lines)
    items = visible_orders(context.user).filter(equipment__line_id__in=[line.pk for line in lines])
    # Unlike the generic list, active orders are not limited to 200: no occurrence should disappear from the dashboard.
    active = list(items.exclude(status='CONCLUIDA').order_by('created_at'))
    history = list(items.filter(status='CONCLUIDA').order_by('-finished_at', '-created_at')[:100])
    return {
        'lines': [{**serialize_record(line), 'sector_name': line.sector.name if line.sector else None} for line
                  in lines],
        'orders': [order_data(record) for record in active + history], 'server_now': timezone.now().isoformat()}


def order_data(order):
    """Monta o JSON de uma OS com máquina, operador, técnico e minutos; duração concluída usa o total registrado."""
    end = order.finished_at or timezone.now()
    seconds = order.downtime_seconds if order.downtime_seconds is not None else max(0, int((
        end - order.created_at).total_seconds()))
    return {**serialize_record(order), 'model': order.equipment.model, 'serial': order.equipment.serial,
            'asset_number': order.equipment.asset_number, 'type_name': order.equipment.equipment_type.name,
            'line_id': order.equipment.line_id,
            'line_name': order.equipment.line.name if order.equipment.line else None,
            'opened_by': order.opened_by_id, 'assigned_to': order.assigned_to_id,
            'opened_by_name': order.opened_by.name,
            'assigned_to_name': order.assigned_to.name if order.assigned_to else None,
            'downtime_minutes': round(seconds / 60, 2), 'server_now': timezone.now().isoformat()}


@operation(['POST'], roles=MAINTENANCE_ROLES)
def start_service(context, pk):
    """POST /api/orders/:id/start: reconfirma a conta conectada e grava técnico/início uma única vez sob bloqueio transacional."""
    received_data = request_body(context)
    registration, password = received_data.get('registration'), received_data.get('password')
    if not isinstance(registration, str) or not isinstance(password, str):
        raise ApiError('Informe matrícula e senha.')
    key = f'order-start:{context.user.pk}'
    cache.add(key, 0, 900)
    if cache.incr(key) > 10:
        raise ApiError('Muitas tentativas. Aguarde 15 minutos.', 429)
    user = authenticate(None, username=registration.strip(), password=password)
    if not user or user.pk != context.user.pk:
        raise ApiError('Confirme a matrícula e senha do técnico conectado.', 403)
    cache.delete(key)
    with transaction.atomic():
        record = get_object_or_404(WorkOrder.objects.select_for_update(), pk=pk)
        if record.status == 'CONCLUIDA':
            raise ApiError('Esta OS já foi concluída.', 409)
        if record.started_at:
            if record.assigned_to_id != user.pk:
                raise ApiError('Esta OS já está em atendimento por outro técnico.', 409)
        else:
            record.started_at = timezone.now()
            record.assigned_to = user
            record.status = 'EM_ANDAMENTO'
            record.save(update_fields=['started_at', 'assigned_to', 'status'])
    return order_data(record)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def work_order_parts(context, pk):
    """Consulta peças ativas e destaca os vínculos cadastrados com a máquina desta OS."""
    order = get_object_or_404(visible_orders(context.user), pk=pk)
    parts = SparePart.objects.filter(active=True).defer('photo_data', 'datasheet_data').annotate(
        compatible=Exists(
            SparePartCompatibility.objects.filter(spare_part_id=OuterRef('pk'), equipment_id=order.equipment_id)))
    if context.filters.get('compatibleOnly') == 'true':
        parts = parts.filter(compatible=True)
    query = context.filters.get('q', '').strip()
    if query:
        parts = parts.filter(
            Q(description__icontains=query) | Q(part_number__icontains=query) | Q(manufacturer__icontains=query) | Q(
                code__icontains=query))
    return [{**serialize_record(part), 'compatible': part.compatible} for part in
            parts.order_by('-compatible', 'description')[:1000]]


@operation(['GET', 'POST'], roles=MAINTENANCE_ROLES)
def work_order_purchases(context, pk):
    """Vincula a solicitação à OS do endereço, impedindo a troca silenciosa de máquina."""
    order = get_object_or_404(visible_orders(context.user), pk=pk)
    if context.method == 'GET':
        items = PurchaseRequest.objects.filter(work_order=order).select_related('requester', 'manager', 'equipment')
        return [purchase_data(record) for record in items]
    received_data = request_body(context)
    for key, expected in [('workOrderId', order.pk), ('equipmentId', order.equipment_id)]:
        if key in received_data and positive_id(received_data[key]) != expected:
            raise ApiError('A solicitação deve pertencer à OS e à máquina selecionadas.')
        received_data[key] = expected
    return save_purchase(context, received_data)


@operation(['GET', 'POST'], roles=MAINTENANCE_ROLES)
def work_order_part_requisitions(context, pk):
    """Lista ou registra solicitação DIRETA de peça para a OS; deriva máquina/serial no servidor, sem criar compra."""
    order = get_object_or_404(visible_orders(context.user), pk=pk)

    def data_for(record):
        """Monta o JSON da solicitação direta incluindo descrição da peça, solicitante e situação solicitada."""
        return {**serialize_record(record), 'description': record.spare_part.description,
                'part_number': record.spare_part.part_number, 'requester_name': record.requester.name,
                'status': 'SOLICITADA'}

    if context.method == 'GET':
        return [data_for(record) for record in order.part_requisitions.select_related('spare_part', 'requester')]
    received_data = request_body(context)
    part = get_object_or_404(SparePart, pk=positive_id(received_data.get('sparePartId')), active=True)
    try:
        quantity = Decimal(str(received_data.get('quantity', '')))
        if not quantity.is_finite() or quantity <= 0 or quantity >= Decimal(
                '100000000000') or quantity.as_tuple().exponent < -3:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ApiError('Informe uma quantidade positiva com até três casas decimais.')
    note = received_data.get('note', '')
    if not isinstance(note, str) or len(note) > 5000:
        raise ApiError('Observação inválida (máximo de 5000 caracteres).')
    record = PartRequisition.objects.create(work_order=order, equipment=order.equipment,
                                            equipment_serial=order.equipment.serial, spare_part=part,
                                            quantity=quantity,
                                            requester=context.user, note=note.strip())
    return Result(data_for(record), status=201)


def pendency_data(record):
    """Serializa a pendência acrescentando os nomes da linha e dos autores para a listagem Angular."""
    return {**serialize_record(record), 'line_name': record.line.name,
            'equipment_model': record.equipment.model,
            'created_by_name': record.created_by.name,
            'resolved_by_name': record.resolved_by.name if record.resolved_by else None}


def active_pendencies():
    """Prepara a consulta de pendências com relacionamentos carregados para evitar uma consulta extra por nome exibido."""
    return LinePendency.objects.select_related('line', 'equipment', 'created_by', 'resolved_by')


@operation(['GET', 'POST'], roles=MAINTENANCE_ROLES)
def work_order_pendencies(context, pk):
    """Consulta ou cria pendência da OS, preservando linha e serial de origem independentemente do fechamento da OS."""
    order = get_object_or_404(visible_orders(context.user), pk=pk)
    if context.method == 'GET':
        return [pendency_data(record) for record in active_pendencies().filter(work_order=order)]
    received_data = request_body(context)
    description = received_data.get('description', '')
    priority = received_data.get('priority', 'MEDIA')
    if not isinstance(description, str) or not 5 <= len(description.strip()) <= 5000:
        raise ApiError('Descreva a pendência com 5 a 5000 caracteres.')
    if not isinstance(priority, str) or priority not in dict(PRIORITIES):
        raise ApiError('Prioridade inválida.')
    with transaction.atomic():
        equipment = get_object_or_404(Equipment.objects.select_for_update(), pk=order.equipment_id)
        if not equipment.line_id:
            raise ApiError('A máquina desta OS precisa estar vinculada a uma linha.', 409)
        record = LinePendency.objects.create(work_order=order, line_id=equipment.line_id,
                                             equipment=equipment, equipment_serial=equipment.serial,
                                             description=description.strip(),
                                             priority=priority, created_by=context.user)
    return Result(pendency_data(record), status=201)


@operation(['GET', 'PATCH'], roles=MAINTENANCE_ROLES)
def line_pendencies(context, pk=None):
    """Filtra pendências para a Central; no PATCH registra solução, responsável e horário sem sobrescrever uma resolução anterior."""
    if context.method == 'GET':
        items = apply_filters(LinePendencyFilter, context.filters, active_pendencies())
        if context.filters.get('lineId'):
            items = items.filter(line_id=positive_id(context.filters['lineId']))
        status = context.filters.get('status')
        if status:
            if status not in ('PENDENTE', 'RESOLVIDA'):
                raise ApiError('Situação inválida.')
            items = items.filter(status=status)
        return [pendency_data(record) for record in items]
    received_data = request_body(context)
    resolution = received_data.get('resolution', '')
    if received_data.get('status') != 'RESOLVIDA' or not isinstance(resolution, str) or not 5 <= len(
            resolution.strip()) <= 5000:
        raise ApiError('Informe a solução com 5 a 5000 caracteres para resolver a pendência.')
    with transaction.atomic():
        record = get_object_or_404(LinePendency.objects.select_for_update(), pk=pk)
        if record.status == 'RESOLVIDA':
            raise ApiError('Esta pendência já foi resolvida.', 409)
        record.status = 'RESOLVIDA'
        record.resolution = resolution.strip()
        record.resolved_by = context.user
        record.resolved_at = timezone.now()
        record.save(update_fields=['status', 'resolution', 'resolved_by', 'resolved_at'])
    return pendency_data(record)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def operations_dashboard(context):
    """Filtra os indicadores por linha e por janela de 7, 30 ou 90 dias."""
    from .dashboard import dashboard_summary
    days = context.filters.get('days', '30')
    if days not in ('7', '30', '90'):
        raise ApiError('Selecione um período de 7, 30 ou 90 dias.')
    equipment = visible_equipment(context.user)
    line = context.filters.get('lineId', '')
    if line:
        line_id = positive_id(line)
        get_object_or_404(Line, pk=line_id, active=True)
        equipment = equipment.filter(line_id=line_id)
    return dashboard_summary(equipment, visible_orders(context.user), int(days))
