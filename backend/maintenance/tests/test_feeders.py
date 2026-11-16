"""Testes do cadastro de feeders e do histórico de preventivas/consertos."""

from datetime import date

from django.core.cache import cache
from django.test import TestCase

from maintenance.authentication import issue_token
from maintenance.models import Feeder, FeederMaintenance, Line, Sector, User


class FeederRegistrationTests(TestCase):
    """Cadastro, filtro e validações do feeder."""

    @classmethod
    def setUpTestData(cls):
        """Prepara dois setores, duas linhas e contas usadas em todos os cenários."""
        cls.sector = Sector.objects.create(code='SET-F', name='SMT')
        cls.other_sector = Sector.objects.create(code='SET-F2', name='DIP')
        cls.line = Line.objects.create(code='LIN-F', name='Linha F', sector=cls.sector)
        cls.foreign_line = Line.objects.create(code='LIN-F2', name='Linha F2', sector=cls.other_sector)
        cls.admin = User.objects.create_user('ADM-F', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')
        cls.tech = User.objects.create_user('TEC-F', 'Strong-Test-Password-123',
                                            name='Técnico', role='TECNICO', sector=cls.sector)

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def as_user(self, user):
        """Reautentica o cliente HTTP para o usuário informado."""
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(user)

    def send(self, method, url, data=None, expected=200):
        """Executa a chamada JSON e devolve o corpo validado."""
        response = getattr(self.client, method)(url, data if data is not None else {},
                                                content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content[:400])
        return response.json() if response.content else {}

    def test_create_feeder_nxt(self):
        """O cadastro de feeder NXT persiste os campos obrigatórios."""
        created = self.send('post', '/api/feeders', {
            'sectorId': self.sector.pk, 'lineId': self.line.pk,
            'platform': 'NXT', 'part_number': 'FP-001', 'width': '8mm',
        }, expected=201)
        self.assertEqual(created['platform'], 'NXT')
        self.assertEqual(created['part_number'], 'FP-001')

    def test_create_feeder_panasonic_with_details(self):
        """O cadastro NPM aceita os campos específicos da Panasonic."""
        created = self.send('post', '/api/feeders', {
            'sectorId': self.sector.pk,
            'platform': 'NPM', 'part_number': 'NPM-200', 'width': '12mm',
            'model_number': 'NP12-BG', 'serial_number': 'SN-ABC',
            'tape_type': 'EMBOSS', 'manufacturing_code': 'CM-XYZ',
        }, expected=201)
        self.assertEqual(created['serial_number'], 'SN-ABC')
        self.assertEqual(created['tape_type'], 'EMBOSS')

    def test_line_from_other_sector_is_rejected(self):
        """A validação de formulário rejeita a linha de outro setor."""
        self.send('post', '/api/feeders', {
            'sectorId': self.sector.pk, 'lineId': self.foreign_line.pk,
            'platform': 'NXT', 'part_number': 'FP-002', 'width': '8mm',
        }, expected=400)

    def test_technician_lists_only_own_sector(self):
        """O técnico vê apenas os feeders do próprio setor."""
        Feeder.objects.create(sector=self.sector, platform='NXT', part_number='OWN', width='8mm')
        Feeder.objects.create(sector=self.other_sector, platform='NXT', part_number='FOREIGN', width='8mm')
        self.as_user(self.tech)
        rows = self.send('get', '/api/feeders')
        parts = {row['part_number'] for row in rows}
        self.assertIn('OWN', parts)
        self.assertNotIn('FOREIGN', parts)


class FeederMaintenanceTests(TestCase):
    """Histórico de preventiva/conserto por feeder."""

    @classmethod
    def setUpTestData(cls):
        """Prepara o feeder e a conta de administrador para o cenário de histórico."""
        cls.sector = Sector.objects.create(code='SET-FM', name='SMT')
        cls.feeder = Feeder.objects.create(
            sector=cls.sector, platform='NPM', part_number='PN-100', width='8mm')
        cls.admin = User.objects.create_user('ADM-FM', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def test_record_preventive(self):
        """O endpoint registra uma preventiva vinculada ao feeder."""
        response = self.client.post(
            f'/api/feeders/{self.feeder.pk}/maintenance',
            {'kind': 'PREVENTIVE', 'date': date.today().isoformat(),
             'description': 'Limpeza e lubrificação completas.'},
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertTrue(FeederMaintenance.objects.filter(feeder=self.feeder, kind='PREVENTIVE').exists())

    def test_list_history(self):
        """A listagem devolve o histórico ordenado pela data mais recente."""
        FeederMaintenance.objects.create(feeder=self.feeder, kind='PREVENTIVE',
                                         date=date(2026, 1, 10), description='Antiga.')
        FeederMaintenance.objects.create(feeder=self.feeder, kind='REPAIR',
                                         date=date(2026, 6, 20), description='Reparo recente.')
        response = self.client.get(f'/api/feeders/{self.feeder.pk}/maintenance')
        rows = response.json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['kind'], 'REPAIR')

    def test_short_description_rejected(self):
        """Descrições muito curtas são rejeitadas pelo formulário."""
        response = self.client.post(
            f'/api/feeders/{self.feeder.pk}/maintenance',
            {'kind': 'PREVENTIVE', 'date': date.today().isoformat(), 'description': 'ok'},
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
