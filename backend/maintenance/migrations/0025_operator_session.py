"""Cria a tabela sessoes_operadores para registrar o login do operador no totem."""
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0024_equipment_ranges_and_electrical')]

    operations = [
        migrations.CreateModel(
            name='OperatorSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('opened_at', models.DateTimeField(db_column='aberta_em', default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(db_column='expira_em', db_index=True)),
                ('line', models.ForeignKey(blank=True, db_column='linha_id', null=True,
                                           on_delete=django.db.models.deletion.SET_NULL,
                                           to='maintenance.line', verbose_name='Linha ativa')),
                ('user', models.ForeignKey(db_column='usuario_id',
                                           on_delete=django.db.models.deletion.CASCADE,
                                           to=settings.AUTH_USER_MODEL, verbose_name='Operador')),
            ],
            options={'db_table': 'sessoes_operadores', 'ordering': ['-opened_at']},
        ),
    ]
