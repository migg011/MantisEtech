"""Catálogo e documento imprimível das preventivas, restritos à equipe técnica."""
import json
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import Context, Engine
from django.utils import timezone

from .base import operation, request_body
from ..exceptions import ApiError
from .common import MAINTENANCE_ROLES, positive_id
from ..filters import PreventiveScheduleFilter, apply_filters
from ..models import Equipment, EquipmentPreventive, EquipmentType, PreventiveChecklist, PreventiveExecution
from .preventive_schedule import schedule_data

FREQUENCIES = dict(PreventiveChecklist._meta.get_field('frequency').choices)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def calendar_template(context):
    """Base provisória autenticada de 2026. Não cria OS, agendas, usuários ou vínculos por semelhança de nomes."""
    source = Path(__file__).resolve().parent.parent / 'document_templates' / 'preventive_calendar_2026.json'
    if not source.exists():
        raise ApiError('Base do calendário ainda não foi preparada.', 404)
    return json.loads(source.read_text(encoding='utf-8'))


def select_equipment(data):
    """Lê equipmentTypeId e frequency recebidos pela API; busca o tipo existente e rejeita uma periodicidade fora do catálogo. Retorna o tipo e o código da frequência."""
    kind = get_object_or_404(EquipmentType, pk=positive_id(data.get('equipmentTypeId')))
    frequency = data.get('frequency')
    if not isinstance(frequency, str) or frequency not in FREQUENCIES:
        raise ApiError('Selecione uma periodicidade válida.')
    return kind, frequency


@operation(['GET', 'PUT'], roles=MAINTENANCE_ROLES)
def checklist(context):
    """GET lê o roteiro; PUT salva itens validados. Com equipmentId, trabalha no roteiro específico da agenda; sem ele, no padrão do tipo. Retorna os itens e sua origem para a tela."""
    data = context.filters if context.method == 'GET' else request_body(context)
    kind, frequency = select_equipment(data)
    if data.get('equipmentId'):
        machine = get_object_or_404(Equipment, pk=positive_id(data.get('equipmentId')),
                                    equipment_type=kind, active=True)
        with transaction.atomic():
            Equipment.objects.select_for_update().get(pk=machine.pk)
            schedule = get_object_or_404(EquipmentPreventive, equipment=machine, frequency=frequency, active=True)
            if context.method == 'PUT':
                schedule.checklist_items = None if data.get('useTypeDefault') is True else validate_items(
                    data.get('items'))
                schedule.save(update_fields=['checklist_items'])
            template = PreventiveChecklist.objects.filter(equipment_type=kind, frequency=frequency).first()
            return {
                'items': schedule.checklist_items if schedule.checklist_items is not None else template.items if template else [],
                'source': 'EQUIPAMENTO' if schedule.checklist_items is not None else 'TIPO'}
    if context.method == 'PUT':
        items = validate_items(data.get('items'))
        template, _ = PreventiveChecklist.objects.update_or_create(
            equipment_type=kind, frequency=frequency, defaults={'items': [record.strip() for record in items]})
    else:
        template = PreventiveChecklist.objects.filter(equipment_type=kind, frequency=frequency).first()
    return {'items': template.items if template else [], 'source': 'TIPO'}


def validate_items(items):
    """Recebe a lista de atividades e exige de 1 a 100 textos não vazios, de até 500 caracteres. Retorna uma nova lista sem espaços nas extremidades ou levanta APIError."""
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or any(
            not isinstance(record, str) or not record.strip() or len(record) > 500 for record in items):
        raise ApiError('Informe de 1 a 100 itens, com até 500 caracteres por item.')
    return [record.strip() for record in items]


@operation(['GET'], roles=MAINTENANCE_ROLES)
def document(context):
    """Gera a prévia HTML do checklist pela rota anterior à OS numerada. Confere máquina ativa e agenda e usa o roteiro padrão do tipo; a interface atual imprime pela rota da OS."""
    kind, frequency = select_equipment(context.filters)
    machine = get_object_or_404(Equipment.objects.select_related('line', 'sector'),
                                pk=positive_id(context.filters.get('equipmentId')), equipment_type=kind,
                                active=True)
    schedule = get_object_or_404(EquipmentPreventive, equipment=machine, frequency=frequency, active=True)
    template = get_object_or_404(PreventiveChecklist, equipment_type=kind, frequency=frequency)
    if not template.items:
        raise ApiError('Cadastre os itens do checklist antes de gerar o arquivo.')
    engine = Engine(dirs=[str(Path(__file__).resolve().parent.parent / 'document_templates')])
    document_html = engine.get_template('preventive_checklist.html').render(Context({
        'machine': machine, 'kind': kind, 'frequency': FREQUENCIES[frequency],
        'items': template.items, 'technician': context.user.name, 'issued': timezone.localtime(),
        'schedule': schedule,
    }))
    response = HttpResponse(document_html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="checklist-{machine.pk}-{frequency.lower()}.html"'
    return response


@operation(['GET'], roles=MAINTENANCE_ROLES)
def schedules(context):
    """O status é calculado pela data local a cada consulta, sem depender do navegador."""
    today = timezone.localdate()
    records = EquipmentPreventive.objects.filter(active=True, equipment__active=True).select_related(
        'equipment__equipment_type', 'equipment__sector', 'equipment__line').order_by('next_due', 'id')
    records = apply_filters(PreventiveScheduleFilter, context.filters, records)
    result = []
    for line in records:
        machine = line.equipment
        days = (line.next_due - today).days
        result.append(
            {**schedule_data(line), 'equipment_id': machine.pk, 'equipment_type_id': machine.equipment_type_id,
             'equipment_name': machine.name or machine.model or machine.equipment_type.name,
             'type_name': machine.equipment_type.name, 'asset_number': machine.asset_number,
             'serial': machine.serial, 'sector_name': machine.sector.name if machine.sector else None,
             'line_name': machine.line.name if machine.line else None, 'days_remaining': days,
             'status': 'VENCIDA' if days < 0 else 'HOJE' if days == 0 else 'EM_DIA'})
    unconfigured = Equipment.objects.filter(active=True).exclude(preventive_schedules__active=True).count()
    return {'today': today, 'schedules': result, 'unconfigured_count': unconfigured}


@operation(['POST'], roles=MAINTENANCE_ROLES)
def complete(context, pk):
    """Bloqueia a rota antiga de conclusão sem atividades e orienta emitir uma OS preventiva. As execuções antigas permanecem no histórico."""
    raise ApiError('Emita uma OS preventiva e registre os itens executados para concluir a manutenção.', 409)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def history(context):
    """GET lista as últimas 100 execuções, com filtro opcional equipmentId. Nas execuções com OS, usa o nome e o executor preservados; nos registros antigos, usa os vínculos disponíveis."""
    records = PreventiveExecution.objects.select_related('schedule__equipment', 'technician', 'order')
    if context.filters.get('equipmentId'):
        records = records.filter(schedule__equipment_id=positive_id(context.filters['equipmentId']))
    return [{'id': line.pk, 'equipment_id': line.schedule.equipment_id,
             'equipment_name': line.order.equipment_snapshot.get('name',
                                                                  '') if line.order_id else line.schedule.equipment.name or line.schedule.equipment.model or str(
                 line.schedule.equipment_id),
             'frequency': line.schedule.frequency, 'performed_date': line.performed_date,
             'previous_due': line.previous_due, 'next_due': line.next_due,
             'technician_name': line.order.executor_name if line.order_id else line.technician.name,
             'notes': line.notes,
             'order_id': line.order_id, 'order_number': line.order.number if line.order_id else None} for line in
            records[:100]]
