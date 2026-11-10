"""Emissão, preenchimento e impressão de OS preventivas com histórico imutável."""
from datetime import time
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import Context, Engine
from django.utils import timezone

from .base import Result, operation, request_body
from ..exceptions import ApiError
from .common import MAINTENANCE_ROLES, positive_id
from ..filters import PreventiveOrderFilter, apply_filters
from ..models import Equipment, EquipmentPreventive, PreventiveChecklist, PreventiveExecution, PreventiveOrder, User
from .preventive import validate_items
from .preventive_schedule import calculate_next_due, parse_date

SAFETY_INSTRUCTIONS = (
    # This text is copied into the order: updating the default does not change old sheets.
    'Antes da atividade, desligar e isolar o equipamento conforme o procedimento de segurança aplicável. / '
    'Before servicing, shut down and isolate the equipment according to the applicable safety procedure.\n'
    'Utilizar os EPIs e observar os riscos descritos no procedimento do equipamento. / Use the required PPE and observe equipment-specific risks.\n'
    'Manter atenção às partes móveis e zonas de prensamento. / Stay clear of moving parts and pinch points.\n'
    'Respeitar a sinalização e reinstalar todas as proteções antes da liberação. / Follow safety signage and reinstall all guards before release.\n'
    'Executar somente atividades para as quais esteja autorizado. / Perform only authorized activities.'
)
RESULTS = {'PENDENTE': 'Pendente', 'REALIZADO': 'Realizado', 'NAO_REALIZADO': 'Não realizado', 'NA': 'Não aplicável'}


def order_data(order, detailed=False):
    """Converte uma OS em dados JSON para a lista. Com detail=True, inclui o roteiro, resultados, peças, orientações e observações; não modifica o registro."""
    data = {'id': order.pk, 'number': order.number, 'schedule_id': order.schedule_id,
            'equipment_id': order.schedule.equipment_id, 'equipment_name': order.equipment_snapshot.get('name', ''),
            'frequency': order.frequency, 'status': order.status, 'planned_date': order.planned_date,
            'planned_time': order.planned_time, 'performed_date': order.performed_date,
            'performed_time': order.performed_time, 'expected_due': order.expected_due,
            'recurrence_basis': order.recurrence_basis, 'assigned_to_id': order.assigned_to_id,
            'assigned_name': order.assigned_name, 'executor_name': order.executor_name,
            'revision': order.revision, 'created_at': order.created_at}
    if detailed:
        data.update(equipment_snapshot=order.equipment_snapshot, items=order.items, results=order.results,
                    safety_instructions=order.safety_instructions, parts=order.parts, notes=order.notes,
                    cancellation_reason=order.cancellation_reason)
    return data


@operation(['GET'], roles=MAINTENANCE_ROLES)
def technicians(context):
    """GET retorna somente ID e nome das contas técnicas/administrativas ativas para selecionar o responsável previsto, sem expor senhas ou outros dados da conta."""
    return list(User.objects.filter(active=True, role__in=MAINTENANCE_ROLES).values('id', 'name'))


