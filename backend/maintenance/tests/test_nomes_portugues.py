"""Testa a renomeação real no PostgreSQL, inclusive sua reversão e chaves compostas."""
from unittest import skipUnless
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'Migração física requer PostgreSQL.')
class TraducaoBancoTests(TransactionTestCase):
    anterior = [('maintenance', '0011_equipmentpreventive_checklist_items_and_more')]
    atual = [('maintenance', '0012_nomes_banco_portugues')]

    def migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def test_preserva_dados_vinculos_arquivos_e_reversao(self):
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            modelos = self.migrar(self.anterior)
            obter = lambda name_value: modelos.get_model('maintenance', name_value)
            setor = obter('Sector').objects.create(code='TRAD', name='Setor teste')
            user_value = obter('User').objects.create(name='Pessoa teste', registration='TRAD', password='hash-preservado', role='ADMINISTRADOR')
            tipo, _ = obter('EquipmentType').objects.get_or_create(id=1, defaults={'name': 'Tipo teste'})
            maquina = obter('Equipment').objects.create(equipment_type=tipo, sector=setor, serial='TRAD-SERIE')
            part_value = obter('SparePart').objects.create(code='TRAD-PECA', description='Peça teste')
            obter('SparePartCompatibility').objects.create(spare_part=part_value, equipment=maquina)
            obter('SparePartTechnical').objects.create(spare_part=part_value, description_pt='Ficha preservada')
            obter('EquipmentAttachment').objects.create(equipment=maquina, kind='MANUAL', filename='teste.pdf', mime_type='application/pdf', content=b'%PDF-preservado', size_bytes=15, uploaded_by=user_value)
            obter('WorkOrder').objects.create(equipment=maquina, opened_by=user_value, problem='Problema preservado')
            for destino in (self.atual, self.anterior, self.atual):
                modelos = self.migrar(destino)
                obter = lambda name_value: modelos.get_model('maintenance', name_value)
                self.assertEqual(obter('User').objects.get(pk=user_value.pk).password, 'hash-preservado')
                self.assertEqual(obter('Equipment').objects.get(pk=maquina.pk).sector_id, setor.pk)
                self.assertEqual(obter('SparePartCompatibility').objects.get(spare_part_id=part_value.pk).equipment_id, maquina.pk)
                self.assertEqual(obter('SparePartTechnical').objects.get(pk=part_value.pk).description_pt, 'Ficha preservada')
                self.assertEqual(bytes(obter('EquipmentAttachment').objects.get(equipment_id=maquina.pk).content), b'%PDF-preservado')
                self.assertEqual(obter('WorkOrder').objects.get(equipment_id=maquina.pk).opened_by_id, user_value.pk)
            tables_value = connection.introspection.table_names()
            self.assertIn('usuarios', tables_value)
            self.assertNotIn('users', tables_value)
            with connection.cursor() as cursor:
                colunas = connection.introspection.get_table_description(cursor, 'usuarios')
            self.assertIn('senha_hash', [coluna.name for coluna in colunas])
        finally:
            # Mesmo em caso de falha, os próximos testes recebem o esquema atual.
            self.migrar(latest)
