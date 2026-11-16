"""Cria a tabela registro_atividades para auditoria de operações administrativas."""
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0027_preventive_schedule_time')]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actor_id', models.PositiveBigIntegerField(db_column='autor_id')),
                ('actor_name', models.CharField('Autor', db_column='autor_nome', max_length=200)),
                ('actor_registration', models.CharField('Matrícula', db_column='autor_matricula', max_length=80)),
                ('method', models.CharField('Método HTTP', db_column='metodo', max_length=8)),
                ('route', models.CharField('Rota', db_column='rota', max_length=180)),
                ('target', models.JSONField('Alvo', db_column='alvo', default=dict)),
                ('created_at', models.DateTimeField(db_column='criado_em', db_index=True,
                                                     default=django.utils.timezone.now)),
            ],
            options={'db_table': 'registro_atividades', 'ordering': ['-created_at', '-pk']},
        ),
    ]