@operation(['GET', 'POST'], roles=MAINTENANCE_ROLES)
def orders(context):
    """GET lista todas as OS abertas e as últimas 100 encerradas. POST valida agenda, previsão e responsável, impede duplicidade e salva uma cópia do roteiro e da identificação da máquina."""
    if context.method == 'GET':
        records = apply_filters(PreventiveOrderFilter, context.filters,
                                PreventiveOrder.objects.select_related('schedule'))
        if context.filters.get('equipmentId'):
            records = records.filter(schedule__equipment_id=positive_id(context.filters['equipmentId']))
        # All open orders must remain accessible regardless of history size.
        return [order_data(order) for order in records.filter(status='ABERTA')] + [order_data(order) for order in
                                                                                    records.exclude(
                                                                                        status='ABERTA')[:100]]
    data = request_body(context)
    schedule_id = positive_id(data.get('scheduleId'))
    expected = parse_date(data.get('expectedDueDate'), 'Vencimento apresentado')
    planned = parse_date(data.get('plannedDate'), 'Data prevista')
    basis = data.get('recurrenceBasis', 'PLANEJADA')
    if basis not in ('PLANEJADA', 'EXECUCAO'):
        raise ApiError('Selecione a regra do próximo vencimento.')
    raw_time = data.get('plannedTime')
    try:
        planned_time = time.fromisoformat(raw_time) if raw_time else None
        if planned_time and planned_time.tzinfo:
            raise ValueError
    except (TypeError, ValueError):
        raise ApiError('Horário previsto inválido.')
    assigned = get_object_or_404(User, pk=positive_id(data.get('assignedToId')), active=True,
                                 role__in=MAINTENANCE_ROLES)
    # Issuance confirms checklist, identification, and schedule link in the same transaction.
    with transaction.atomic():
        initial = get_object_or_404(EquipmentPreventive, pk=schedule_id)
        machine = get_object_or_404(
            Equipment.objects.select_for_update(of=('self',)).select_related('equipment_type', 'sector', 'line'),
            pk=initial.equipment_id, active=True)
        schedule = get_object_or_404(EquipmentPreventive.objects.select_for_update(), pk=schedule_id, active=True)
        existing = PreventiveOrder.objects.filter(schedule=schedule, status='ABERTA').first()
        if existing:
            raise ApiError(f'Já existe a OS {existing.number} aberta para esta preventiva.', 409,
                           {'orderId': existing.pk})
        if expected != schedule.next_due:
            raise ApiError('O vencimento foi atualizado. Atualize os alertas antes de emitir a OS.', 409)
        template = PreventiveChecklist.objects.filter(equipment_type=machine.equipment_type,
                                                      frequency=schedule.frequency).first()
        items = validate_items(
            schedule.checklist_items if schedule.checklist_items is not None else template.items if template else [])
        # The report uses this copy and does not go back to the registration for the machine's current name.
        snapshot = {'name': machine.name or machine.model or machine.equipment_type.name,
                    'type_name': machine.equipment_type.name, 'model': machine.model or '',
                    'asset_number': machine.asset_number or '', 'serial': machine.serial or '',
                    'manufacturer': machine.manufacturer or '', 'line_name': machine.line.name if machine.line else '',
                    'sector_name': machine.sector.name if machine.sector else ''}
        # The result position matches the activity position; PENDENTE is the initial state.
        order = PreventiveOrder.objects.create(schedule=schedule, expected_due=expected, planned_date=planned,
                                               planned_time=planned_time, recurrence_basis=basis,
                                               frequency=schedule.frequency,
                                               equipment_snapshot=snapshot, items=items,
                                               results=[{'status': 'PENDENTE', 'notes': ''} for _ in items],
                                               safety_instructions=SAFETY_INSTRUCTIONS, assigned_to=assigned,
                                               assigned_name=assigned.name, created_by=context.user)
    return Result(order_data(order, True), status=201)


def lock_order(pk, revision):
    """Dentro de uma transação, bloqueia máquina, agenda e OS nessa ordem. Exige OS aberta e revisão atual, evitando gravações simultâneas que apaguem o preenchimento de outra pessoa."""
    # The first read finds the links; subsequent reads lock the records.
    initial = get_object_or_404(PreventiveOrder, pk=pk)
    Equipment.objects.select_for_update().get(pk=initial.schedule.equipment_id)
    EquipmentPreventive.objects.select_for_update().get(pk=initial.schedule_id)
    order = PreventiveOrder.objects.select_for_update().select_related('schedule').get(pk=pk)
    if order.status != 'ABERTA':
        raise ApiError('Esta OS já foi concluída ou cancelada e não pode ser alterada.', 409)
    # revision identifies the version open on the screen. An old version cannot overwrite the new one.
    if isinstance(revision, bool) or not isinstance(revision, int) or revision != order.revision:
        raise ApiError('Esta OS foi atualizada. Feche e abra novamente para carregar a versão atual.', 409)
    return order


