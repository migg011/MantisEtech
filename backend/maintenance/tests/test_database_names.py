"""Test the actual PostgreSQL rename, including its reversal and composite keys."""
from unittest import skipUnless
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'The physical migration requires PostgreSQL.')
class DatabaseTranslationTests(TransactionTestCase):
    previous = [('maintenance', '0011_equipmentpreventive_checklist_items_and_more')]
    current = [('maintenance', '0012_nomes_banco_portugues')]

    def migrate_to(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_preserves_data_links_files_and_reversal(self):
        # The test exercises 0012, but the suite must remain on the latest schema.
        final_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        models = self.migrate_to(self.previous)
        try:
            get_model = lambda name: models.get_model('maintenance', name)
            sector = get_model('Sector').objects.create(code='TRAD', name='Setor teste')
            user = get_model('User').objects.create(name='Pessoa teste', registration='TRAD', password='hash-preservado',
                                                   role='ADMINISTRADOR')
            kind, _ = get_model('EquipmentType').objects.get_or_create(id=1, defaults={'name': 'Tipo teste'})
            machine = get_model('Equipment').objects.create(equipment_type=kind, sector=sector, serial='TRAD-SERIE')
            part = get_model('SparePart').objects.create(code='TRAD-PECA', description='Peça teste')
            get_model('SparePartCompatibility').objects.create(spare_part=part, equipment=machine)
            get_model('SparePartTechnical').objects.create(spare_part=part, description_pt='Ficha preservada')
            get_model('EquipmentAttachment').objects.create(equipment=machine, kind='MANUAL', filename='teste.pdf',
                                                        mime_type='application/pdf', content=b'%PDF-preservado',
                                                        size_bytes=15, uploaded_by=user)
            get_model('WorkOrder').objects.create(equipment=machine, opened_by=user, problem='Problema preservado')
            for target in (self.current, self.previous, self.current):
                models = self.migrate_to(target)
                get_model = lambda name: models.get_model('maintenance', name)
                self.assertEqual(get_model('User').objects.get(pk=user.pk).password, 'hash-preservado')
                self.assertEqual(get_model('Equipment').objects.get(pk=machine.pk).sector_id, sector.pk)
                self.assertEqual(get_model('SparePartCompatibility').objects.get(spare_part_id=part.pk).equipment_id,
                                 machine.pk)
                self.assertEqual(get_model('SparePartTechnical').objects.get(pk=part.pk).description_pt, 'Ficha preservada')
                self.assertEqual(bytes(get_model('EquipmentAttachment').objects.get(equipment_id=machine.pk).content),
                                 b'%PDF-preservado')
                self.assertEqual(get_model('WorkOrder').objects.get(equipment_id=machine.pk).opened_by_id, user.pk)
            tables = connection.introspection.table_names()
            self.assertIn('usuarios', tables)
            self.assertNotIn('users', tables)
            with connection.cursor() as cursor:
                columns = connection.introspection.get_table_description(cursor, 'usuarios')
            self.assertIn('senha_hash', [column.name for column in columns])
        finally:
            # Even on failure, the following tests receive the current schema.
            self.migrate_to(final_targets)
