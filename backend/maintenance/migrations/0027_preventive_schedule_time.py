"""Adiciona o horário planejado à agenda de preventiva para gerar ordens no turno correto."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0026_feeders')]

    operations = [
        migrations.AddField(
            model_name='equipmentpreventive',
            name='planned_time',
            field=models.TimeField('Horário planejado', blank=True, db_column='hora_programada', null=True),
        ),
    ]
