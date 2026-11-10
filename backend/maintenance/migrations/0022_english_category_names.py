from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Renomeia o estado do ORM sem alterar tabelas, colunas ou dados existentes."""

    dependencies = [('maintenance', '0021_rename_movimentacaoestoque_stockmovement')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel('CategoriaMaterial', 'MaterialCategory'),
                migrations.CreateModel(
                    name='SparePartCategory',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('spare_part', models.ForeignKey(db_column='sparepart_id', on_delete=django.db.models.deletion.CASCADE, to='maintenance.sparepart')),
                        ('category', models.ForeignKey(db_column='categoriamaterial_id', on_delete=django.db.models.deletion.CASCADE, to='maintenance.materialcategory')),
                    ],
                    options={'db_table': 'categorias_pecas', 'unique_together': {('spare_part', 'category')}},
                ),
                migrations.RenameField('sparepart', 'categorias', 'categories'),
                migrations.AlterField(
                    model_name='sparepart', name='categories',
                    field=models.ManyToManyField(blank=True, related_name='parts', through='maintenance.SparePartCategory', to='maintenance.materialcategory'),
                ),
            ],
        ),
    ]
