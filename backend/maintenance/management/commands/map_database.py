"""Document the physical schema and ORM. The transaction is read-only and exports no personal data."""
import inspect
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader

from maintenance.portuguese_names import TABLE_NAMES


MODULES = {
    'Estrutura industrial': ['sectors', 'lines', 'equipment_types', 'equipment', 'equipment_movements',
                             'equipment_attachments'],
    'Acesso e usuários': ['users'],
    'Manutenção corretiva': ['problem_types', 'work_orders', 'line_pendencies',
                             'maintenance_part_requisitions'],
    'Manutenção preventiva': ['preventive_checklists', 'equipment_preventives', 'preventive_orders',
                              'preventive_executions'],
    'Peças e documentação técnica': ['spare_parts', 'spare_part_compatibility', 'spare_part_technical'],
    'Compras e aprovação': ['spare_purchase_requests', 'spare_purchase_request_items', 'spare_purchase_events'],
}
MODULES = {group: [TABLE_NAMES.get(table, table) for table in tables] for group, tables in MODULES.items()}


class Command(BaseCommand):
    help = 'Extrai metadados e contagens do PostgreSQL, sem alterar o banco nem expor valores de registros.'

    def add_arguments(self, parser):
        """Make the output directory explicit; only documentation files are written."""
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        """Combine current models and the real catalog in a consistent read-only transaction."""
        if connection.vendor != 'postgresql':
            raise RuntimeError('Execute com as configurações PostgreSQL, não com SQLite de testes.')
        models = {model._meta.db_table: model for model in apps.get_models()}
        result = {'captured_at': datetime.now(ZoneInfo('America/Manaus')).isoformat(), 'modules': MODULES,
                  'tables': []}
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                cursor.execute("SELECT current_database(), current_setting('server_version'), current_schema()")
                result['database'], result['server_version'], result['schema'] = cursor.fetchone()
                cursor.execute("SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname")
                tables = cursor.fetchall()
                for name, size in tables:
                    # Identifiers come from the catalog and are quoted by the backend; no name becomes executable SQL.
                    quoted = connection.ops.quote_name(name)
                    cursor.execute(f'SELECT COUNT(*) FROM public.{quoted}')
                    table = {'name': name, 'rows': cursor.fetchone()[0], 'bytes': size,
                             'module': next((group for group, names in MODULES.items() if name in names),
                                            'Infraestrutura Django')}
                    model = models.get(name)
                    table['model'] = model.__name__ if model else None
                    table['purpose'] = inspect.getdoc(model) if model else 'Controle interno de versões do esquema.'
                    table['source'] = (f'maintenance/models.py:{inspect.getsourcelines(model)[1]}'
                                       if model and model._meta.app_label == 'maintenance' else None)
                    fields = {field.column: field for field in model._meta.concrete_fields if field.column} \
                        if model else {}
                    cursor.execute("""SELECT column_name, data_type, udt_name, is_nullable, column_default,
                        is_identity, character_maximum_length, numeric_precision, numeric_scale
                        FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
                                   [name])
                    table['columns'] = []
                    for column in cursor.fetchall():
                        entry = dict(zip(['name', 'type', 'pg_type', 'nullable', 'default', 'identity', 'length',
                                          'precision', 'scale'], column))
                        entry['nullable'] = entry['nullable'] == 'YES'
                        field = fields.get(entry['name'])
                        if field:
                            entry.update({'orm_field': field.name, 'label': str(field.verbose_name),
                                          'choices': list(field.choices or [])})
                            if field.is_relation:
                                entry['orm_relation'] = {'table': field.related_model._meta.db_table,
                                                         'column': field.target_field.column,
                                                         'on_delete': field.remote_field.on_delete.__name__,
                                                         'one_to_one': field.one_to_one}
                        table['columns'].append(entry)
                    cursor.execute("""SELECT con.conname, con.contype, pg_get_constraintdef(con.oid), con.convalidated,
                        target.relname, con.condeferrable, con.condeferred
                        FROM pg_constraint con JOIN pg_class source ON source.oid=con.conrelid
                        JOIN pg_namespace n ON n.oid=source.relnamespace
                        LEFT JOIN pg_class target ON target.oid=con.confrelid
                        WHERE n.nspname='public' AND source.relname=%s ORDER BY con.conname""", [name])
                    table['constraints'] = [dict(zip(['name', 'kind', 'definition', 'validated', 'target',
                                                      'deferrable', 'deferred'], row)) for row in cursor.fetchall()]
                    cursor.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=%s ORDER BY indexname",
                                   [name])
                    table['indexes'] = [dict(zip(['name', 'definition'], row)) for row in cursor.fetchall()]
                    result['tables'].append(table)
                loader = MigrationLoader(connection)
                result['pending_migrations'] = sorted(f'{app}.{name}' for app, name in
                                                      set(loader.disk_migrations) - loader.applied_migrations.keys())
                cursor.execute('SELECT app,name FROM django_migrations ORDER BY app,name')
                result['applied_migrations'] = [f'{app}.{name}' for app, name in cursor.fetchall()]
                cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema='public' ORDER BY table_name")
                result['views'] = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT event_object_table,trigger_name,event_manipulation FROM information_schema.triggers WHERE trigger_schema='public'")
                result['triggers'] = [dict(zip(['table', 'name', 'event'], row)) for row in cursor.fetchall()]
        expected = {name for name, model in models.items() if model._meta.app_label == 'maintenance'}
        found = {table['name'] for table in result['tables']}
        result['missing_model_tables'] = sorted(expected - found)
        result['missing_model_columns'] = []
        for table in result['tables']:
            model = models.get(table['name'])
            if model:
                actual = {column['name'] for column in table['columns']}
                result['missing_model_columns'].extend(
                    f'{table["name"]}.{field.column}' for field in model._meta.concrete_fields
                    if field.column and field.column not in actual)
        output = Path(options['output'])
        output.mkdir(parents=True, exist_ok=True)
        (output / 'catalogo-postgres.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                        encoding='utf-8')
        self.stdout.write(json.dumps({'database': result['database'], 'tables': len(found),
                                      'business_tables': len(expected & found),
                                      'columns': sum(len(table['columns']) for table in result['tables']),
                                      'foreign_keys': sum(constraint['kind'] == 'f' for table in result['tables']
                                                          for constraint in table['constraints']),
                                      'pending_migrations': result['pending_migrations'],
                                      'missing_model_tables': result['missing_model_tables'],
                                      'missing_model_columns': result['missing_model_columns']},
                                     ensure_ascii=False))
