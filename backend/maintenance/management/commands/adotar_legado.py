"""Comando de compatibilidade para uma cópia do PostgreSQL antigo; não é necessário para um banco novo."""

from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

class Command(BaseCommand):
    """Comando de compatibilidade para uma cópia do PostgreSQL antigo; não é necessário para um banco novo."""
    help = 'Adota uma CÓPIA do PostgreSQL original: atualiza esquema aditivamente e registra migrações Django.'
    def handle(self, *args, **options):
        """Executa a adoção do esquema de uma cópia legada e aplica as migrações Django."""
        if connection.vendor != 'postgresql':
            raise CommandError('Este comando é exclusivo para PostgreSQL.')
        tables = set(connection.introspection.table_names())
        if not {'users', 'equipment', 'lines'}.issubset(tables):
            raise CommandError('As tabelas do sistema original não foram encontradas. Para banco novo, use migrate.')
        sql_dir = Path(__file__).resolve().parents[2] / 'legacy_sql'
        with transaction.atomic(), connection.cursor() as cursor:
            for path in sorted(sql_dir.glob('*.sql')):
                cursor.execute(path.read_text(encoding='utf-8'))
            cursor.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ NULL')
        call_command('migrate', fake_initial=True, interactive=False)
        self.stdout.write(self.style.SUCCESS('Esquema legado adotado; usuários, equipamentos, anexos e históricos preservados.'))
