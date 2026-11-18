"""Calcula os indicadores que aparecem no painel."""
from datetime import datetime, time, timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from .models import PreventiveOrderCode

def dashboard_summary(equipment, orders, days=30):
    """Resume as ordens e os equipamentos no período escolhido."""
    now=timezone.now()
    today=timezone.localdate(now)
    first_day=today-timedelta(days=days-1)
    period_start=timezone.make_aware(datetime.combine(first_day,time.min))
    ids=equipment.values('pk')
    corrective_orders=orders.filter(equipment_id__in=ids)
    preventive_orders=PreventiveOrderCode.objects.filter(schedule__equipment_id__in=ids)
    corrective_in_period=corrective_orders.filter(created_at__gte=period_start,created_at__lte=now)
    preventive_in_period=preventive_orders.filter(created_at__gte=period_start,created_at__lte=now)
    open_corrective_orders=corrective_orders.exclude(status='CONCLUIDA')
    total=equipment.count()
    fault_count=open_corrective_orders.values('equipment_id').distinct().count()
    open_order_count=open_corrective_orders.count()+preventive_orders.filter(status='ABERTA').count()
    # Calcula a porcentagem de equipamentos sem uma ordem corretiva aberta.
    availability=round(100*(total-fault_count)/total,1) if total else None
    repair_hours=[]
    for repair_start,repair_end in corrective_orders.filter(status='CONCLUIDA',finished_at__gte=period_start,finished_at__lte=now,started_at__isnull=False).values_list('started_at','finished_at'):
        if repair_end and repair_end>=repair_start: repair_hours.append((repair_end-repair_start).total_seconds()/3600)
    daily_counts={first_day+timedelta(days=i):{'opened':0,'closed':0} for i in range(days)}
    def count_by_day(queryset,date_field,count_key):
        groups=queryset.annotate(day=TruncDate(date_field,tzinfo=timezone.get_current_timezone())).values('day').annotate(total=Count('pk'))
        for group in groups:
            if group['day'] in daily_counts:daily_counts[group['day']][count_key]+=group['total']
    count_by_day(corrective_in_period,'created_at','opened')
    count_by_day(preventive_in_period,'created_at','opened')
    count_by_day(corrective_orders.filter(status='CONCLUIDA',finished_at__gte=period_start,finished_at__lte=now),'finished_at','closed')
    count_by_day(preventive_orders.filter(status='CONCLUIDA',finished_at__gte=period_start,finished_at__lte=now),'finished_at','closed')
    recent_orders=[]
    for order in corrective_in_period.select_related('equipment','equipment__equipment_type').order_by('-created_at','-pk')[:6]:
        e=order.equipment
        recent_orders.append({'id':order.pk,'number':f'OS-{order.pk:06d}','equipment':e.asset_number or e.model or e.equipment_type.name,'kind':'CORRETIVA','status':order.status,'created_at':order.created_at})
    for order in preventive_in_period.select_related('schedule__equipment','schedule__equipment__equipment_type').order_by('-created_at','-pk')[:6]:
        e=order.schedule.equipment
        recent_orders.append({'id':order.pk,'number':order.number,'equipment':e.asset_number or e.model or e.equipment_type.name,'kind':'PREVENTIVA','status':order.status,'created_at':order.created_at})
    recent_orders.sort(key=lambda r:(r['created_at'],r['number']),reverse=True)
    return {'generated_at':now,'days':days,'start_date':first_day,'end_date':today,
        'summary':{'equipment_total':total,'equipment_active':total-fault_count,'equipment_fault':fault_count,'open_orders':open_order_count,'availability_pct':availability,'mttr_hours':round(sum(repair_hours)/len(repair_hours),2) if repair_hours else None,'mttr_sample':len(repair_hours),'mtbf_hours':None},
        'distribution':{'corrective':corrective_in_period.count(),'preventive':preventive_in_period.count(),'predictive':None},
        'evolution':[{'date':day,**counts} for day,counts in daily_counts.items()],
        'latest_orders':recent_orders[:6]}
