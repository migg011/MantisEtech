"""Verifica que a tradução não quebra os nomes usados por integrações anteriores."""
from datetime import date
from django.test import SimpleTestCase, RequestFactory
from maintenance import api
from maintenance.models import UserCode, User
from maintenance.schedule_rules import next_due_value
from maintenance.preventive_schedule import next_due, parse_date
from maintenance.services import internal_code


class CompatibilidadePortuguesTests(SimpleTestCase):
    def test_aliases_aceitam_argumentos_nomeados_anteriores(self):
        self.assertEqual(next_due(performed=date(2026, 1, 31), frequency='MENSAL'),
                         next_due_value(date(2026, 1, 31), 'MENSAL'))
        self.assertEqual(parse_date(value='2026-01-31', label='Data'), date(2026, 1, 31))
        self.assertTrue(internal_code(prefix='TESTE').startswith('TESTE-'))

    def test_decorador_antigo_mantem_roles_e_public(self):
        @api.endpoint(['GET'], roles=['TECNICO'], public=True)
        def consultar(request_value):
            return {'ok': True}
        response_value = consultar(RequestFactory().get('/api/teste'))
        self.assertEqual(response_value.status_code, 200)
        self.assertJSONEqual(response_value.content, {'ok': True})

    def test_nome_portugues_do_modelo_preserva_registro_django(self):
        self.assertIs(UserCode, User)
        self.assertEqual(UserCode._meta.label, 'maintenance.User')
        self.assertEqual(UserCode._meta.db_table, 'usuarios')
