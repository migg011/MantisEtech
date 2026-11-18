"""Emissão, preenchimento e impressão de OS preventivas com histórico imutável."""
from .compatibility_value import adapt_call
from datetime import date, time
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.template import Context, Engine
from django.utils import timezone

from .api import APIErrorCode, STAFFCode, body_value, endpoint_value, positive_id_value, sector_scope
from .models import EquipmentCode, EquipmentPreventiveCode, PreventiveChecklistCode, PreventiveOrderCode, PreventiveExecutionCode, UserCode
from .preventive_views import validate_items_value
from .schedule_rules import next_due_value, parse_date_value
from .preventive_planning import SHIFTS, annual_window, available_shifts, planning_lock, reserve_next_shift, shift_slot

SAFETYCode = (
    # Este texto é copiado para a OS: atualizar o padrão não altera fichas antigas.
    'Antes da atividade, desligar e isolar o equipamento conforme o procedimento de segurança aplicável. / '
    'Before servicing, shut down and isolate the equipment according to the applicable safety procedure.\n'
    'Utilizar os EPIs e observar os riscos descritos no procedimento do equipamento. / Use the required PPE and observe equipment-specific risks.\n'
    'Manter atenção às partes móveis e zonas de prensamento. / Stay clear of moving parts and pinch points.\n'
    'Respeitar a sinalização e reinstalar todas as proteções antes da liberação. / Follow safety signage and reinstall all guards before release.\n'
    'Executar somente atividades para as quais esteja autorizado. / Perform only authorized activities.'
)
RESULTSCode = {'PENDENTE': 'Pendente', 'REALIZADO': 'Realizado', 'NAO_REALIZADO': 'Não realizado', 'NA': 'Não aplicável'}


def order_data_value(order_value, detail_value=False):
    """Converte uma OS em dados JSON para a lista. Com detail=True, inclui o roteiro, resultados, peças, orientações e observações; não modifica o registro."""
    data_value = {'id': order_value.pk, 'number': order_value.number, 'schedule_id': order_value.schedule_id,
            'equipment_id': order_value.schedule.equipment_id, 'equipment_name': order_value.equipment_snapshot.get('name', ''),
            'frequency': order_value.frequency, 'status': order_value.status, 'planned_date': order_value.planned_date,
            'planned_time': order_value.planned_time, 'performed_date': order_value.performed_date, 'performed_time': order_value.performed_time, 'expected_due': order_value.expected_due,
            'recurrence_basis': order_value.recurrence_basis, 'assigned_to_id': order_value.assigned_to_id,
            'assigned_name': order_value.assigned_name, 'executor_name': order_value.executor_name,
            'revision': order_value.revision, 'created_at': order_value.created_at}
    if detail_value_value:
        data_value.update(equipment_snapshot=order_value.equipment_snapshot, items=order_value.items, results=order_value.results,
                    safety_instructions=order_value.safety_instructions, parts=order_value.parts, notes=order_value.notes,
                    cancellation_reason=order_value.cancellation_reason)
    return data_value


@endpoint_value(['GET'], roles_value=STAFFCode)
def technicians_value(request_value):
    """GET retorna somente ID e nome das contas técnicas/administrativas ativas para selecionar o responsável previsto, sem expor senhas ou outros dados da conta."""
    users = UserCode.objects.filter(active=True, role__in=STAFFCode)
    if not request_value.user.is_admin:
        users = sector_scope(users, request_value.user)
    return list(users.values('id', 'name', 'role', 'sector_id'))


def validate_annual_window(schedule, day):
    if schedule.frequency == 'ANUAL':
        start, end = annual_window(schedule.next_due)
        if not start <= day <= end:
            raise APIErrorCode('A preventiva anual deve ser programada entre 20/12 e 03/01 da janela do vencimento.')


