"""Cria o cadastro de feeders e os registros de preventiva/conserto por feeder."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0025_operator_session')]

    operations = [
        migrations.CreateModel(
            name='Feeder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField('Plataforma', db_column='plataforma', max_length=3,
                                              choices=[('NXT', 'NXT Fuji'), ('NPM', 'NPM Panasonic')])),
                ('part_number', models.CharField('Part number', db_column='part_number', max_length=100)),
                ('width', models.CharField('Largura', db_column='largura', max_length=40)),
                ('model_number', models.CharField('Modelo', db_column='modelo', blank=True, default='', max_length=100)),
                ('serial_number', models.CharField('Número de série', db_column='numero_serie', blank=True, default='', max_length=100)),
                ('tape_type', models.CharField('Tipo de fita', db_column='tipo_fita', blank=True, default='', max_length=6,
                                               choices=[('EMBOSS', 'Emboss'), ('PAPER', 'Paper'), ('BOTH', 'Emboss e Paper')])),
                ('manufacturing_code', models.CharField('Código do fabricante', db_column='codigo_fabricante',
                                                        blank=True, default='', max_length=40)),
                ('line', models.ForeignKey(blank=True, db_column='linha_id', null=True,
                                           on_delete=django.db.models.deletion.PROTECT,
                                           related_name='feeders', to='maintenance.line', verbose_name='Linha SMT')),
                ('sector', models.ForeignKey(db_column='setor_id',
                                             on_delete=django.db.models.deletion.PROTECT,
                                             related_name='feeders', to='maintenance.sector', verbose_name='Setor')),
            ],
            options={'db_table': 'feeders', 'ordering': ['part_number', 'id']},
        ),
        migrations.AddConstraint(
            model_name='feeder',
            constraint=models.CheckConstraint(condition=models.Q(platform__in=['NXT', 'NPM']),
                                              name='feeder_valid_platform'),
        ),
        migrations.CreateModel(
            name='FeederMaintenance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField('Tipo', db_column='tipo', default='PREVENTIVE', max_length=10,
                                          choices=[('PREVENTIVE', 'Preventiva'), ('REPAIR', 'Conserto')])),
                ('date', models.DateField('Data', db_column='data')),
                ('description', models.TextField('Descrição', db_column='descricao', max_length=4000)),
                ('feeder', models.ForeignKey(db_column='feeder_id',
                                             on_delete=django.db.models.deletion.PROTECT,
                                             related_name='maintenance_records', to='maintenance.feeder',
                                             verbose_name='Feeder')),
            ],
            options={'db_table': 'feeder_preventives', 'ordering': ['-date', '-id']},
        ),
        migrations.AddConstraint(
            model_name='feedermaintenance',
            constraint=models.CheckConstraint(condition=models.Q(kind__in=['PREVENTIVE', 'REPAIR']),
                                              name='feeder_valid_maintenance_type'),
        ),
    ]
