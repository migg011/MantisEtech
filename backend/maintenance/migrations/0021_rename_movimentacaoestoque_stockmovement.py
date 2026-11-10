from django.db import migrations


class Migration(migrations.Migration):
    """Keep the physical table while exposing the English model name to Django."""

    dependencies = [
        ('maintenance', '0020_descricao_ocorrencia_os'),
    ]

    operations = [
        migrations.RenameModel(old_name='MovimentacaoEstoque', new_name='StockMovement'),
    ]
