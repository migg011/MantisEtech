from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('maintenance', '0029_english_table_names')]

    operations = [
        # Restore the table names used by the incoming version.
        migrations.AlterModelTable('activitylog', 'registro_atividades'),
        migrations.AlterModelTable('equipment', 'equipamentos'),
        migrations.AlterModelTable('equipmentattachment', 'anexos_equipamento'),
        migrations.AlterModelTable('equipmentmovement', 'movimentacoes_equipamento'),
        migrations.AlterModelTable('equipmentpreventive', 'agendas_preventiva'),
        migrations.AlterModelTable('equipmenttype', 'tipos_equipamento'),
        migrations.AlterModelTable('line', 'linhas'),
        migrations.AlterModelTable('linependency', 'pendencias_linha'),
        migrations.AlterModelTable('materialcategory', 'categorias_materiais'),
        migrations.AlterModelTable('operatorsession', 'sessoes_operadores'),
        migrations.AlterModelTable('partrequisition', 'solicitacoes_pecas_manutencao'),
        migrations.AlterModelTable('preventivechecklist', 'roteiros_preventiva'),
        migrations.AlterModelTable('preventiveexecution', 'execucoes_preventiva'),
        migrations.AlterModelTable('preventiveorder', 'ordens_preventiva'),
        migrations.AlterModelTable('problemtype', 'tipos_problema'),
        migrations.AlterModelTable('purchaseevent', 'eventos_solicitacao_compra'),
        migrations.AlterModelTable('purchaseitem', 'itens_solicitacao_compra'),
        migrations.AlterModelTable('purchaserequest', 'solicitacoes_compra'),
        migrations.AlterModelTable('sector', 'setores'),
        migrations.AlterModelTable('sparepart', 'pecas_reposicao'),
        migrations.AlterModelTable('sparepartcategory', 'categorias_pecas'),
        migrations.AlterModelTable('sparepartcompatibility', 'compatibilidade_pecas_equipamentos'),
        migrations.AlterModelTable('spareparttechnical', 'fichas_tecnicas_pecas'),
        migrations.AlterModelTable('stockmovement', 'movimentacoes_estoque_pecas'),
        migrations.AlterModelTable('user', 'usuarios'),
        migrations.AlterModelTable('workorder', 'ordens_servico'),
        migrations.RenameModel('StockMovement', 'MovimentacaoEstoque'),
        migrations.RenameModel('MaterialCategory', 'CategoriaMaterial'),
        # Both ORM representations use the same join table and columns.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField('sparepart', 'categories'),
                migrations.DeleteModel('SparePartCategory'),
                migrations.AddField(
                    'sparepart',
                    'categorias',
                    models.ManyToManyField(
                        to='maintenance.categoriamaterial',
                        db_table='categorias_pecas',
                        related_name='pecas',
                        blank=True,
                    ),
                ),
            ],
        ),
    ]
