"""Datas e configuração da agenda de preventivas por equipamento."""
from .compatibility_value import adapt_call
import calendar
import re
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import EquipmentPreventiveCode, PERIODICIDADES_PREVENTIVA
from .preventive_planning import annual_window, reserve_next_shift

FREQUENCIESCode = dict(PERIODICIDADES_PREVENTIVA)


# Calcula a próxima data a partir da frequência da preventiva.
def next_due_value(performed_value, frequency_value):
    """Meses de calendário, limitados ao último dia válido do mês de destino."""
    if frequency_value == 'QUINZENAL':
        return performed_value + timedelta(days=15)
    months = {'MENSAL': 1, 'BIMESTRAL': 2, 'TRIMESTRAL': 3, 'SEMESTRAL': 6, 'ANUAL': 12}[frequency_value]
    # Um índice contínuo de meses permite atravessar dezembro sem uma regra especial por ano.
    month_index = performed_value.year * 12 + performed_value.month - 1 + months
    year_value, month_value = divmod(month_index, 12)
    month_value += 1
    # Se o dia não existir no destino, usa o último dia válido daquele mês.
    return date(year_value, month_value, min(performed_value.day, calendar.monthrange(year_value, month_value)[1]))


def parse_date_value(value_value, label_value):
    """Converte um texto AAAA-MM-DD em date após conferir formato, existência e intervalo do ano. Levanta ValidationError, transformado pela API em resposta 400."""
    if not isinstance(value_value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value_value):
        raise ValidationError(f'{label_value}: informe uma data válida no formato AAAA-MM-DD.')
    try:
        parsed = date.fromisoformat(value_value)
        # Reserva margem para calcular o próximo ciclo sem exceder o limite de datas.
        if not 1900 <= parsed.year <= 9997:
            raise ValueError
        return parsed
    except ValueError:
        raise ValidationError(f'{label_value}: data inválida.')


def validate_schedules_value(value_value):
    """Valida a lista enviada pelo cadastro: até seis frequências válidas, sem duplicidade e com data opcional. Retorna pares frequência/data; ainda não grava nada."""
    if not isinstance(value_value, list) or len(value_value) > len(FREQUENCIESCode):
        raise ValidationError('Informe uma lista com até seis tipos de preventiva.')
    result_value, seen = [], set()
    for item_value in value_value:
        if not isinstance(item_value, dict):
            raise ValidationError('Configuração de preventiva inválida.')
        frequency_value = item_value.get('frequency')
        if not isinstance(frequency_value, str) or frequency_value not in FREQUENCIESCode or frequency_value in seen:
            raise ValidationError('Periodicidade inválida ou duplicada.')
        seen.add(frequency_value)
        due = item_value.get('nextDue')
        result_value.append((frequency_value, parse_date_value(due, 'Próximo vencimento') if due not in (None, '') else None))
    return result_value


def sync_schedules_value(equipment_value, selections_value):
    """Chamado com bloqueio da máquina e dentro da transação de cadastro."""
    selected = [frequency_value for frequency_value, _ in selections_value]
    for schedule_value in equipment_value.preventive_schedules.filter(orders__status='ABERTA'):
        submitted = dict(selections_value)
        if schedule_value.frequency not in submitted or (submitted[schedule_value.frequency] is not None and submitted[schedule_value.frequency] != schedule_value.next_due):
            raise ValidationError('Conclua ou cancele a OS preventiva aberta antes de alterar seu vencimento ou desmarcar a periodicidade.')
    # Desmarcar é desativar. Apagar a agenda destruiria a referência dos históricos e das OS.
    equipment_value.preventive_schedules.exclude(frequency__in=selected).update(active=False)
    today = timezone.localdate()
    for frequency_value, due in selections_value:
        if equipment_value.preventive_schedules.filter(frequency=frequency_value, orders__status='ABERTA').exists():
            continue
        if frequency_value == 'ANUAL':
            due = annual_window(due)[0] if due else None
            default_due = annual_window(today)[0]
        else:
            default_due = next_due_value(today, frequency_value)
        schedule_value, created_value = EquipmentPreventiveCode.objects.get_or_create(
            equipment=equipment_value, frequency=frequency_value,
            defaults={'next_due': due or default_due})
        new_date = due or schedule_value.next_due
        if created_value or not schedule_value.active or new_date != schedule_value.next_due:
            schedule_value.next_due = new_date
            schedule_value.planned_time = None
            if new_date >= today:
                schedule_value.next_due, schedule_value.planned_time = reserve_next_shift(schedule_value, new_date)
        schedule_value.active = True
        schedule_value.save(update_fields=['active', 'next_due', 'planned_time'])


def schedule_data_value(schedule_value):
    """Retorna ID, frequência, próximo vencimento e última realização da agenda em um dicionário que o Django consegue converter para JSON."""
    return {'id': schedule_value.pk, 'frequency': schedule_value.frequency,
            'next_due': schedule_value.next_due, 'planned_time': schedule_value.planned_time,
            'last_performed': schedule_value.last_performed}

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
next_due = adapt_call(next_due_value, {'performed': 'performed_value', 'frequency': 'frequency_value'})
parse_date = adapt_call(parse_date_value, {'value': 'value_value', 'label': 'label_value'})
validate_schedules = adapt_call(validate_schedules_value, {'value': 'value_value'})
sync_schedules = adapt_call(sync_schedules_value, {'equipment': 'equipment_value', 'selections': 'selections_value'})
schedule_data = adapt_call(schedule_data_value, {'schedule': 'schedule_value'})
FREQUENCIES = FREQUENCIESCode
