"""Catálogo e documento imprimível das preventivas, restritos à equipe técnica."""
from .compatibility_value import adapt_call
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from pathlib import Path
import json
from django.template import Context, Engine
from django.utils import timezone
from django.db import transaction

from .api import APIErrorCode, STAFFCode, body_value, endpoint_value, positive_id_value, sector_scope, visible_equipment_value
from .models import EquipmentCode, EquipmentTypeCode, PreventiveChecklistCode, EquipmentPreventiveCode, PreventiveExecutionCode
from .schedule_rules import schedule_data_value
from .preventive_planning import annual_window

FREQUENCIES = dict(PreventiveChecklistCode._meta.get_field('frequency').choices)


@endpoint_value(['GET'], roles_value=STAFFCode)
def calendar_template_value(request_value):
    """Base provisória autenticada de 2026. Não cria OS, agendas, usuários ou vínculos por semelhança de nomes."""
    source_value = Path(__file__).resolve().parent / 'document_templates' / 'preventive_calendar_2026.json'
    if not source_value.exists():
        raise APIErrorCode('Base do calendário ainda não foi preparada.', 404)
    return json.loads(source_value.read_text(encoding='utf-8'))


def selection_value(data_value):
    """Lê equipmentTypeId e frequency recebidos pela API; busca o tipo existente e rejeita uma periodicidade fora do catálogo. Retorna o tipo e o código da frequência."""
    kind = get_object_or_404(EquipmentTypeCode, pk=positive_id_value(data_value.get('equipmentTypeId')))
    frequency_value = data_value.get('frequency')
    if not isinstance(frequency_value, str) or frequency_value not in FREQUENCIES:
        raise APIErrorCode('Selecione uma periodicidade válida.')
    return kind, frequency_value


@endpoint_value(['GET', 'PUT'], roles_value=STAFFCode)
def checklist_value(request_value):
    """GET lê o roteiro; PUT salva itens validados. Com equipmentId, trabalha no roteiro específico da agenda; sem ele, no padrão do tipo. Retorna os itens e sua origem para a tela."""
    data_value = request_value.GET if request_value.method == 'GET' else body_value(request_value)
    kind, frequency_value = selection_value(data_value)
    if data_value.get('equipmentId'):
        machine = get_object_or_404(visible_equipment_value(request_value.user), pk=positive_id_value(data_value.get('equipmentId')), equipment_type=kind, active=True)
        with transaction.atomic():
            EquipmentCode.objects.select_for_update().get(pk=machine.pk)
            schedule_value = get_object_or_404(EquipmentPreventiveCode, equipment=machine, frequency=frequency_value, active=True)
            if request_value.method == 'PUT':
                schedule_value.checklist_items = None if data_value.get('useTypeDefault') is True else validate_items_value(data_value.get('items'))
                schedule_value.save(update_fields=['checklist_items'])
            template = PreventiveChecklistCode.objects.filter(equipment_type=kind, frequency=frequency_value).first()
            return {'items': schedule_value.checklist_items if schedule_value.checklist_items is not None else template.items if template else [],
                    'source': 'EQUIPAMENTO' if schedule_value.checklist_items is not None else 'TIPO'}
    if request_value.method == 'PUT':
        items_value = validate_items_value(data_value.get('items'))
        template, _ = PreventiveChecklistCode.objects.update_or_create(
            equipment_type=kind, frequency=frequency_value, defaults={'items': [item_value.strip() for item_value in items_value]})
    else:
        template = PreventiveChecklistCode.objects.filter(equipment_type=kind, frequency=frequency_value).first()
    return {'items': template.items if template else [], 'source': 'TIPO'}


def validate_items_value(items_value):
    """Recebe a lista de atividades e exige de 1 a 100 textos não vazios, de até 500 caracteres. Retorna uma nova lista sem espaços nas extremidades ou levanta APIError."""
    if not isinstance(items_value, list) or not 1 <= len(items_value) <= 100 or any(
            not isinstance(item_value, str) or not item_value.strip() or len(item_value) > 500 for item_value in items_value):
        raise APIErrorCode('Informe de 1 a 100 itens, com até 500 caracteres por item.')
    return [item_value.strip() for item_value in items_value]


