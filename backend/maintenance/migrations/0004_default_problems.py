"""Evolução versionada do banco: 0004_default_problems. Usa o estado histórico dos modelos e é executada pelo comando migrate."""

from django.db import migrations


def seed_problems(apps, schema_editor):
    """Insere problemas iniciais de manutenção usando o estado histórico do banco desta migração."""
    ProblemType = apps.get_model('maintenance', 'ProblemType')
    for name, priority in [
        ('Equipamento não liga', 'ALTA'),
        ('Falha na alimentação de placas', 'ALTA'),
        ('Falha de sensor', 'MEDIA'),
        ('Travamento mecânico', 'ALTA'),
        ('Falha de comunicação', 'MEDIA'),
        ('Ruído ou vibração anormal', 'MEDIA'),
        ('Falha de qualidade no processo', 'ALTA'),
        ('Vazamento de ar comprimido', 'MEDIA'),
    ]:
        ProblemType.objects.using(schema_editor.connection.alias).get_or_create(
            name=name, defaults={'priority': priority, 'active': True})


class Migration(migrations.Migration):
    """Declara dependências e operações desta versão do esquema; migrate registra sua aplicação no banco."""
    dependencies = [('maintenance', '0003_problem_catalog')]
    operations = [migrations.RunPython(seed_problems, migrations.RunPython.noop)]
