"""Verify that the public English names remain stable for integrations."""
from datetime import date

from django.test import SimpleTestCase

from maintenance.models import User
from maintenance.services.base import OperationContext, Result, operation
from maintenance.services.preventive_schedule import calculate_next_due, parse_date
from maintenance.services.registrations import generate_internal_code


class PublicNamesTests(SimpleTestCase):
    def test_service_arguments_are_accepted(self):
        self.assertEqual(calculate_next_due(date(2026, 1, 31), 'MENSAL'), date(2026, 2, 28))
        self.assertEqual(parse_date('2026-01-31', 'Data'), date(2026, 1, 31))
        self.assertTrue(generate_internal_code('TESTE').startswith('TESTE-'))

    def test_operation_decorator_keeps_roles_and_public(self):
        @operation(['GET'], roles=['TECNICO'], public=True)
        def read(context):
            return Result({'ok': True})

        response = read(OperationContext(method='GET'))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.data, {'ok': True})

    def test_model_name_preserves_django_record(self):
        self.assertEqual(User._meta.label, 'maintenance.User')
        self.assertEqual(User._meta.db_table, 'usuarios')