@endpoint_value(['GET'], roles_value=STAFFCode)
def document_value(request_value):
    """Gera a prévia HTML do checklist pela rota anterior à OS numerada. Confere máquina ativa e agenda e usa o roteiro padrão do tipo; a interface atual imprime pela rota da OS."""
    kind, frequency_value = selection_value(request_value.GET)
    machine = get_object_or_404(visible_equipment_value(request_value.user),
                                pk=positive_id_value(request_value.GET.get('equipmentId')), equipment_type=kind, active=True)
    schedule_value = get_object_or_404(EquipmentPreventiveCode, equipment=machine, frequency=frequency_value, active=True)
    template = get_object_or_404(PreventiveChecklistCode, equipment_type=kind, frequency=frequency_value)
    if not template.items:
        raise APIErrorCode('Cadastre os itens do checklist antes de gerar o arquivo.')
    engine = Engine(dirs=[str(Path(__file__).resolve().parent / 'document_templates')])
    html_value = engine.get_template('preventive_checklist.html').render(Context({
        'machine': machine, 'kind': kind, 'frequency': FREQUENCIES[frequency_value],
        'items': template.items, 'technician': request_value.user.name, 'issued': timezone.localtime(), 'schedule': schedule_value,
    }))
    response_value = HttpResponse(html_value, content_type='text/html; charset=utf-8')
    response_value['Content-Disposition'] = f'attachment; filename="checklist-{machine.pk}-{frequency_value.lower()}.html"'
    return response_value


@endpoint_value(['GET'], roles_value=STAFFCode)
def schedules_value(request_value):
    """O status é calculado pela data local a cada consulta, sem depender do navegador."""
    today = timezone.localdate()
    rows_value = EquipmentPreventiveCode.objects.filter(active=True, equipment__active=True).select_related(
        'equipment__equipment_type', 'equipment__sector', 'equipment__line').order_by('next_due', 'id')
    result_value = []
    for row_value in sector_scope(rows_value, request_value.user, 'equipment__sector'):
        machine = row_value.equipment
        deadline = row_value.next_due
        if row_value.frequency == 'ANUAL' and today > deadline:
            _, deadline = annual_window(deadline)
        days = (deadline - today).days
        result_value.append({**schedule_data_value(row_value), 'equipment_id': machine.pk, 'equipment_type_id': machine.equipment_type_id,
                       'equipment_name': machine.name or machine.model or machine.equipment_type.name,
                       'type_name': machine.equipment_type.name, 'asset_number': machine.asset_number,
                       'serial': machine.serial, 'sector_name': machine.sector.name if machine.sector else None,
                       'line_name': machine.line.name if machine.line else None, 'days_remaining': days,
                       'status': 'VENCIDA' if days < 0 else 'HOJE' if days == 0 else 'EM_DIA'})
    unconfigured = visible_equipment_value(request_value.user).exclude(preventive_schedules__active=True).count()
    return {'today': today, 'schedules': result_value, 'unconfigured_count': unconfigured}


@endpoint_value(['POST'], roles_value=STAFFCode)
def complete_value(request_value, pk):
    """Bloqueia a rota antiga de conclusão sem atividades e orienta emitir uma OS preventiva. As execuções antigas permanecem no histórico."""
    raise APIErrorCode('Emita uma OS preventiva e registre os itens executados para concluir a manutenção.', 409)


@endpoint_value(['GET'], roles_value=STAFFCode)
def history_value(request_value):
    """GET lista as últimas 100 execuções, com filtro opcional equipmentId. Nas execuções com OS, usa o nome e o executor preservados; nos registros antigos, usa os vínculos disponíveis."""
    rows_value = PreventiveExecutionCode.objects.select_related('schedule__equipment', 'technician', 'order')
    rows_value = sector_scope(rows_value, request_value.user, 'schedule__equipment__sector')
    if request_value.GET.get('equipmentId'):
        rows_value = rows_value.filter(schedule__equipment_id=positive_id_value(request_value.GET['equipmentId']))
    return [{'id': row_value.pk, 'equipment_id': row_value.schedule.equipment_id,
             'equipment_name': row_value.order.equipment_snapshot.get('name', '') if row_value.order_id else row_value.schedule.equipment.name or row_value.schedule.equipment.model or str(row_value.schedule.equipment_id),
             'frequency': row_value.schedule.frequency, 'performed_date': row_value.performed_date,
             'previous_due': row_value.previous_due, 'next_due': row_value.next_due,
             'technician_name': row_value.order.executor_name if row_value.order_id else row_value.technician.name, 'notes': row_value.notes,
             'order_id': row_value.order_id, 'order_number': row_value.order.number if row_value.order_id else None} for row_value in rows_value[:100]]

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
calendar_template = adapt_call(calendar_template_value, {'request': 'request_value'})
selection = adapt_call(selection_value, {'data': 'data_value'})
checklist = adapt_call(checklist_value, {'request': 'request_value'})
validate_items = adapt_call(validate_items_value, {'items': 'items_value'})
document = adapt_call(document_value, {'request': 'request_value'})
schedules = adapt_call(schedules_value, {'request': 'request_value'})
complete = adapt_call(complete_value, {'request': 'request_value'})
history = adapt_call(history_value, {'request': 'request_value'})
