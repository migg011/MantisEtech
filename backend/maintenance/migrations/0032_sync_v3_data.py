from datetime import date

from django.db import migrations


def assign_demo_stock(apps, schema_editor):
    part = apps.get_model('maintenance', 'SparePart')
    movement = apps.get_model('maintenance', 'MovimentacaoEstoque')
    purchase = apps.get_model('maintenance', 'PurchaseRequest')
    sector = apps.get_model('maintenance', 'Sector')
    balance = apps.get_model('maintenance', 'SectorStock')
    alias = schema_editor.connection.alias
    parts = part.objects.using(alias).filter(stock_quantity__isnull=False)
    movements = movement.objects.using(alias).filter(sector__isnull=True)
    purchases = purchase.objects.using(alias).filter(sector__isnull=True)
    if not (parts.exists() or movements.exists() or purchases.exists()):
        return

    demo, _ = sector.objects.using(alias).get_or_create(code='ESTOQUE-DEMO', defaults={
        'name': 'Estoque demonstrativo', 'cost_center': 'DEMO',
    })
    balance.objects.using(alias).bulk_create((
        balance(spare_part_id=row.pk, sector_id=demo.pk, quantity=row.stock_quantity,
                location=row.storage_location or '')
        for row in parts.defer('photo_data', 'datasheet_data').iterator()
    ), batch_size=500)
    movements.update(sector_id=demo.pk)
    purchases.update(sector_id=demo.pk)


def align_annual_dates(apps, schema_editor):
    schedule_model = apps.get_model('maintenance', 'EquipmentPreventive')
    alias = schema_editor.connection.alias
    schedules = schedule_model.objects.using(alias).filter(active=True, frequency='ANUAL').exclude(orders__status='ABERTA')
    for schedule in schedules.iterator():
        due = schedule.next_due
        year = due.year - (due.month == 1 and due.day <= 3)
        schedule.next_due = date(year, 12, 20)
        schedule.save(using=alias, update_fields=['next_due'])


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0031_sync_v3_schema')]

    operations = [
        migrations.RunPython(assign_demo_stock, migrations.RunPython.noop),
        migrations.RunPython(align_annual_dates, migrations.RunPython.noop),
    ]
