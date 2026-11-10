"""Evolução versionada do banco: 0002_equipment_types. Usa o estado histórico dos modelos e é executada pelo comando migrate."""

from django.db import migrations

TYPES = ['PICK & PLACE', 'PRINTER', 'CONVEYOR', 'BUFFER', 'AOI', 'SPI', 'ROUTER', 'LASER', 'VACUUM LOADER', 'MAGAZINE LOADER', 'REFLOW', 'DISPENSING']

def seed_types(apps, schema_editor):
    """Usa os modelos históricos da migração para inserir os tipos iniciais sem depender do models.py atual."""
    equipment_type = apps.get_model('maintenance', 'EquipmentType')
    for pk, name in enumerate(TYPES, 1):
        equipment_type.objects.using(schema_editor.connection.alias).get_or_create(pk=pk, defaults={'name': name})

class Migration(migrations.Migration):
    """Declara dependências e operações desta versão do esquema; migrate registra sua aplicação no banco."""
    dependencies = [('maintenance', '0001_initial')]
    operations = [migrations.RunPython(seed_types, migrations.RunPython.noop)]
