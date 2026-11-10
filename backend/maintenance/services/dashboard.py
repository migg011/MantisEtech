"""Indicadores do painel calculados no banco, sem o limite de 200 OS da listagem."""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from ..models import PreventiveOrder


def dashboard_summary(equipment, orders, days=30):
    now = timezone.now()
    today = timezone.localdate(now)
    first_day = today - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(first_day, time.min))
    ids = equipment.values('pk')
    corrective = orders.filter(equipment_id__in=ids)
    preventive = PreventiveOrder.objects.filter(schedule__equipment_id__in=ids)
    corrective_period = corrective.filter(created_at__gte=start, created_at__lte=now)
    preventive_period = preventive.filter(created_at__gte=start, created_at__lte=now)
    open_corrective = corrective.exclude(status='CONCLUIDA')
    total = equipment.count()
    failures = open_corrective.values('equipment_id').distinct().count()
    open_orders = open_corrective.count() + preventive.filter(status='ABERTA').count()
    # Instant availability, not historical production availability.
    availability = round(100 * (total - failures) / total, 1) if total else None
    repairs = []
    for repair_start, end in corrective.filter(status='CONCLUIDA', finished_at__gte=start, finished_at__lte=now,
                                               started_at__isnull=False).values_list('started_at', 'finished_at'):
        if end and end >= repair_start: repairs.append((end - repair_start).total_seconds() / 3600)
    series = {first_day + timedelta(days=i): {'opened': 0, 'closed': 0} for i in range(days)}

    def count_by_day(queryset, field, key):
        groups = queryset.annotate(day=TruncDate(field, tzinfo=timezone.get_current_timezone())).values(
            'day').annotate(total=Count('pk'))
        for group in groups:
            if group['day'] in series: series[group['day']][key] += group['total']

    count_by_day(corrective_period, 'created_at', 'opened')
    count_by_day(preventive_period, 'created_at', 'opened')
    count_by_day(corrective.filter(status='CONCLUIDA', finished_at__gte=start, finished_at__lte=now),
                 'finished_at', 'closed')
    count_by_day(preventive.filter(status='CONCLUIDA', finished_at__gte=start, finished_at__lte=now),
                 'finished_at', 'closed')
    latest = []
    for order in corrective_period.select_related('equipment', 'equipment__equipment_type').order_by('-created_at',
                                                                                                     '-pk')[:6]:
        machine = order.equipment
        latest.append({'id': order.pk, 'number': f'OS-{order.pk:06d}',
                       'equipment': machine.asset_number or machine.model or machine.equipment_type.name,
                       'kind': 'CORRETIVA', 'status': order.status, 'created_at': order.created_at})
    for order in preventive_period.select_related('schedule__equipment',
                                                  'schedule__equipment__equipment_type').order_by('-created_at',
                                                                                                  '-pk')[:6]:
        machine = order.schedule.equipment
        latest.append(
            {'id': order.pk, 'number': order.number,
             'equipment': machine.asset_number or machine.model or machine.equipment_type.name,
             'kind': 'PREVENTIVA', 'status': order.status, 'created_at': order.created_at})
    latest.sort(key=lambda row: (row['created_at'], row['number']), reverse=True)
    return {'generated_at': now, 'days': days, 'start_date': first_day, 'end_date': today,
            'summary': {'equipment_total': total, 'equipment_active': total - failures, 'equipment_fault': failures,
                        'open_orders': open_orders, 'availability_pct': availability,
                        'mttr_hours': round(sum(repairs) / len(repairs), 2) if repairs else None,
                        'mttr_sample': len(repairs), 'mtbf_hours': None},
            'distribution': {'corrective': corrective_period.count(), 'preventive': preventive_period.count(),
                             'predictive': None},
            'evolution': [{'date': day, **values} for day, values in series.items()],
            'latest_orders': latest[:6]}
