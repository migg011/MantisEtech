"""Compatibility command for a copy of the old PostgreSQL database; unnecessary for a new database."""

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    """Compatibility command for a copy of the old PostgreSQL database; unnecessary for a new database."""
    help = 'Adota uma CÓPIA do PostgreSQL original: atualiza esquema aditivamente e registra migrações Django.'

    def handle(self, *args, **options):
        """Adopt the schema of a legacy copy and apply the Django migrations."""
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
        self.stdout.write(self.style.SUCCESS(
            'Esquema legado adotado; usuários, equipamentos, anexos e históricos preservados.'))
