"""Permite faixas (ex.: 220-240) em tensão, frequência e pressão, e adiciona a categoria Esquema elétrico aos anexos do equipamento."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0023_user_sector')]

    operations = [
        migrations.AlterField(
            model_name='equipment',
            name='voltage_v',
            field=models.CharField('Tensão (V)', blank=True, db_column='tensao_v', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='equipment',
            name='frequency_hz',
            field=models.CharField('Frequência (Hz)', blank=True, db_column='frequencia_hz', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='equipment',
            name='pneumatic_pressure_bar',
            field=models.CharField('Pressão pneumática (bar)', blank=True, db_column='pressao_pneumatica_bar', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='equipmentattachment',
            name='kind',
            field=models.CharField(
                max_length=10,
                db_column='categoria',
                choices=[('PHOTO', 'Foto'), ('MANUAL', 'Manual técnico'), ('ELECTRICAL', 'Esquema elétrico')],
            ),
        ),
    ]