def execution_data(order, data):
    """Valida os resultados na ordem do roteiro, justificativas, peças, observações e data/horário realizados. Atualiza o objeto em memória; quem chamou decide se e quando gravar no banco."""
    results = data.get('results')
    if not isinstance(results, list) or len(results) != len(order.items):
        raise ApiError('Preencha os resultados de todos os itens da OS, na ordem apresentada.')
    normalized = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get('status'), str) or result[
            'status'] not in RESULTS:
            raise ApiError('Resultado de atividade inválido.')
        notes = result.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ApiError('Observação do item deve ter até 2000 caracteres.')
        if result['status'] in ('NA', 'NAO_REALIZADO') and not notes.strip():
            raise ApiError('Justifique os itens não realizados ou não aplicáveis.')
        normalized.append({'status': result['status'], 'notes': notes.strip()})
    notes = data.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 4000:
        raise ApiError('Observações gerais devem ter até 4000 caracteres.')
    parts = data.get('parts', [])
    if not isinstance(parts, list) or len(parts) > 50:
        raise ApiError('Informe até 50 peças substituídas.')
    normalized_parts = []
    for part in parts:
        if not isinstance(part, dict):
            raise ApiError('Peça inválida.')
        description, code, quantity = part.get('description'), part.get('partNumber', ''), part.get('quantity')
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 250 or not isinstance(code,
                                                                                                          str) or len(
            code) > 160:
            raise ApiError('Informe a descrição da peça (até 250 caracteres) e um código válido (até 160).')
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not 0 < quantity <= 1000000:
            raise ApiError('Quantidade da peça deve ser maior que zero e até 1.000.000.')
        normalized_parts.append({'description': description.strip(), 'partNumber': code.strip(), 'quantity': quantity})
    raw_date = data.get('performedDate')
    performed_date = parse_date(raw_date, 'Data realizada') if raw_date else None
    if performed_date and performed_date > timezone.localdate():
        raise ApiError('A execução não pode estar no futuro.')
    try:
        performed_time = time.fromisoformat(data['performedTime']) if data.get('performedTime') else None
        if performed_time and (performed_time.tzinfo or not performed_date):
            raise ValueError
    except (ValueError, TypeError):
        raise ApiError('Horário realizado inválido ou sem data realizada.')
    if performed_date and performed_time and performed_date == timezone.localdate() and performed_time > timezone.localtime().time():
        raise ApiError('O horário realizado não pode estar no futuro.')
    order.performed_time = performed_time
    # No save happens here: validation is shared by the draft and completion.
    order.results, order.parts, order.notes, order.performed_date = normalized, normalized_parts, notes.strip(), performed_date


@operation(['GET', 'PATCH'], roles=MAINTENANCE_ROLES)
def details(context, pk):
    """GET consulta uma OS completa. PATCH salva preenchimento parcial com controle de revisão, mantendo a OS aberta e sem atualizar o próximo vencimento."""
    if context.method == 'GET':
        return order_data(get_object_or_404(PreventiveOrder.objects.select_related('schedule'), pk=pk), True)
    data = request_body(context)
    with transaction.atomic():
        order = lock_order(pk, data.get('revision'))
        execution_data(order, data)
        order.revision += 1
        order.save(update_fields=['results', 'parts', 'notes', 'performed_date', 'performed_time', 'revision'])
    return order_data(order, True)


