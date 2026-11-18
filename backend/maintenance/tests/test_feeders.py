from django.test import TestCase

from maintenance.api import issue_token_value
from maintenance.models import Feeder, Line, Sector, User


class FeederRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sector = Sector.objects.create(code='SMT-FD', name='Setor SMT')
        cls.line = Line.objects.create(code='SMT-FD-1', name='Linha 1', sector=cls.sector)
        cls.user = User.objects.create_user('FEEDER-ADMIN', None, name='Administrador', role='ADMINISTRADOR')

    def setUp(self):
        self.url = f'/api/sectors/{self.sector.pk}/feeders'
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {issue_token_value(self.user)}'

    def register(self, platform, **details):
        return self.client.post(self.url, {
            'line_id': self.line.pk, 'platform': platform, 'part_number': 'PN-01', 'width': '8 mm',
            **details,
        }, content_type='application/json')

    def test_panasonic_label_is_saved_and_returned_in_catalog(self):
        details = {
            'model_number': 'KXFW1KS5A00', 'serial_number': 'FA0210ANF438066',
            'tape_type': 'BOTH', 'manufacturing_code': '2017G',
        }
        response = self.register('NPM', **details)
        self.assertEqual(response.status_code, 201, response.content)
        item = self.client.get(self.url).json()['feeders'][0]
        self.assertEqual({key: item[key] for key in details}, details)

    def test_platforms_remain_usable_without_panasonic_details(self):
        for platform in ('NXT', 'NPM'):
            with self.subTest(platform=platform):
                response = self.register(platform)
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(response.json()['serial_number'], '')

    def test_invalid_tape_cannot_create_panasonic_feeder(self):
        response = self.register('NPM', tape_type='INVALID')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Feeder.objects.exists())