@endpoint_value(['GET'], roles_value=STAFFCode)
def shifts_value(request_value):
    schedule = get_object_or_404(
        sector_scope(EquipmentPreventiveCode.objects.select_related('equipment__equipment_type'),
                     request_value.user, 'equipment__sector'),
        pk=positive_id_value(request_value.GET.get('scheduleId')),
        active=True, equipment__active=True,
    )
    day = parse_date_value(request_value.GET.get('date'), 'Data prevista')
    validate_annual_window(schedule, day)
    available = available_shifts(day, schedule)
    return [{'time': start.strftime('%H:%M'), 'label': label, 'available': start in available}
            for start, label in SHIFTS]


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def orders_value(request_value):
    """GET lista todas as OS abertas e as últimas 100 encerradas. POST valida agenda, previsão e responsável, impede duplicidade e salva uma cópia do roteiro e da identificação da máquina."""
    if request_value.method == 'GET':
        rows_value = sector_scope(PreventiveOrderCode.objects.select_related('schedule'),
                                  request_value.user, 'schedule__equipment__sector')
        if request_value.GET.get('equipmentId'):
            rows_value = rows_value.filter(schedule__equipment_id=positive_id_value(request_value.GET['equipmentId']))
        # Todas as abertas precisam continuar acessíveis, independentemente do tamanho do histórico.
        return [order_data_value(order_value) for order_value in rows_value.filter(status='ABERTA')] + [order_data_value(order_value) for order_value in rows_value.exclude(status='ABERTA')[:100]]
    data_value = body_value(request_value)
    schedule_id = positive_id_value(data_value.get('scheduleId'))
    expected_value = parse_date_value(data_value.get('expectedDueDate'), 'Vencimento apresentado')
    planned = parse_date_value(data_value.get('plannedDate'), 'Data prevista')
    basis = data_value.get('recurrenceBasis', 'PLANEJADA')
    if basis not in ('PLANEJADA', 'EXECUCAO'):
        raise APIErrorCode('Selecione a regra do próximo vencimento.')
    raw_time = data_value.get('plannedTime')
    try:
        planned_time = time.fromisoformat(raw_time) if raw_time else None
        if planned_time and planned_time.tzinfo:
            raise ValueError
    except (TypeError, ValueError):
        raise APIErrorCode('Horário previsto inválido.')
    assigned = get_object_or_404(UserCode, pk=positive_id_value(data_value.get('assignedToId')), active=True, role__in=STAFFCode)
    # A emissão confirma roteiro, identificação e vínculo da agenda na mesma transação.
    with transaction.atomic():
        planning_lock()
        initial = get_object_or_404(sector_scope(EquipmentPreventiveCode.objects.all(), request_value.user,
                                                 'equipment__sector'), pk=schedule_id)
        machine = get_object_or_404(EquipmentCode.objects.select_for_update(of=('self',)).select_related('equipment_type', 'sector', 'line'), pk=initial.equipment_id, active=True)
        if not request_value.user.is_admin and machine.sector_id != request_value.user.sector_id:
            raise Http404
        if not assigned.is_admin and (not assigned.sector_id or assigned.sector_id != machine.sector_id):
            raise APIErrorCode('Selecione um técnico do setor do equipamento.')
        schedule_value = get_object_or_404(EquipmentPreventiveCode.objects.select_for_update(), pk=schedule_id, active=True)
        existing = PreventiveOrderCode.objects.filter(schedule=schedule_value, status='ABERTA').first()
        if existing:
            raise APIErrorCode(f'Já existe a OS {existing.number} aberta para esta preventiva.', 409, {'orderId': existing.pk})
        if expected_value != schedule_value.next_due:
            raise APIErrorCode('O vencimento foi atualizado. Atualize os alertas antes de emitir a OS.', 409)
        validate_annual_window(schedule_value, planned)
        day, shift = shift_slot(planned, planned_time) if planned_time else (planned, None)
        available = available_shifts(planned if schedule_value.frequency == 'ANUAL' else day, schedule_value)
        if not available or (shift is not None and shift not in available):
            raise APIErrorCode('Este turno já está ocupado. Selecione outro turno ou outra data.', 409)
        if planned_time is None:
            planned_time = available[0]
        template = PreventiveChecklistCode.objects.filter(equipment_type=machine.equipment_type, frequency=schedule_value.frequency).first()
        items_value = validate_items_value(schedule_value.checklist_items if schedule_value.checklist_items is not None else template.items if template else [])
        # O relatório usa esta cópia, e não volta ao cadastro para buscar o nome atual da máquina.
        snapshot = {'name': machine.name or machine.model or machine.equipment_type.name,
                    'type_name': machine.equipment_type.name, 'model': machine.model or '',
                    'asset_number': machine.asset_number or '', 'serial': machine.serial or '',
                    'manufacturer': machine.manufacturer or '', 'line_name': machine.line.name if machine.line else '',
                    'sector_name': machine.sector.name if machine.sector else ''}
        # A posição do resultado corresponde à posição da atividade; PENDENTE é o estado inicial.
        order_value = PreventiveOrderCode.objects.create(schedule=schedule_value, expected_due=expected_value, planned_date=planned,
            planned_time=planned_time, recurrence_basis=basis, frequency=schedule_value.frequency,
            equipment_snapshot=snapshot, items=items_value, results=[{'status': 'PENDENTE', 'notes': ''} for _ in items_value],
            safety_instructions=SAFETYCode, assigned_to=assigned, assigned_name=assigned.name, created_by=request_value.user)
        if schedule_value.planned_time is not None:
            schedule_value.planned_time = None
            schedule_value.save(update_fields=['planned_time'])
    return JsonResponse(order_data_value(order_value, True), status=201)