@operation(['POST'], roles=MAINTENANCE_ROLES)
def complete(context, pk):
    """POST exige atividades realizadas ou justificadas como não aplicáveis. Na mesma transação, grava o histórico, identifica o executor, conclui a OS e atualiza a agenda pela regra escolhida."""
    data = request_body(context)
    with transaction.atomic():
        order = lock_order(pk, data.get('revision'))
        execution_data(order, data)
        if not order.performed_date:
            raise ApiError('Informe a data realizada para concluir a OS.')
        if any(result['status'] in ('PENDENTE', 'NAO_REALIZADO') for result in order.results):
            raise ApiError(
                'Há atividades pendentes ou não realizadas. Resolva-as antes de concluir. Você pode salvar o preenchimento sem concluir.')
        if not any(result['status'] == 'REALIZADO' for result in order.results):
            raise ApiError('Registre ao menos uma atividade realizada antes de concluir.')
        schedule = order.schedule
        if not schedule.active or not schedule.equipment.active or schedule.next_due != order.expected_due:
            raise ApiError('A agenda desta OS foi alterada ou desativada. Cancele a OS e revise o planejamento.', 409)
        if schedule.last_performed and order.performed_date <= schedule.last_performed:
            raise ApiError('A execução deve ser posterior à última realização registrada.')
        # Execution forecast and reference due date are different: preserving the calendar uses the second.
        next_due = calculate_next_due(
            order.expected_due if order.recurrence_basis == 'PLANEJADA' else order.performed_date, order.frequency)
        # The executor comes from the authenticated session; the client cannot choose another user in JSON.
        PreventiveExecution.objects.create(schedule=schedule, order=order, performed_date=order.performed_date,
                                           previous_due=order.expected_due, next_due=next_due,
                                           technician=context.user, notes=order.notes)
        schedule.next_due, schedule.last_performed = next_due, order.performed_date
        schedule.save(update_fields=['next_due', 'last_performed'])
        order.status, order.finished_by, order.executor_name, order.finished_at = 'CONCLUIDA', context.user, context.user.name, timezone.now()
        order.revision += 1
        order.save(
            update_fields=['results', 'parts', 'notes', 'performed_date', 'performed_time', 'status', 'finished_by',
                           'executor_name', 'finished_at', 'revision'])
    return {**order_data(order, True), 'next_due': next_due}


@operation(['POST'], roles=MAINTENANCE_ROLES)
def cancel(context, pk):
    """POST exige justificativa e revisão atual para cancelar uma OS aberta. Preserva a OS para consulta e libera outra emissão sem registrar execução ou alterar o vencimento."""
    data = request_body(context)
    reason = data.get('reason')
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 2000:
        raise ApiError('Informe o motivo do cancelamento (5 a 2000 caracteres).')
    with transaction.atomic():
        order = lock_order(pk, data.get('revision'))
        order.status, order.cancellation_reason = 'CANCELADA', reason.strip()
        order.finished_by, order.executor_name, order.finished_at = context.user, context.user.name, timezone.now()
        order.revision += 1
        order.save(
            update_fields=['status', 'cancellation_reason', 'finished_by', 'executor_name', 'finished_at', 'revision'])
    return order_data(order, True)


@operation(['GET'], roles=MAINTENANCE_ROLES)
def document(context, pk):
    """GET monta a ficha HTML a partir dos dados preservados na OS, incluindo resultados já salvos e peças. Retorna um download; imprimir não salva preenchimento nem conclui a manutenção."""
    order = get_object_or_404(PreventiveOrder.objects.select_related('schedule'), pk=pk)
    engine = Engine(dirs=[str(Path(__file__).resolve().parent.parent / 'document_templates')])
    records = [{'description': record,
                'status': RESULTS[result['status']] if result['status'] != 'PENDENTE' else '',
                'notes': result['notes']}
               for record, result in zip(order.items, order.results)]
    document_html = engine.get_template('preventive_order.html').render(
        Context({'order': order, 'machine': order.equipment_snapshot,
                 'rows': records, 'frequency': order.get_frequency_display(), 'status': order.get_status_display()}))
    response = HttpResponse(document_html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{order.number}.html"'
    return response
