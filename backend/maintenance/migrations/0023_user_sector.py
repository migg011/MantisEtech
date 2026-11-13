"""Vincula o usuário ao setor para restringir equipamentos e OS ao setor da conta."""
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def copy_sector_from_line(apps, schema_editor):
    """Pre-preenche o setor dos operadores e técnicos com o setor da linha vinculada."""
    alias = schema_editor.connection.alias
    users = apps.get_model('maintenance', 'User').objects.using(alias)
    lines = apps.get_model('maintenance', 'Line').objects.using(alias)
    users.filter(role__in=['OPERADOR', 'TECNICO'], line__sector__isnull=False).update(
        sector_id=Subquery(lines.filter(pk=OuterRef('line_id')).values('sector_id')[:1]),
    )


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0022_english_category_names')]
    operations = [
        migrations.AddField(
            model_name='user',
            name='sector',
            field=models.ForeignKey(
                blank=True,
                db_column='setor_id',
                null=True,
                on_delete=models.deletion.PROTECT,
                to='maintenance.sector',
                verbose_name='Setor',
            ),
        ),
        migrations.RunPython(copy_sector_from_line, migrations.RunPython.noop),
    ]