def lock_order_value(pk, revision_value, user):
    """Dentro de uma transação, bloqueia máquina, agenda e OS nessa ordem. Exige OS aberta e revisão atual, evitando gravações simultâneas que apaguem o preenchimento de outra pessoa."""
    # A primeira leitura encontra os vínculos; as leituras seguintes bloqueiam os registros.
    initial = get_object_or_404(PreventiveOrderCode, pk=pk)
    get_object_or_404(sector_scope(EquipmentCode.objects.select_for_update(of=('self',)), user),
                      pk=initial.schedule.equipment_id)
    EquipmentPreventiveCode.objects.select_for_update().get(pk=initial.schedule_id)
    order_value = PreventiveOrderCode.objects.select_for_update().select_related('schedule').get(pk=pk)
    if order_value.status != 'ABERTA':
        raise APIErrorCode('Esta OS já foi concluída ou cancelada e não pode ser alterada.', 409)
    # revision identifica a versão aberta na tela. Uma versão antiga não pode sobrescrever a nova.
    if isinstance(revision_value, bool) or not isinstance(revision_value, int) or revision_value != order_value.revision:
        raise APIErrorCode('Esta OS foi atualizada. Feche e abra novamente para carregar a versão atual.', 409)
    return order_value


def execution_data_value(order_value, data_value):
    """Valida os resultados na ordem do roteiro, justificativas, peças, observações e data/horário realizados. Atualiza o objeto em memória; quem chamou decide se e quando gravar no banco."""
    results = data_value.get('results')
    if not isinstance(results, list) or len(results) != len(order_value.items):
        raise APIErrorCode('Preencha os resultados de todos os itens da OS, na ordem apresentada.')
    normalized = []
    for result_value in results:
        if not isinstance(result_value, dict) or not isinstance(result_value.get('status'), str) or result_value['status'] not in RESULTSCode:
            raise APIErrorCode('Resultado de atividade inválido.')
        notes_value = result_value.get('notes', '')
        if not isinstance(notes_value, str) or len(notes_value) > 2000:
            raise APIErrorCode('Observação do item deve ter até 2000 caracteres.')
        if result_value['status'] in ('NA', 'NAO_REALIZADO') and not notes_value.strip():
            raise APIErrorCode('Justifique os itens não realizados ou não aplicáveis.')
        normalized.append({'status': result_value['status'], 'notes': notes_value.strip()})
    notes_value = data_value.get('notes', '')
    if not isinstance(notes_value, str) or len(notes_value) > 4000:
        raise APIErrorCode('Observações gerais devem ter até 4000 caracteres.')
    parts_value = data_value.get('parts', [])
    if not isinstance(parts_value, list) or len(parts_value) > 50:
        raise APIErrorCode('Informe até 50 peças substituídas.')
    normalized_parts = []
    for part_value in parts_value:
        if not isinstance(part_value, dict):
            raise APIErrorCode('Peça inválida.')
        description, code, quantity = part_value.get('description'), part_value.get('partNumber', ''), part_value.get('quantity')
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 250 or not isinstance(code, str) or len(code) > 160:
            raise APIErrorCode('Informe a descrição da peça (até 250 caracteres) e um código válido (até 160).')
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not 0 < quantity <= 1000000:
            raise APIErrorCode('Quantidade da peça deve ser maior que zero e até 1.000.000.')
        normalized_parts.append({'description': description.strip(), 'partNumber': code.strip(), 'quantity': quantity})
    raw_date = data_value.get('performedDate')
    performed_value = parse_date_value(raw_date, 'Data realizada') if raw_date else None
    if performed_value and performed_value > timezone.localdate():
        raise APIErrorCode('A execução não pode estar no futuro.')
    try:
        performed_time = time.fromisoformat(data_value['performedTime']) if data_value.get('performedTime') else None
        if performed_time and (performed_time.tzinfo or not performed_value):
            raise ValueError
    except (ValueError, TypeError):
        raise APIErrorCode('Horário realizado inválido ou sem data realizada.')
    if performed_value and performed_time and performed_value == timezone.localdate() and performed_time > timezone.localtime().time():
        raise APIErrorCode('O horário realizado não pode estar no futuro.')
    order_value.performed_time = performed_time
    # Nenhum save acontece aqui: a validação é compartilhada pelo rascunho e pela conclusão.
    order_value.results, order_value.parts, order_value.notes, order_value.performed_date = normalized, normalized_parts, notes_value.strip(), performed_value


