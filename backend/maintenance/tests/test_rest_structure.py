"""DRF integration regressions: authentication, filters, contracts, and services."""
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework.serializers import ModelSerializer
from rest_framework.views import APIView

from maintenance import serializers
from maintenance.authentication import issue_token
from maintenance.models import User, Sector, Line, Equipment, EquipmentType
from maintenance.services.base import OperationContext, Result
from maintenance.services.organization import sectors


class RestContractTests(SimpleTestCase):
    def test_main_routes_are_drf_views(self):
        paths = [
            '/api/auth/login', '/api/me', '/api/dashboard', '/api/line-status',
            '/api/users', '/api/users/1/status', '/api/sectors', '/api/lines',
            '/api/lines/1/equipment/2', '/api/equipment/1/attachments/PHOTO/download',
            '/api/orders/1/start', '/api/orders/1/pendencies',
            '/api/spare-parts/inventory.csv', '/api/spare-parts/1/stock-movements',
            '/api/spare-purchase/parts/1/technical', '/api/spare-purchase/requests/1/export.csv',
            '/api/preventive-checklists/document', '/api/preventive-orders/1/complete',
            '/api/v1/auth/login/', '/api/v1/users/', '/api/v1/work-orders/',
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(issubclass(resolve(path).func.cls, APIView))

    def test_serializers_use_real_fields_and_expose_no_secrets(self):
        for name, klass in vars(serializers).items():
            if isinstance(klass, type) and issubclass(klass, ModelSerializer):
                with self.subTest(serializer=name):
                    fields = klass().fields
                    self.assertIsInstance(klass.Meta.fields, list)
                    self.assertFalse({'password', 'content', 'photo_data', 'datasheet_data'} & fields.keys())
                    self.assertTrue(all(field.read_only for field in fields.values()))


class RestIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('REST-ADM', 'Senha-Teste-123456', name='Administrador REST',
                                                role='ADMINISTRADOR')
        cls.technician = User.objects.create_user('REST-TEC', 'Senha-Teste-123456', name='Técnico REST', role='TECNICO')
        sector = Sector.objects.create(code='REST-SET', name='SMT')
        cls.line = Line.objects.create(code='REST-L1', name='Linha REST 1', sector=sector)
        other_line = Line.objects.create(code='REST-L2', name='Linha REST 2', sector=sector)
        cls.operator = User.objects.create_user('REST-OP', 'Senha-Teste-123456', name='Operador REST',
                                                role='OPERADOR', line=cls.line)
        kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'Máquina REST'})
        cls.machine = Equipment.objects.create(name='Máquina REST própria', equipment_type=kind, sector=sector,
                                                 line=cls.line, position=1)
        Equipment.objects.create(name='Máquina REST outra linha', equipment_type=kind, sector=sector, line=other_line,
                                   position=1)

    def setUp(self):
        cache.clear()

    def api_client(self, user):
        return Client(HTTP_AUTHORIZATION='Bearer ' + issue_token(user))

    def test_login_and_v1_query_use_same_angular_bearer(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/api/v1/auth/login/', {'registration': 'REST-ADM', 'password': 'Senha-Teste-123456'},
                                content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()['token']
        identity = client.get('/api/me', HTTP_AUTHORIZATION='Bearer ' + token)
        self.assertEqual(identity.status_code, 200)
        self.assertEqual(identity.json()['registration'], 'REST-ADM')
        self.assertEqual(client.get('/api/v1/users/', HTTP_AUTHORIZATION='Bearer ' + token).status_code, 200)

    def test_session_cookie_does_not_replace_token(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/api/users').status_code, 401)

    def test_operator_has_same_restrictions_in_both_apis(self):
        client = self.api_client(self.operator)
        self.assertEqual(client.get('/api/users').status_code, 403)
        self.assertEqual(client.get('/api/v1/users/').status_code, 403)
        for path in ['/api/equipment', '/api/v1/equipments/']:
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual([item['id'] for item in response.json()], [self.machine.pk])

    def test_filters_apply_after_access_scope(self):
        client = self.api_client(self.admin)
        response = client.get('/api/equipment', {'q': 'própria', 'lineId': self.line.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['id'] for item in response.json()], [self.machine.pk])
        self.assertEqual(client.get('/api/equipment', {'equipmentTypeId': 'inválido'}).status_code, 400)
        users = client.get('/api/users', {'role': 'TECNICO'}).json()
        self.assertEqual([user['registration'] for user in users], ['REST-TEC'])

    def test_registration_service_works_without_http_request(self):
        result = sectors(OperationContext(user=self.technician, method='POST', data={'name': 'Novo setor REST'}))
        self.assertIsInstance(result, Result)
        self.assertEqual(result.status, 201)
        self.assertTrue(Sector.objects.filter(pk=result.data['id'], name='Novo setor REST').exists())

    def test_json_errors_and_token_invalidation(self):
        client = self.api_client(self.admin)
        response = client.post('/api/sectors', {'name': 'X'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertIn('details', response.json())
        self.admin.set_password('Outra-Senha-123456')
        self.admin.save(update_fields=['password'])
        self.assertEqual(client.get('/api/me').status_code, 401)
