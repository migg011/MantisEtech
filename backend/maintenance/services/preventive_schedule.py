"""Datas e configuração da agenda preventiva dos equipamentos."""
import calendar
import re
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import EquipmentPreventive, PREVENTIVE_FREQUENCIES

PERIODICITIES = dict(PREVENTIVE_FREQUENCIES)


def calculate_next_due(performed_date, frequency):
    """Meses do calendário, limitados ao último dia válido do mês de destino."""
    if frequency == 'QUINZENAL':
        return performed_date + timedelta(days=15)
    months = {'MENSAL': 1, 'BIMESTRAL': 2, 'TRIMESTRAL': 3, 'SEMESTRAL': 6, 'ANUAL': 12}[frequency]
    # A continuous month index crosses December without a special rule per year.
    month_index = performed_date.year * 12 + performed_date.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    # If the day does not exist at the destination, use the last valid day of that month.
    return date(year, month, min(performed_date.day, calendar.monthrange(year, month)[1]))


def parse_date(value, label):
    """Converte uma data AAAA-MM-DD após validar formato, existência e intervalo do ano. Lança ValidationError, convertido pela API em resposta 400."""
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValidationError(f'{label}: informe uma data válida no formato AAAA-MM-DD.')
    try:
        converted_date = date.fromisoformat(value)
        # Reserve margin to calculate the next cycle without exceeding the date limit.
        if not 1900 <= converted_date.year <= 9997:
            raise ValueError
        return converted_date
    except ValueError:
        raise ValidationError(f'{label}: data inválida.')


def validate_schedules(value):
    """Valida a lista do cadastro: até seis periodicidades válidas, sem duplicatas e com data opcional. Retorna pares de periodicidade e data, sem gravar."""
    if not isinstance(value, list) or len(value) > len(PERIODICITIES):
        raise ValidationError('Informe uma lista com até seis tipos de preventiva.')
    result, found = [], set()
    for record in value:
        if not isinstance(record, dict):
            raise ValidationError('Configuração de preventiva inválida.')
        frequency = record.get('frequency')
        if not isinstance(frequency, str) or frequency not in PERIODICITIES or frequency in found:
            raise ValidationError('Periodicidade inválida ou duplicada.')
        found.add(frequency)
        next_due = record.get('nextDue')
        result.append((frequency,
                       parse_date(next_due, 'Próximo vencimento') if next_due not in (None, '') else None))
    return result


def sync_schedules(equipment, selections):
    """Executado com a máquina bloqueada e dentro da transação do cadastro."""
    selected = [frequency for frequency, _ in selections]
    for schedule in equipment.preventive_schedules.filter(orders__status='ABERTA'):
        submitted = dict(selections)
        if schedule.frequency not in submitted or (
                submitted[schedule.frequency] is not None and submitted[schedule.frequency] != schedule.next_due):
            raise ValidationError(
                'Conclua ou cancele a OS preventiva aberta antes de alterar seu vencimento ou desmarcar a periodicidade.')
    # Unchecking means deactivating. Deleting the schedule would destroy the history and order references.
    equipment.preventive_schedules.exclude(frequency__in=selected).update(active=False)
    for frequency, next_due in selections:
        schedule, created = EquipmentPreventive.objects.get_or_create(
            equipment=equipment, frequency=frequency,
            defaults={'next_due': next_due or calculate_next_due(timezone.localdate(), frequency)})
        if not created:
            schedule.active = True
            if next_due is not None:
                schedule.next_due = next_due
            schedule.save(update_fields=['active', 'next_due'])


def schedule_data(schedule):
    """Retorna identificação, periodicidade, próxima data e última execução em um dicionário serializável pelo Django."""
    return {'id': schedule.pk, 'frequency': schedule.frequency,
            'next_due': schedule.next_due, 'last_performed': schedule.last_performed}