@endpoint_value(['GET', 'PATCH'], roles_value=STAFFCode)
def detail_value_value(request_value, pk):
    """GET consulta uma OS completa. PATCH salva preenchimento parcial com controle de revisão, mantendo a OS aberta e sem atualizar o próximo vencimento."""
    if request_value.method == 'GET':
        return order_data_value(get_object_or_404(sector_scope(PreventiveOrderCode.objects.select_related('schedule'),
                                                   request_value.user, 'schedule__equipment__sector'), pk=pk), True)
    data_value = body_value(request_value)
    with transaction.atomic():
        order_value = lock_order_value(pk, data_value.get('revision'), request_value.user)
        execution_data_value(order_value, data_value)
        order_value.revision += 1
        order_value.save(update_fields=['results', 'parts', 'notes', 'performed_date', 'performed_time', 'revision'])
    return order_data_value(order_value, True)


@endpoint_value(['POST'], roles_value=STAFFCode)
def complete_value(request_value, pk):
    """POST exige atividades realizadas ou justificadas como não aplicáveis. Na mesma transação, grava o histórico, identifica o executor, conclui a OS e atualiza a agenda pela regra escolhida."""
    data_value = body_value(request_value)
    with transaction.atomic():
        planning_lock()
        order_value = lock_order_value(pk, data_value.get('revision'), request_value.user)
        execution_data_value(order_value, data_value)
        if not order_value.performed_date:
            raise APIErrorCode('Informe a data realizada para concluir a OS.')
        if any(result_value['status'] in ('PENDENTE', 'NAO_REALIZADO') for result_value in order_value.results):
            raise APIErrorCode('Há atividades pendentes ou não realizadas. Resolva-as antes de concluir. Você pode salvar o preenchimento sem concluir.')
        if not any(result_value['status'] == 'REALIZADO' for result_value in order_value.results):
            raise APIErrorCode('Registre ao menos uma atividade realizada antes de concluir.')
        schedule_value = order_value.schedule
        if not schedule_value.active or not schedule_value.equipment.active or schedule_value.next_due != order_value.expected_due:
            raise APIErrorCode('A agenda desta OS foi alterada ou desativada. Cancele a OS e revise o planejamento.', 409)
        if schedule_value.last_performed and order_value.performed_date <= schedule_value.last_performed:
            raise APIErrorCode('A execução deve ser posterior à última realização registrada.')
        if order_value.frequency == 'ANUAL':
            start, _ = annual_window(order_value.expected_due)
            due, next_time = date(start.year + 1, 12, 20), None
        else:
            reference = order_value.expected_due if order_value.recurrence_basis == 'PLANEJADA' else order_value.performed_date
            candidate = next_due_value(reference, order_value.frequency)
            due, next_time = reserve_next_shift(schedule_value, max(candidate, timezone.localdate()))
        # O executor vem da sessão autenticada; o cliente não escolhe outro usuário no JSON.
        PreventiveExecutionCode.objects.create(schedule=schedule_value, order=order_value, performed_date=order_value.performed_date,
            previous_due=order_value.expected_due, next_due=due, technician=request_value.user, notes=order_value.notes)
        schedule_value.next_due, schedule_value.last_performed = due, order_value.performed_date
        schedule_value.planned_time = next_time
        schedule_value.save(update_fields=['next_due', 'last_performed', 'planned_time'])
        order_value.status, order_value.finished_by, order_value.executor_name, order_value.finished_at = 'CONCLUIDA', request_value.user, request_value.user.name, timezone.now()
        order_value.revision += 1
        order_value.save(update_fields=['results', 'parts', 'notes', 'performed_date', 'performed_time', 'status', 'finished_by', 'executor_name', 'finished_at', 'revision'])
        if order_value.frequency == 'ANUAL':
            reset_after_annual_cycle(order_value)
    return {**order_data_value(order_value, True), 'next_due': due}


