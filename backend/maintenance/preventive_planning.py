"""Reserva turnos para OS emitidas e próximas preventivas já programadas."""
from datetime import date, time, timedelta
import re

from django.db import connection
from django.utils import timezone

from .models import EquipmentPreventive, PreventiveOrder


SHIFTS = (
    (time(6), '1º turno · 06:00 às 14:00'),
    (time(14), '2º turno · 14:00 às 22:00'),
    (time(22), '3º turno · 22:00 às 06:00 do dia seguinte'),
)


def planning_lock():
    """Serializa reservas no PostgreSQL até a transação terminar."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [113766001, 1])


def annual_window(day):
    """Devolve os limites da janela anual associada à data."""
    year = day.year - (day.month == 1 and day.day <= 3)
    return date(year, 12, 20), date(year + 1, 1, 3)


def is_shift_exempt(frequency, equipment_type_name, day):
    start, end = annual_window(day)
    kind = ' '.join(re.split(r'[\s_-]+', equipment_type_name.upper()))
    return 'CONVEYOR' in kind.split() or 'MAGAZINE LOADER' in kind or (
        frequency == 'ANUAL' and start <= day <= end
    )


def shift_slot(day, scheduled_time):
    """O terceiro turno continua na madrugada do dia seguinte."""
    if scheduled_time < SHIFTS[0][0]:
        return day - timedelta(days=1), SHIFTS[2][0]
    return day, next(start for start, _ in reversed(SHIFTS) if scheduled_time >= start)


def occupied_shifts(day, schedule):
    """Inclui reservas automáticas e OS não canceladas, sem contar a própria reserva."""
    occupied = set()
    tomorrow = day + timedelta(days=1)
    orders = PreventiveOrder.objects.filter(planned_date__range=(day, tomorrow)).exclude(status='CANCELADA')
    machine = schedule.equipment
    scope = {'line_id': machine.line_id, 'sector_id': machine.sector_id}
    order_scope = {f'schedule__equipment__{key}': value for key, value in scope.items()}
    orders = orders.filter(**order_scope)
    for planned_day, planned_time, frequency, type_name in orders.values_list(
        'planned_date', 'planned_time', 'frequency', 'schedule__equipment__equipment_type__name',
    ):
        if is_shift_exempt(frequency, type_name, planned_day):
            continue
        if planned_time is None:
            if planned_day == day:
                occupied.update(start for start, _ in SHIFTS)
            continue
        shift_day, start = shift_slot(planned_day, planned_time)
        if shift_day == day:
            occupied.add(start)

    reservations = EquipmentPreventive.objects.filter(
        active=True, equipment__active=True, next_due=day, planned_time__isnull=False,
    ).exclude(pk=schedule.pk).filter(**{f'equipment__{key}': value for key, value in scope.items()})
    for planned_time, frequency, type_name in reservations.values_list(
        'planned_time', 'frequency', 'equipment__equipment_type__name',
    ):
        if not is_shift_exempt(frequency, type_name, day):
            occupied.add(shift_slot(day, planned_time)[1])
    return occupied


def available_shifts(day, schedule):
    if is_shift_exempt(schedule.frequency, schedule.equipment.equipment_type.name, day):
        return [start for start, _ in SHIFTS]
    blocked = occupied_shifts(day, schedule)
    return [start for start, _ in SHIFTS if start not in blocked]


def reserve_next_shift(schedule, day):
    """Encontra o primeiro turno livre a partir da data calculada."""
    if schedule.frequency == 'ANUAL':
        return day, None
    now = timezone.localtime()
    while True:
        for start in available_shifts(day, schedule):
            if day != now.date() or start >= now.time():
                return day, start
        day += timedelta(days=1)
