"""Testes do vínculo entre usuário e setor: cadastro, filtragem e restrições na OS."""

from django.core.cache import cache
from django.test import Client, TestCase

from maintenance.authentication import issue_token
from maintenance.models import (Equipment, EquipmentType, Line, ProblemType, Sector, User,
                                WorkOrder)


class UserSectorBindingTests(TestCase):
    """Cadastro e serialização do setor vinculado à conta."""

    @classmethod
    def setUpTestData(cls):
        """Prepara setores, linhas e contas compartilhados pelos cenários de vínculo."""
        cls.sector = Sector.objects.create(code='SET-1', name='SMT')
        cls.other_sector = Sector.objects.create(code='SET-2', name='DIP')
        cls.line = Line.objects.create(code='LIN-1', name='Linha 1', sector=cls.sector)
        cls.admin = User.objects.create_user('ADM', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')

    def setUp(self):
        """Autentica cada cenário como administrador e limpa o cache de tentativas."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def send(self, method, url, data=None, expected=200):
        """Executa a chamada JSON e devolve o corpo validando status e tipo de resposta."""
        response = getattr(self.client, method)(url, data if data is not None else {},
                                                content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content[:1000])
        return response.json()

    def test_create_technician_requires_sector(self):
        """A criação de técnico sem setor é rejeitada pelo formulário."""
        error = self.send('post', '/api/users', {
            'name': 'Técnico sem setor', 'registration': 'TEC-NO-SECTOR',
            'role': 'TECNICO', 'password': 'Strong-Test-Password-123',
        }, expected=400)
        self.assertIn('sector', str(error).lower())

    def test_create_technician_stores_sector(self):
        """O cadastro de técnico persiste o setor informado e o devolve na lista."""
        created = self.send('post', '/api/users', {
            'name': 'Técnico 1', 'registration': 'TEC-1', 'role': 'TECNICO',
            'password': 'Strong-Test-Password-123', 'sectorId': self.sector.pk,
        }, expected=201)
        self.assertEqual(created['sector_id'], self.sector.pk)

    def test_administrator_does_not_require_sector(self):
        """Administrador é criado sem setor; o formulário zera o campo nesse perfil."""
        created = self.send('post', '/api/users', {
            'name': 'Novo admin', 'registration': 'ADM-2', 'role': 'ADMINISTRADOR',
            'password': 'Strong-Test-Password-123', 'sectorId': self.sector.pk,
        }, expected=201)
        self.assertIsNone(created['sector_id'])

    def test_patch_user_sets_sector(self):
        """A edição por PATCH persiste o setor informado."""
        operator = User.objects.create_user(
            'OP-MIG', 'Strong-Test-Password-123', name='Operador', role='OPERADOR',
            line=self.line, sector=self.sector)
        updated = self.send('patch', f'/api/users/{operator.pk}', {
            'sectorId': self.other_sector.pk, 'role': 'TECNICO',
        })
        self.assertEqual(updated['sector_id'], self.other_sector.pk)

    def test_user_list_filters_by_sector(self):
        """A lista de usuários aceita o filtro sectorId para localizar a equipe de um setor."""
        User.objects.create_user('TEC-A', 'Strong-Test-Password-123',
                                 name='Técnico A', role='TECNICO', sector=self.sector)
        User.objects.create_user('TEC-B', 'Strong-Test-Password-123',
                                 name='Técnico B', role='TECNICO', sector=self.other_sector)
        rows = self.send('get', f'/api/users?sectorId={self.sector.pk}')
        matriculas = {row['registration'] for row in rows}
        self.assertIn('TEC-A', matriculas)
        self.assertNotIn('TEC-B', matriculas)


class WorkOrderSectorRestrictionTests(TestCase):
    """O fechamento da OS é restrito ao setor do técnico responsável."""

    @classmethod
    def setUpTestData(cls):
        """Prepara dois setores com equipamentos e contas separadas para o cenário de restrição."""
        cls.own_sector = Sector.objects.create(code='SET-OWN', name='SMT')
        cls.foreign_sector = Sector.objects.create(code='SET-OTHER', name='DIP')
        cls.own_line = Line.objects.create(code='LIN-OWN', name='Linha própria', sector=cls.own_sector)
        cls.foreign_line = Line.objects.create(code='LIN-OTHER', name='Linha externa', sector=cls.foreign_sector)
        cls.kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        cls.own_equipment = Equipment.objects.create(
            equipment_type=cls.kind, sector=cls.own_sector, line=cls.own_line, model='Máquina setor próprio', position=1)
        cls.foreign_equipment = Equipment.objects.create(
            equipment_type=cls.kind, sector=cls.foreign_sector, line=cls.foreign_line, model='Máquina setor externo', position=1)
        cls.problem = ProblemType.objects.create(name='Falha no motor', priority='MEDIA')
        cls.admin = User.objects.create_user('ADM', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')
        cls.tech = User.objects.create_user('TEC', 'Strong-Test-Password-123',
                                            name='Técnico', role='TECNICO', sector=cls.own_sector)

    def setUp(self):
        """Limpa o cache de tentativas antes de cada cenário de restrição por setor."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def as_user(self, user):
        """Reautentica o cliente HTTP para a conta informada no cenário."""
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(user)

    def send(self, method, url, data=None, expected=200):
        """Executa a chamada JSON e valida status e corpo retornados."""
        response = getattr(self.client, method)(url, data if data is not None else {},
                                                content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content[:1000])
        return response.json()

    def _open_and_start(self, equipment):
        """Cria a OS como admin, inicia o atendimento pelo técnico e devolve o identificador."""
        self.as_user(self.admin)
        order = self.send('post', '/api/work-orders', {
            'equipmentId': equipment.pk, 'problemTypeId': self.problem.pk,
            'priority': 'MEDIA', 'occurrenceDescription': 'Teste de restrição por setor.',
        }, expected=201)
        self.as_user(self.tech)
        self.send('post', f"/api/work-orders/{order['id']}/start",
                  {'registration': 'TEC', 'password': 'Strong-Test-Password-123'})
        return order['id']

    def test_technician_lists_only_own_sector_equipment(self):
        """O técnico vê apenas equipamentos do próprio setor na lista."""
        self.as_user(self.tech)
        rows = self.send('get', '/api/equipment')
        modelos = {row['model'] for row in rows}
        self.assertIn('Máquina setor próprio', modelos)
        self.assertNotIn('Máquina setor externo', modelos)

    def test_technician_closes_order_in_own_sector(self):
        """O técnico consegue concluir uma OS do próprio setor."""
        order_id = self._open_and_start(self.own_equipment)
        closed = self.send('patch', f'/api/work-orders/{order_id}', {'status': 'CONCLUIDA'})
        self.assertEqual(closed['status'], 'CONCLUIDA')

    def test_technician_cannot_close_order_in_other_sector(self):
        """O técnico recebe 403 ao tentar fechar OS de outro setor."""
        # Admin abre uma OS no setor externo e inicia como técnico — mesmo iniciado, o fechamento é bloqueado.
        order_id = self._open_and_start(self.foreign_equipment)
        self.send('patch', f'/api/work-orders/{order_id}', {'status': 'CONCLUIDA'}, expected=403)