def reset_after_annual_cycle(order):
    """Reprograma as agendas do cadastro quando a última anual da janela for concluída."""
    start, end = annual_window(order.expected_due)
    annuals = EquipmentPreventiveCode.objects.filter(active=True, equipment__active=True, frequency='ANUAL')
    # As agendas anuais ainda não avançadas indicam que esta janela continua aberta.
    if annuals.filter(next_due__lte=end).exists():
        return
    annual_orders = PreventiveOrderCode.objects.filter(
        schedule__active=True, schedule__equipment__active=True, frequency='ANUAL',
        status='CONCLUIDA', expected_due__range=(start, end),
    ).order_by('performed_date', 'pk')
    actual_dates = dict(annual_orders.values_list('schedule__equipment_id', 'performed_date'))
    latest = max(actual_dates.values(), default=order.performed_date)
    schedules = EquipmentPreventiveCode.objects.filter(active=True, equipment__active=True).exclude(
        frequency='ANUAL',
    ).exclude(orders__status='ABERTA').select_related('equipment__equipment_type').order_by('next_due', 'pk')
    # Libera todas as reservas que serão recalculadas antes de distribuir os novos turnos.
    schedules.update(planned_time=None)
    today = timezone.localdate()
    for schedule in schedules:
        base = actual_dates.get(schedule.equipment_id, latest)
        candidate = next_due_value(base, schedule.frequency)
        schedule.next_due, schedule.planned_time = reserve_next_shift(schedule, max(candidate, today))
        schedule.save(update_fields=['next_due', 'planned_time'])


@endpoint_value(['POST'], roles_value=STAFFCode)
def cancel_value(request_value, pk):
    """POST exige justificativa e revisão atual para cancelar uma OS aberta. Preserva a OS para consulta e libera outra emissão sem registrar execução ou alterar o vencimento."""
    data_value = body_value(request_value)
    reason = data_value.get('reason')
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 2000:
        raise APIErrorCode('Informe o motivo do cancelamento (5 a 2000 caracteres).')
    with transaction.atomic():
        planning_lock()
        order_value = lock_order_value(pk, data_value.get('revision'), request_value.user)
        order_value.status, order_value.cancellation_reason = 'CANCELADA', reason.strip()
        order_value.finished_by, order_value.executor_name, order_value.finished_at = request_value.user, request_value.user.name, timezone.now()
        order_value.revision += 1
        order_value.save(update_fields=['status', 'cancellation_reason', 'finished_by', 'executor_name', 'finished_at', 'revision'])
    return order_data_value(order_value, True)


@endpoint_value(['GET'], roles_value=STAFFCode)
def document_value(request_value, pk):
    """GET monta a ficha HTML a partir dos dados preservados na OS, incluindo resultados já salvos e peças. Retorna um download; imprimir não salva preenchimento nem conclui a manutenção."""
    order_value = get_object_or_404(sector_scope(PreventiveOrderCode.objects.select_related('schedule'),
                                                   request_value.user, 'schedule__equipment__sector'), pk=pk)
    engine = Engine(dirs=[str(Path(__file__).resolve().parent / 'document_templates')])
    rows_value = [{'description': item_value, 'status': RESULTSCode[result_value['status']] if result_value['status'] != 'PENDENTE' else '', 'notes': result_value['notes']}
            for item_value, result_value in zip(order_value.items, order_value.results)]
    html_value = engine.get_template('preventive_order.html').render(Context({'order': order_value, 'machine': order_value.equipment_snapshot,
        'rows': rows_value, 'frequency': order_value.get_frequency_display(), 'status': order_value.get_status_display()}))
    response_value = HttpResponse(html_value, content_type='text/html; charset=utf-8')
    response_value['Content-Disposition'] = f'attachment; filename="{order_value.number}.html"'
    return response_value

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
order_data = adapt_call(order_data_value, {'detail': 'detail_value', 'order': 'order_value'})
technicians = adapt_call(technicians_value, {'request': 'request_value'})
orders = adapt_call(orders_value, {'request': 'request_value'})
lock_order = adapt_call(lock_order_value, {'revision': 'revision_value'})
execution_data = adapt_call(execution_data_value, {'data': 'data_value', 'order': 'order_value'})
detail = adapt_call(detail_value_value, {'request': 'request_value'})
complete = adapt_call(complete_value, {'request': 'request_value'})
cancel = adapt_call(cancel_value, {'request': 'request_value'})
document = adapt_call(document_value, {'request': 'request_value'})
SAFETY = SAFETYCode
RESULTS = RESULTSCode
