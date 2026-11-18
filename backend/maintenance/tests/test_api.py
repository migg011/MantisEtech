"""Testes de integração HTTP: usam cliente Django e banco de testes para verificar contratos, permissões, validações e persistência."""

import base64
from pathlib import Path

import bcrypt
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from maintenance.api import issue_token_value
from maintenance.models import (UserCode, SectorCode, LineCode, EquipmentTypeCode, EquipmentCode, EquipmentAttachmentCode,
                                EquipmentMovementCode, WorkOrderCode, ProblemTypeCode, SparePartCode, SparePartTechnicalCode,
                                PurchaseRequestCode, PurchaseItemCode, PartRequisitionCode, EquipmentPreventive, PreventiveOrder, PreventiveExecution)
from maintenance.maintenance_services import REQUIRED_TECHNICALCode


class AngularAPITests(TestCase):
    """Agrupa os cenários HTTP e de persistência do contrato consumido pelo Angular."""
    @classmethod
    def setUpTestData(cls):
        """Prepara setor, linhas, máquinas e contas de teste compartilhados pela classe, isolados dos dados reais."""
        cls.sector = SectorCode.objects.create(code='SET-1', name='SMT')
        cls.other_sector = SectorCode.objects.create(code='SET-2', name='Outro setor')
        cls.line = LineCode.objects.create(code='LIN-1', name='Linha 1', sector=cls.sector)
        cls.other_line = LineCode.objects.create(code='LIN-2', name='Linha 2', sector=cls.other_sector)
        cls.kind, _ = EquipmentTypeCode.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        cls.admin = UserCode.objects.create_user('ADM', 'Strong-Test-Password-123', name='Admin', role='ADMINISTRADOR')
        cls.tech = UserCode.objects.create_user('TEC', 'Strong-Test-Password-123', name='Técnico', role='TECNICO', sector=cls.sector)
        cls.operator = UserCode.objects.create_user('OP', 'Strong-Test-Password-123', name='Operador', role='OPERADOR', line=cls.line, sector=cls.sector)
        cls.problem = ProblemTypeCode.objects.create(name='Falha no motor', priority='MEDIA')
        cls.machine = EquipmentCode.objects.create(equipment_type=cls.kind, sector=cls.sector, model='Máquina local', line=cls.line, position=1, length_mm=1500)
        cls.foreign = EquipmentCode.objects.create(equipment_type=cls.kind, sector=cls.other_sector, model='Máquina externa', line=cls.other_line, position=1)
        cls.available = EquipmentCode.objects.create(equipment_type=cls.kind, sector=cls.sector, model='Disponível')

    def setUp(self):
        """Limpa o cache de tentativas e inicia cada teste HTTP com o administrador autenticado."""
        cache.clear()
        self.as_user(self.admin)

    def as_user(self, user):
        """Assina um token de teste para a conta escolhida e o configura no cabeçalho do cliente HTTP."""
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token_value(user)
        if user.role == 'OPERADOR':
            self.send('post', '/api/operator-line', {'lineId': self.line.pk})

    def send(self, method, url, data=None, expected=200):
        """Executa uma chamada JSON e confere status e tipo de resposta antes de devolver o corpo ao teste."""
        response = getattr(self.client, method)(url, data if data is not None else {}, content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content[:1000])
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        return response.json()

    def test_equipment_history_combines_only_completed_work_for_selected_machine(self):
        now = timezone.now()
        order = WorkOrderCode.objects.create(
            equipment=self.machine, opened_by=self.admin, status='CONCLUIDA',
            finished_at=now, problem='Sensor falhou', corrective_action='Sensor substituído',
        )
        WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.admin, problem='OS aberta')
        WorkOrderCode.objects.create(equipment=self.foreign, opened_by=self.admin, status='CONCLUIDA', problem='Outra máquina')
        day = timezone.localdate()
        schedule = EquipmentPreventive.objects.create(equipment=self.machine, frequency='MENSAL', next_due=day)
        preventive = PreventiveOrder.objects.create(
            schedule=schedule, status='CONCLUIDA', expected_due=day, planned_date=day, frequency='MENSAL',
            created_by=self.admin, items=['Limpar filtro', 'Trocar correia'],
            results=[{'status': 'REALIZADO'}, {'status': 'NAO_APLICAVEL'}], performed_date=day,
        )
        for linked in (None, preventive):
            PreventiveExecution.objects.create(
                schedule=schedule, order=linked, performed_date=day, previous_due=day,
                next_due=day, technician=self.tech, notes='Registro de execução',
            )
        part = SparePartCode.objects.create(code='HIST-PART', description='Sensor de reposição', part_number='574337')
        PartRequisitionCode.objects.create(work_order=order, equipment=self.machine, spare_part=part,
                                          quantity=2, requester=self.tech)
        rows = self.send('get', f'/api/equipment/{self.machine.pk}/history')
        self.assertEqual(rows[0]['requestedParts'][0]['partNumber'], '574337')
        self.assertEqual(rows[0]['requestedParts'][0]['quantity'], '2.000')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['number'], f'#{order.pk}')
        self.assertEqual(rows[0]['reason'], 'Sensor falhou')
        self.assertEqual(rows[0]['services'], ['Sensor substituído'])
        self.assertEqual(next(row for row in rows if row['number'] == preventive.number)['services'], ['Limpar filtro'])
        self.assertEqual(next(row for row in rows if row['number'] is None)['performedDate'], day.isoformat())
        self.as_user(self.tech)
        self.send('get', f'/api/equipment/{self.foreign.pk}/history', expected=404)

    def test_equipment_pressure_accepts_scalar_and_range(self):
        data = {'equipmentTypeId': self.kind.pk, 'sectorId': self.sector.pk, 'pneumaticPressureBar': '4 - 8'}
        equipment = self.send('post', '/api/equipment', data, expected=201)
        url = f"/api/equipment/{equipment['id']}"
        self.assertEqual(EquipmentCode.objects.get(pk=equipment['id']).pneumatic_pressure_bar, '4 - 8')
        self.assertEqual(self.send('patch', url, {'pneumaticPressureBar': 6})['pneumatic_pressure_bar'], '6')
        self.assertEqual(self.send('patch', url, {'pneumaticPressureBar': '4,5 a 8 bar'})['pneumatic_pressure_bar'], '4.5 - 8')
        self.send('patch', url, {'pneumaticPressureBar': '8 - 4'}, expected=400)
        self.assertEqual(EquipmentCode.objects.get(pk=equipment['id']).pneumatic_pressure_bar, '4.5 - 8')
        self.assertIsNone(self.send('patch', url, {'pneumaticPressureBar': None})['pneumatic_pressure_bar'])

    def test_equipment_frequency_accepts_nominal_values_and_ranges(self):
        equipment = self.send('post', '/api/equipment', {
            'equipmentTypeId': self.kind.pk, 'sectorId': self.sector.pk, 'frequencyHz': '50 / 60 Hz',
        }, expected=201)
        self.assertEqual(equipment['frequency_hz'], '50/60')
        url = f"/api/equipment/{equipment['id']}"
        self.assertEqual(self.send('patch', url, {'name': 'Nome atualizado'})['frequency_hz'], '50/60')
        self.assertEqual(self.send('patch', url, {'frequencyHz': '50 a 60'})['frequency_hz'], '50 - 60')
        self.send('patch', url, {'frequencyHz': '60 - 50'}, expected=400)
        self.assertEqual(EquipmentCode.objects.get(pk=equipment['id']).frequency_hz, '50 - 60')
        self.assertEqual(self.send('patch', url, {'frequencyHz': 60})['frequency_hz'], '60')
        self.assertIsNone(self.send('patch', url, {'frequencyHz': None})['frequency_hz'])

    def create_part(self):
        """Cria uma peça pela própria API para reutilizar nos cenários de compra e compatibilidade."""
        return self.send('post', '/api/spare-parts', {
            'description': 'Sensor de posição', 'partNumber': '=UNSAFE()', 'unit': 'UN',
            'minimumStock': 2, 'maximumStock': 5, 'reorderPoint': 1,
            'equipmentIds': [self.machine.pk]}, expected=201)

    def test_preventive_catalog_purchase_has_no_machine_compatibility(self):
        """A lista geral permite comprar várias peças e não cria vínculo com o equipamento consultado na preventiva."""
        self.as_user(self.tech)
        first = SparePartCode.objects.create(code='PREV-01', description='Filtro geral', unit='UN')
        second = SparePartCode.objects.create(code='PREV-02', description='Correia geral', unit='UN')
        catalog = self.send('get', '/api/spare-purchase/parts')
        self.assertTrue({first.pk, second.pk}.issubset({row['id'] for row in catalog}))
        purchase = self.send('post', '/api/spare-purchase/requests', {
            'purchaseType':'NACIONAL', 'managerId':self.admin.pk, 'priority':'MEDIA',
            'justification':'Materiais para as preventivas programadas',
            'items':[{'sparePartId':first.pk, 'quantity':2, 'itemNote':'Troca de filtro'},
                     {'sparePartId':second.pk, 'quantity':3}]
        }, expected=201)
        # Cabeçalho e catálogo são independentes da máquina; só a compra recebe os itens selecionados.
        self.assertIsNone(purchase['equipment_id'])
        self.assertIsNone(purchase['work_order_id'])
        self.assertEqual(purchase['status'], 'RASCUNHO')
        detail = self.send('get', f"/api/spare-purchase/requests/{purchase['id']}")
        self.assertEqual(len(detail['items']), 2)
        self.assertEqual(detail['items'][0]['item_note'], 'Troca de filtro')
        self.assertEqual(first.compatibility.count(), 0)
        self.assertEqual(second.compatibility.count(), 0)

    def create_purchase(self, part, purchase_type='NACIONAL'):
        """Cria uma compra como técnico, com itens para validar o fluxo de rascunho e aprovação."""
        self.as_user(self.tech)
        return self.send('post', '/api/spare-purchase/requests', {
            'purchaseType': purchase_type, 'managerId': self.admin.pk, 'priority': 'ALTA',
            'justification': 'Reposição de sensor da linha',
            'items': [{'sparePartId': part['id'], 'quantity': 2}, {'sparePartId': part['id'], 'quantity': 3}]}, expected=201)

    def test_part_requisition_is_direct_and_keeps_serial_without_purchase(self):
        """Solicitação direta preserva serial e não cria compra; valida quantidade e perfis."""
        part = self.create_part()
        self.machine.serial = 'SERIAL-OS-123'
        self.machine.save()
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator,
                                         problem='Falha de sensor', priority='MEDIA')
        url = f'/api/orders/{order.pk}/part-requisitions'
        self.as_user(self.tech)
        item = self.send('post', url, {'sparePartId': part['id'], 'quantity': 2,
                         'equipmentId': self.foreign.pk, 'equipment_serial': 'FALSO'}, expected=201)
        self.assertEqual(item['status'], 'SOLICITADA')
        self.assertEqual(item['equipment_id'], self.machine.pk)
        self.assertEqual(item['equipment_serial'], 'SERIAL-OS-123')
        self.assertFalse(PurchaseRequestCode.objects.exists())
        self.machine.serial = 'SERIAL-NOVO'
        self.machine.save()
        self.assertEqual(self.send('get', url)[0]['equipment_serial'], 'SERIAL-OS-123')
        for quantity in [0, -1, 'NaN', 'Infinity', '1.0001']:
            self.send('post', url, {'sparePartId': part['id'], 'quantity': quantity}, expected=400)
        self.assertEqual(len(self.send('get', url)), 1)
        self.as_user(self.operator)
        self.send('get', url, expected=403)
        self.send('post', url, {'sparePartId': part['id'], 'quantity': 1}, expected=403)

    def test_line_pendencies_preserve_origin_and_resolution_history(self):
        """Pendência preserva linha/serial de origem e audita a resolução mesmo após fechamento da OS."""
        self.machine.serial = 'SERIAL-PENDENCIA'
        self.machine.save()
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Sensor')
        url = f'/api/orders/{order.pk}/pendencies'
        self.as_user(self.tech)
        item = self.send('post', url, {'description': 'Revisar sensor na próxima parada', 'priority': 'ALTA',
            'lineId': self.other_line.pk, 'equipmentId': self.foreign.pk}, expected=201)
        self.assertEqual(item['line_id'], self.line.pk)
        self.assertEqual(item['equipment_id'], self.machine.pk)
        self.assertEqual(item['equipment_serial'], 'SERIAL-PENDENCIA')
        self.assertEqual(item['created_by_name'], self.tech.name)
        self.assertEqual(item['status'], 'PENDENTE')
        self.assertEqual(self.send('get', url)[0]['id'], item['id'])
        self.assertEqual(len(self.send('get', f'/api/line-pendencies?lineId={self.line.pk}&status=PENDENTE')), 1)
        self.assertEqual(self.send('get', f'/api/line-pendencies?lineId={self.other_line.pk}'), [])
        # Fechar a OS ou mover a máquina não deve apagar ou transferir a pendência.
        order.status = 'CONCLUIDA'
        order.save()
        self.machine.line = None
        self.machine.position = None
        self.machine.serial = 'NOVO-SERIAL'
        self.machine.save()
        pending = self.send('get', '/api/line-pendencies')[0]
        self.assertEqual(pending['line_id'], self.line.pk)
        self.assertEqual(pending['equipment_serial'], 'SERIAL-PENDENCIA')
        resolve_url = f"/api/line-pendencies/{item['id']}"
        self.send('patch', resolve_url, {'status': 'RESOLVIDA', 'resolution': ''}, expected=400)
        resolved = self.send('patch', resolve_url, {'status': 'RESOLVIDA', 'resolution': 'Sensor revisado e testado'})
        self.assertEqual(resolved['resolved_by_name'], self.tech.name)
        self.assertIsNotNone(resolved['resolved_at'])
        self.assertEqual(self.send('get', '/api/line-pendencies?status=PENDENTE'), [])
        self.assertEqual(len(self.send('get', '/api/line-pendencies?status=RESOLVIDA')), 1)
        self.send('patch', resolve_url, {'status': 'RESOLVIDA', 'resolution': 'Outra solução'}, expected=409)

    def test_line_pendency_validation_and_permissions(self):
        """Valida descrição, prioridade, vínculo com linha e bloqueio do operador no módulo de pendências."""
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Sensor')
        url = f'/api/orders/{order.pk}/pendencies'
        self.as_user(self.operator)
        self.send('get', '/api/line-pendencies', expected=403)
        self.send('post', url, {'description': 'Revisar sensor'}, expected=403)
        self.send('get', url, expected=403)
        self.as_user(self.tech)
        for data in [{'description': 'x'}, {'description': 'Revisar sensor', 'priority': 'INVALIDA'},
                     {'description': 'Revisar sensor', 'priority': []}]:
            self.send('post', url, data, expected=400)
        self.machine.line = None
        self.machine.position = None
        self.machine.save()
        self.send('post', url, {'description': 'Revisar sensor'}, expected=409)
        self.assertEqual(self.send('get', '/api/line-pendencies'), [])

    def test_line_status_board_includes_all_active_orders_and_scopes_operator(self):
        """Painel retorna mais de 200 ocorrências ativas e limita o operador à sua linha."""
        WorkOrderCode.objects.bulk_create([WorkOrderCode(equipment=self.machine, opened_by=self.operator,
            problem='Aguardando atendimento') for _ in range(205)])
        foreign = WorkOrderCode.objects.create(equipment=self.foreign, opened_by=self.admin, problem='Outra linha')
        board = self.send('get', '/api/line-status')
        self.assertEqual(len(board['orders']), 206)
        self.assertEqual(len(board['lines']), 2)
        self.assertIn('server_now', board)
        self.assertEqual(board['orders'][0]['opened_by_name'], self.operator.name)
        self.as_user(self.operator)
        board = self.send('get', '/api/line-status')
        self.assertEqual([line['id'] for line in board['lines']], [self.line.pk])
        self.assertEqual(len(board['orders']), 205)
        self.assertNotIn(foreign.pk, [order['id'] for order in board['orders']])

    def test_line_status_board_includes_clear_lines_and_completed_history(self):
        """Painel mantém linhas sem ocorrências e limita o histórico às 100 concluídas mais recentes da consulta."""
        self.assertEqual(self.send('get', '/api/line-status')['orders'], [])
        self.assertEqual(len(self.send('get', '/api/line-status')['lines']), 2)
        WorkOrderCode.objects.bulk_create([WorkOrderCode(equipment=self.machine, opened_by=self.operator,
            problem='Concluida', status='CONCLUIDA') for _ in range(105)])
        history = self.send('get', '/api/line-status')['orders']
        self.assertEqual(len(history), 100)
        self.assertTrue(all(order['status'] == 'CONCLUIDA' for order in history))

    def test_backend_has_no_frontend_or_page_routes(self):
        """Django entrega API JSON sem servir páginas ou os arquivos do Angular."""
        root = Path(settings.BASE_DIR)
        for folder in ('maintenance/templates', 'maintenance/static', 'staticfiles'):
            self.assertFalse((root / folder).exists(), folder)
        self.assertEqual(settings.TEMPLATES, [])
        for path in ('/', '/entrar/', '/totem/', '/setores/', '/static/maintenance/app.css', '/api/unknown'):
            self.send('get', path, expected=404)
        self.assertEqual(self.send('get', '/api/health')['status'], 'ok')

    def test_totem_indicators_include_all_orders_and_respect_operator_line(self):
        # Mais de 200 OS concluídas não podem esconder uma ocorrência antiga no Totem.
        """Indicadores de máquina usam todas as OS e respeitam o escopo de linha do operador."""
        WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Falha na linha', status='ABERTA')
        working = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Em atendimento', status='EM_ANDAMENTO')
        WorkOrderCode.objects.bulk_create([
            WorkOrderCode(equipment=self.machine, opened_by=self.operator, problem='Concluída', status='CONCLUIDA')
            for _ in range(201)
        ])
        EquipmentAttachmentCode.objects.create(equipment=self.machine, kind='PHOTO', filename='machine.png',
                                           mime_type='image/png', size_bytes=3, content=b'png', uploaded_by=self.admin)
        self.as_user(self.operator)
        rows = self.send('get', '/api/equipment')
        self.assertEqual([row['id'] for row in rows], [self.machine.pk])
        self.assertEqual(rows[0]['open_order_count'], 2)
        self.assertEqual(rows[0]['in_progress_order_count'], 1)
        self.assertTrue(rows[0]['has_photo'])
        working.status = 'CONCLUIDA'
        working.save(update_fields=['status'])
        row = self.send('get', '/api/equipment')[0]
        self.assertEqual(row['open_order_count'], 1)
        self.assertEqual(row['in_progress_order_count'], 0)

    def test_login_contract_and_protected_requests(self):
        """Login fornece token/usuário e os demais endpoints exigem autenticação válida."""
        self.client.defaults.clear()
        self.send('get', '/api/equipment', expected=401)
        result = self.send('post', '/api/auth/login', {'registration': 'OP', 'password': 'Strong-Test-Password-123'})
        self.assertIsNone(result['user']['lineId'])
        self.assertNotIn('password', result['user'])
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + result['token']
        self.assertEqual(self.send('get', '/api/me')['id'], self.operator.pk)
        self.client.defaults['HTTP_AUTHORIZATION'] += 'tampered'
        self.send('get', '/api/me', expected=401)

    def test_legacy_bcrypt_login_upgrades_hash(self):
        """Login válido converte o hash de senha antigo para o padrão Django."""
        legacy = bcrypt.hashpw(b'legacy-secure-password', bcrypt.gensalt(rounds=4)).decode()
        UserCode.objects.filter(pk=self.admin.pk).update(password=legacy)
        result = self.send('post', '/api/auth/login', {'registration': 'ADM', 'password': 'legacy-secure-password'})
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.password.startswith('$2'))
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + result['token']
        self.send('get', '/api/me')

    def test_problem_catalog_permissions_filter_and_operator_priority(self):
        """Catálogo filtra tipos e aplica prioridade obrigatória ao operador."""
        self.as_user(self.tech)
        specific = self.send('post', '/api/problem-types', {
            'name': 'Travamento da máquina', 'equipmentTypeId': self.kind.pk, 'priority': 'ALTA'
        }, expected=201)
        other_kind = EquipmentTypeCode.objects.create(pk=999, name='TIPO ESPECÍFICO TESTE')
        other = self.send('post', '/api/problem-types', {
            'name': 'Problema de outro tipo', 'equipmentTypeId': other_kind.pk
        }, expected=201)
        self.as_user(self.operator)
        allowed = self.send('get', f'/api/problem-types?equipmentTypeId={self.kind.pk}')
        self.assertIn(self.problem.pk, [item['id'] for item in allowed])
        self.assertIn(specific['id'], [item['id'] for item in allowed])
        self.assertNotIn(other['id'], [item['id'] for item in allowed])
        self.send('get', '/api/problem-types?includeInactive=true', expected=403)
        self.send('post', '/api/problem-types', {'name': 'Problema indevido'}, expected=403)
        self.send('patch', f"/api/problem-types/{specific['id']}", {'name': 'Editado indevidamente'}, expected=403)
        self.send('delete', f"/api/problem-types/{specific['id']}", expected=403)
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'problem': 'Texto livre não permitido'}, expected=400)
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'problemTypeId': other['id']}, expected=400)
        order = self.send('post', '/api/orders', {
            'equipmentId': self.machine.pk, 'problemTypeId': specific['id'],
            'problem': 'Tentativa de alterar a descrição', 'priority': 'BAIXA'
        }, expected=201)
        self.assertEqual(order['priority'], 'ALTA')
        self.assertEqual(order['problem'], 'Travamento da máquina')
        self.assertEqual(order['problem_type_id'], specific['id'])

    def test_problem_catalog_preserves_order_description_and_rejects_inactive(self):
        """OS mantém a descrição original do problema e não aceita opção desativada."""
        order = self.send('post', '/api/orders', {
            'equipmentId': self.machine.pk, 'problemTypeId': self.problem.pk
        }, expected=201)
        self.send('patch', f'/api/problem-types/{self.problem.pk}', {'name': 'Novo nome do problema'})
        self.assertEqual(WorkOrderCode.objects.get(pk=order['id']).problem, 'Falha no motor')
        self.send('delete', f'/api/problem-types/{self.problem.pk}')
        self.assertNotIn(self.problem.pk, [item['id'] for item in self.send('get', '/api/problem-types')])
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'problemTypeId': self.problem.pk}, expected=400)
        self.assertIsNotNone(WorkOrderCode.objects.get(pk=order['id']).problem_type_id)
        self.send('patch', f'/api/problem-types/{self.problem.pk}', {'active': True})
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'problemTypeId': self.problem.pk}, expected=201)
        self.send('post', '/api/problem-types', {'name': 'novo nome do problema'}, expected=400)

    def test_login_throttling(self):
        """Limite de tentativas de login impede repetição ilimitada de senhas."""
        for _ in range(10):
            self.send('post', '/api/auth/login', {'registration': 'unknown', 'password': 'wrong'}, expected=401)
        self.send('post', '/api/auth/login', {'registration': 'ADM', 'password': 'wrong'}, expected=429)

    def test_token_expiration_password_reset_and_disabled_user(self):
        """Sessão expira, troca de senha invalida token anterior e conta desativada perde acesso."""
        with override_settings(API_TOKEN_MAX_AGE=-1):
            self.send('get', '/api/me', expected=401)
        self.send('patch', f'/api/users/{self.tech.pk}/password', {'password': 'Other-Strong-Password-123'})
        self.as_user(self.tech)  # old in-memory password hash
        self.send('get', '/api/me', expected=401)
        self.tech.refresh_from_db()
        self.as_user(self.tech)
        self.send('get', '/api/me')
        UserCode.objects.filter(pk=self.tech.pk).update(active=False)
        self.send('get', '/api/me', expected=401)

    def test_cookie_alone_never_authenticates_or_changes_state(self):
        """Cookie de sessão isolado não substitui o Bearer exigido pela API."""
        secured = Client(enforce_csrf_checks=True)
        secured.cookies['sessionid'] = 'old-session'
        self.assertEqual(secured.post('/api/sectors', {'name': 'Teste'}, content_type='application/json').status_code, 401)
        secured.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token_value(self.tech)
        self.assertEqual(secured.post('/api/sectors', {'name': 'Teste'}, content_type='application/json').status_code, 201)

    def test_every_angular_list_endpoint_returns_json(self):
        """As consultas utilizadas pelo Angular respeitam o contrato JSON."""
        for path in ('/api/sectors', '/api/lines', '/api/equipment-types', '/api/equipment',
                     '/api/users', '/api/orders', '/api/spare-parts', '/api/spare-purchase/managers',
                     '/api/spare-purchase/parts', '/api/spare-purchase/requests'):
            with self.subTest(path=path):
                self.assertIsInstance(self.send('get', path), list)
        self.assertNotIn('password', str(self.send('get', '/api/users')))

    def test_sector_line_equipment_and_partial_updates(self):
        """Cadastros relacionados e PATCH preservam campos que não vieram na atualização."""
        sector = self.send('post', '/api/sectors', {'name': 'Montagem', 'description': 'Setor novo'}, expected=201)
        sector = self.send('patch', f"/api/sectors/{sector['id']}", {'name': 'Montagem final'})
        self.assertEqual(sector['description'], 'Setor novo')
        line = self.send('post', '/api/lines', {'name': 'Linha nova', 'sectorId': sector['id']}, expected=201)
        item = self.send('post', '/api/equipment', {'equipmentTypeId': self.kind.pk, 'sectorId': sector['id'],
                         'model': 'Modelo novo', 'lengthMm': 1250, 'manufacturingDateText': '03/2020'}, expected=201)
        updated = self.send('patch', f"/api/equipment/{item['id']}", {'model': 'Revisado'})
        self.assertEqual(updated['length_mm'], '1250.00')
        self.assertEqual(updated['sector_id'], sector['id'])
        self.send('post', f"/api/lines/{line['id']}/equipment", {'equipmentId': item['id'], 'position': 1}, expected=201)
        summary = next(x for x in self.send('get', '/api/lines') if x['id'] == line['id'])
        self.assertEqual(summary['equipment_count'], 1)
        self.assertEqual(float(summary['length_mm']), 1250)
        self.send('delete', f"/api/sectors/{sector['id']}", expected=409)
        self.send('delete', f"/api/equipment/{item['id']}", expected=409)
        self.send('delete', f"/api/lines/{line['id']}/equipment/{item['id']}")
        self.send('delete', f"/api/equipment/{item['id']}")

    def test_equipment_validation_and_duplicate_errors(self):
        """Valida campos técnicos e devolve erros coerentes para duplicidades."""
        payload = {'equipmentTypeId': self.kind.pk, 'sectorId': self.sector.pk,
                   'lengthMm': -1, 'manufacturingDateText': '31/02/2026'}
        result = self.send('post', '/api/equipment', payload, expected=400)
        self.assertIn('length_mm', result['details'])
        self.assertIn('manufacturing_date_text', result['details'])
        self.send('get', '/api/equipment?sectorId=invalid', expected=400)
        self.send('post', '/api/lines', {'name': 'Linha', 'sectorId': self.other_sector.pk}, expected=201)
        self.send('post', '/api/users', {'name': 'Duplicado', 'registration': 'ADM', 'role': 'TECNICO',
                                      'password': 'Strong-Test-Password-123'}, expected=400)

    def test_operator_scope_and_technician_permissions(self):
        """Operador fica restrito à linha; técnico tem apenas as permissões previstas."""
        self.as_user(self.operator)
        items = self.send('get', f'/api/equipment?lineId={self.other_line.pk}&available=true')
        self.assertEqual([x['id'] for x in items], [self.machine.pk])
        self.assertEqual([x['id'] for x in self.send('get', '/api/lines')], [self.line.pk])
        for path in ('/api/users', '/api/sectors', '/api/spare-parts'):
            self.send('get', path, expected=403)
        self.send('post', '/api/orders', {'equipmentId': self.foreign.pk, 'priority': 'ALTA', 'problemTypeId': self.problem.pk}, expected=400)
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'priority': 'ALTA', 'problemTypeId': self.problem.pk}, expected=201)
        self.assertEqual(len(self.send('get', '/api/orders')), 1)
        self.as_user(self.tech)
        self.send('get', '/api/users', expected=403)
        self.assertEqual([line['id'] for line in self.send('get', '/api/lines')], [self.line.pk])
        self.assertNotIn(self.foreign.pk, [equipment['id'] for equipment in self.send('get', '/api/equipment')])
        foreign_order = WorkOrderCode.objects.create(equipment=self.foreign, opened_by=self.admin, problem='Sensor')
        foreign_url = f'/api/orders/{foreign_order.pk}'
        self.send('get', foreign_url, expected=404)
        self.send('post', foreign_url + '/start', {'registration': 'TEC', 'password': 'Strong-Test-Password-123'}, expected=404)
        self.send('patch', foreign_url, {'status': 'CONCLUIDA'}, expected=404)
        self.send('patch', f'/api/sectors/{self.sector.pk}', {'name': 'Editado'}, expected=403)
        self.send('post', f'/api/sectors/{self.sector.pk}', {'name': 'Bypass'}, expected=405)
        self.send('patch', f'/api/equipment/{self.machine.pk}', {'model': 'Editado'}, expected=403)

    def test_operator_with_inactive_line_has_no_equipment(self):
        """Linha inativa não disponibiliza máquinas ao operador."""
        self.as_user(self.operator)
        LineCode.objects.filter(pk=self.line.pk).update(active=False)
        self.assertEqual(self.send('get', '/api/equipment'), [])
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'priority': 'ALTA', 'problemTypeId': self.problem.pk}, expected=403)

    def test_operator_chooses_and_leaves_line_with_same_login(self):
        token = issue_token_value(self.operator)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + token
        path = '/api/operator-line'
        self.assertIsNone(self.send('get', path)['lineId'])
        local_line = LineCode.objects.create(code='LIN-3', name='Outra linha local', sector=self.sector)
        self.assertCountEqual([line['id'] for line in self.send('get', path)['lines']], [self.line.pk, local_line.pk])
        self.send('post', path, {'lineId': self.other_line.pk}, expected=404)
        self.assertEqual(self.send('get', '/api/equipment'), [])
        self.assertEqual(self.send('post', path, {'lineId': self.line.pk})['lineId'], self.line.pk)
        self.assertEqual([row['id'] for row in self.send('get', '/api/equipment')], [self.machine.pk])
        self.send('post', path, {'lineId': local_line.pk}, expected=409)
        second = Client(HTTP_AUTHORIZATION='Bearer ' + issue_token_value(self.operator))
        self.assertIsNone(second.get(path).json()['lineId'])
        self.assertIsNone(self.send('delete', path)['lineId'])
        self.assertEqual(self.send('get', '/api/equipment'), [])
        self.assertEqual(self.send('get', '/api/orders'), [])
        self.send('get', f'/api/equipment/{self.machine.pk}/attachments', expected=404)
        self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'problemTypeId': self.problem.pk}, expected=403)
        self.send('post', path, {'lineId': self.other_line.pk}, expected=404)
        self.assertEqual(self.send('post', path, {'lineId': local_line.pk})['lineId'], local_line.pk)
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.line_id, self.line.pk)

    def test_user_management_self_protection_and_account_without_line(self):
        """Administração protege a própria conta e cadastra operadores sem linha fixa."""
        user = self.send('post', '/api/users', {'name': 'Operador novo', 'registration': 'OP2', 'role': 'OPERADOR',
                        'password': 'Strong-Test-Password-123', 'sectorId': self.sector.pk}, expected=201)
        self.assertEqual(user['sector_id'], self.sector.pk)
        self.assertIsNone(user['line_id'])
        self.send('patch', f"/api/users/{user['id']}", {'name': 'Nome atualizado'})
        self.assertTrue(UserCode.objects.get(pk=user['id']).check_password('Strong-Test-Password-123'))
        self.send('patch', f'/api/users/{self.admin.pk}', {'role': 'TECNICO'}, expected=400)
        self.send('patch', f'/api/users/{self.admin.pk}/status', {'active': False}, expected=403)
        self.send('patch', f"/api/users/{user['id']}/status", {'active': False})
        LineCode.objects.filter(pk=self.line.pk).update(active=False)
        self.send('patch', f"/api/users/{user['id']}/status", {'active': True})
        self.send('patch', f"/api/users/{user['id']}/password", {'password': 'short'}, expected=400)

    def test_allocation_validation_history_and_dismantle(self):
        """Montagem valida setor/posição, grava histórico e devolve máquinas ao desmontar."""
        self.as_user(self.tech)
        self.send('post', f'/api/lines/{self.line.pk}/equipment', {'equipmentId': self.available.pk, 'position': 1}, expected=400)
        self.send('post', f'/api/lines/{self.other_line.pk}/equipment', {'equipmentId': self.available.pk, 'position': 2}, expected=404)
        self.send('post', f'/api/lines/{self.line.pk}/equipment', {'equipmentId': self.available.pk, 'position': 2}, expected=201)
        self.assertEqual(EquipmentMovementCode.objects.count(), 1)
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Falha no motor')
        self.assertEqual(self.send('post', f'/api/lines/{self.line.pk}/dismantle')['released'], 2)
        self.assertEqual(EquipmentMovementCode.objects.count(), 3)
        self.assertTrue(WorkOrderCode.objects.filter(pk=order.pk).exists())
        self.assertEqual(len(self.send('get', f'/api/equipment/{self.available.pk}/movements')), 2)

    def test_database_rejects_line_without_position(self):
        """Restrição do banco impede equipamento alocado sem uma posição válida."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            EquipmentCode.objects.create(equipment_type=self.kind, sector=self.sector, line=self.line)

    def test_attachments_signature_replacement_download_and_scope(self):
        """Upload valida assinatura/tamanho, substitui a categoria e protege o download."""
        self.as_user(self.tech)
        url = f'/api/equipment/{self.machine.pk}/attachments/PHOTO'
        data = {'filename': 'photo.png', 'mimeType': 'image/png', 'base64': base64.b64encode(b'fake').decode()}
        self.send('put', url, data, expected=400)
        png = b'\x89PNG\r\n\x1a\nimage'
        data['base64'] = base64.b64encode(png).decode()
        self.send('put', url, data)
        data['filename'] = 'replaced.png'
        self.send('put', url, data)
        self.assertEqual(EquipmentAttachmentCode.objects.count(), 1)
        result = self.send('get', f'/api/equipment/{self.machine.pk}/attachments')
        self.assertNotIn('content', result[0])
        self.assertEqual(result[0]['filename'], 'replaced.png')
        self.as_user(self.operator)
        response = self.client.get(url + '/download')
        self.assertEqual(b''.join(response.streaming_content), png)
        self.send('get', f'/api/equipment/{self.foreign.pk}/attachments/PHOTO/download', expected=404)
        self.send('put', url, data, expected=403)
        self.as_user(self.tech)
        data['base64'] = base64.b64encode(png + b'x' * (3 * 1024 * 1024)).decode()
        self.send('put', url, data, expected=400)

    def test_new_equipment_copies_first_available_photo_by_type_and_name(self):
        data = {'equipmentTypeId': self.kind.pk, 'sectorId': self.sector.pk, 'name': 'NXT'}
        first = self.send('post', '/api/equipment', data, expected=201)
        self.assertFalse(first['has_photo'])
        reference = self.send('post', '/api/equipment', data, expected=201)
        png = b'\x89PNG\r\n\x1a\nimage'
        photo = {'filename': 'nxt.png', 'mimeType': 'image/png', 'base64': base64.b64encode(png).decode()}
        source_url = f"/api/equipment/{reference['id']}/attachments"
        self.send('put', source_url + '/PHOTO', photo)
        self.send('put', source_url + '/MANUAL', {
            'filename': 'manual.pdf', 'mimeType': 'application/pdf',
            'base64': base64.b64encode(b'%PDF-1.7 example').decode(),
        })

        match = {**data, 'name': ' nxt ', 'sectorId': self.other_sector.pk}
        lookup = self.send('get', f'/api/equipment-reference?equipmentTypeId={self.kind.pk}&name=nxt')
        self.assertEqual(lookup['photoFilename'], 'nxt.png')
        inherited = self.send('post', '/api/equipment', match, expected=201)
        self.assertTrue(inherited['has_photo'])
        inherited_url = f"/api/equipment/{inherited['id']}/attachments"
        self.assertEqual([row['kind'] for row in self.send('get', inherited_url)], ['PHOTO'])
        response = self.client.get(inherited_url + '/PHOTO/view')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), png)

        self.send('put', inherited_url + '/PHOTO', {**photo, 'filename': 'outra.png'})
        self.assertEqual(EquipmentAttachmentCode.objects.get(equipment_id=reference['id'], kind='PHOTO').filename, 'nxt.png')
        other_type = EquipmentTypeCode.objects.create(id=99, name='Tipo diferente para teste da foto')
        for changes in ({'name': 'NPM'}, {'equipmentTypeId': other_type.pk}, {'useReferencePhoto': False}):
            with self.subTest(changes=changes):
                created = self.send('post', '/api/equipment', {**data, **changes}, expected=201)
                self.assertFalse(created['has_photo'])


    def test_equipment_documents_open_inline_and_keep_separate_pdfs(self):
        base = f'/api/equipment/{self.machine.pk}/attachments'
        pdf = b'%PDF-1.7 example'
        upload = {'filename': 'manual.pdf', 'mimeType': 'application/pdf',
                  'base64': base64.b64encode(pdf).decode()}
        self.send('put', base + '/MANUAL', upload)
        self.send('put', base + '/ELECTRICAL', {**upload, 'filename': 'esquema.pdf'})
        self.assertEqual({item['kind'] for item in self.send('get', base)}, {'MANUAL', 'ELECTRICAL'})
        invalid_pdf = {**upload, 'base64': base64.b64encode(b'fake').decode()}
        self.send('put', base + '/ELECTRICAL', invalid_pdf, expected=400)

        self.as_user(self.tech)
        response = self.client.get(base + '/ELECTRICAL/view')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline;'))
        self.assertEqual(b''.join(response.streaming_content), pdf)
        response = self.client.get(base + '/MANUAL/download')
        self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(b''.join(response.streaming_content), pdf)

        self.assertEqual(Client().get(base + '/ELECTRICAL/view').status_code, 401)
        self.as_user(self.operator)
        self.send('get', f'/api/equipment/{self.foreign.pk}/attachments/ELECTRICAL/view', expected=404)

    def test_equipment_manual_multipart_accepts_25_mb_and_rejects_larger_files(self):
        url = f'/api/equipment/{self.machine.pk}/attachments/MANUAL'
        limit = 25 * 1024 * 1024
        content = b'%PDF-1.7'.ljust(limit, b' ')
        response = self.client.post(url, {'file': SimpleUploadedFile('manual.pdf', content, 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['size_bytes'], limit)

        response = self.client.post(url, {'file': SimpleUploadedFile('excesso.pdf', content + b' ', 'application/pdf')})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('25 MB', response.json()['error'])
        attachment = EquipmentAttachmentCode.objects.defer('content').get(equipment=self.machine, kind='MANUAL')
        self.assertEqual((attachment.filename, attachment.size_bytes), ('manual.pdf', limit))

    def test_photo_survives_edit_and_stays_scoped_to_equipment(self):
        """Reabrir/editar cadastro preserva foto; substituir uma máquina não troca a foto de outra."""
        url = f'/api/equipment/{self.machine.pk}/attachments/PHOTO'
        png = b'\x89PNG\r\n\x1a\nimage'
        self.send('put', url, {'filename': 'original.png', 'mimeType': 'image/png',
                              'base64': base64.b64encode(png).decode()})
        EquipmentAttachmentCode.objects.create(equipment=self.available, kind='PHOTO', filename='outra.png',
                                        content=png + b'outra', mime_type='image/png', size_bytes=len(png) + 5, uploaded_by=self.admin)
        edited = self.send('patch', f'/api/equipment/{self.machine.pk}', {'name': 'Nome atualizado'})
        self.assertTrue(edited['has_photo'])
        reopened = self.send('get', f'/api/equipment/{self.machine.pk}/attachments')
        self.assertEqual(reopened[0]['filename'], 'original.png')
        self.send('put', url, {'filename': 'nova.png', 'mimeType': 'image/png',
                              'base64': base64.b64encode(png + b'nova').decode()})
        self.assertEqual(bytes(EquipmentAttachmentCode.objects.get(equipment=self.available, kind='PHOTO').content), png + b'outra')
        # Cliente novo simula recarregar a tela, sem depender de estado do formulário.
        cliente = Client(HTTP_AUTHORIZATION='Bearer ' + issue_token_value(self.admin))
        response_value = cliente.get(url + '/download')
        self.assertEqual(b''.join(response_value.streaming_content), png + b'nova')
        self.assertIn('no-store', response_value['Cache-Control'])

    def test_transfer_equipment_preserves_identity_attachments_and_orders(self):
        """Transferência muda apenas o setor e gera histórico com motivo e autoria."""
        maquina = self.available
        EquipmentAttachmentCode.objects.create(equipment=maquina, kind='PHOTO', filename='foto.png',
            content=b'conteudo preservado', mime_type='image/png', size_bytes=19, uploaded_by=self.admin)
        order_value = WorkOrderCode.objects.create(equipment=maquina, opened_by=self.admin, problem='Histórico preservado')
        response_value = self.send('post', f'/api/equipment/{maquina.pk}/transfer', {
            'originSectorId': self.sector.pk, 'destinationSectorId': self.other_sector.pk, 'reason': 'Remanejamento para teste'})
        maquina.refresh_from_db()
        self.assertEqual(maquina.sector_id, self.other_sector.pk)
        self.assertEqual(response_value['id'], maquina.pk)
        self.assertTrue(response_value['has_photo'])
        self.assertIsNone(maquina.line_id)
        self.assertEqual(bytes(EquipmentAttachmentCode.objects.get(equipment=maquina).content), b'conteudo preservado')
        order_value.refresh_from_db()
        self.assertEqual(order_value.equipment_id, maquina.pk)
        evento = maquina.movements.get(action='TRANSFERENCIA')
        self.assertEqual((evento.from_sector_id, evento.to_sector_id, evento.performed_by_id), (self.sector.pk, self.other_sector.pk, self.admin.pk))
        self.assertEqual(evento.reason, 'Remanejamento para teste')
        history_value = self.send('get', f'/api/equipment/{maquina.pk}/movements')
        self.assertEqual(history_value[0]['from_sector_name'], self.sector.name)
        self.assertEqual(history_value[0]['to_sector_name'], self.other_sector.name)
        source_value = self.send('get', f'/api/equipment?sectorId={self.sector.pk}')
        destino = self.send('get', f'/api/equipment?sectorId={self.other_sector.pk}')
        self.assertNotIn(maquina.pk, [item['id'] for item in source_value])
        self.assertIn(maquina.pk, [item['id'] for item in destino])

    def test_transfer_rejects_allocated_same_inactive_and_stale_sector(self):
        """Valida alocação, destino ativo, motivo e setor de origem sem gerar histórico indevido."""
        data_value = {'originSectorId': self.sector.pk, 'destinationSectorId': self.other_sector.pk, 'reason': 'Transferência de teste'}
        self.send('post', f'/api/equipment/{self.machine.pk}/transfer', data_value, expected=400)
        url = f'/api/equipment/{self.available.pk}/transfer'
        for alteracoes in ({'destinationSectorId':self.sector.pk}, {'originSectorId':self.other_sector.pk}, {'reason':''}, {'reason':'x'*501}, {'destinationSectorId':None}):
            self.send('post', url, {**data_value, **alteracoes}, expected=400)
        self.other_sector.active = False
        self.other_sector.save(update_fields=['active'])
        self.send('post', url, data_value, expected=404)
        self.available.refresh_from_db()
        self.assertEqual(self.available.sector_id, self.sector.pk)
        self.assertFalse(self.available.movements.exists())

    def test_transfer_requires_administrator(self):
        """Operador e técnico não alteram a propriedade do equipamento entre setores."""
        for user_value in (self.tech, self.operator):
            self.as_user(user_value)
            self.send('post', f'/api/equipment/{self.available.pk}/transfer', {
                'originSectorId':self.sector.pk, 'destinationSectorId':self.other_sector.pk, 'reason':'Teste de autorização'}, expected=403)

    def test_edit_line_preserves_allocation_and_orders(self):
        """Renomear linha preserva código, setor, alocações e vínculos de OS."""
        order_value = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.admin, problem='Falha')
        codigo = self.line.code
        self.as_user(self.tech)
        response_value = self.send('patch', f'/api/lines/{self.line.pk}', {
            'name':'  Linha SMT piloto  ', 'description':'Nova descrição', 'sectorId':self.other_sector.pk})
        self.line.refresh_from_db()
        self.machine.refresh_from_db()
        order_value.refresh_from_db()
        self.assertEqual(response_value['name'], 'Linha SMT piloto')
        self.assertEqual(self.line.description, 'Nova descrição')
        self.assertEqual((self.line.code, self.line.sector_id), (codigo, self.sector.pk))
        self.assertEqual((self.machine.line_id, self.machine.position), (self.line.pk, 1))
        self.assertEqual(order_value.equipment_id, self.machine.pk)
        self.send('patch', f'/api/lines/{self.line.pk}', {'description':''})
        self.line.refresh_from_db()
        self.assertEqual(self.line.name, 'Linha SMT piloto')
        self.assertEqual(self.line.description, '')

    def test_edit_line_rejects_operator_and_invalid_names(self):
        url = f'/api/lines/{self.line.pk}'
        for name_value in (' ', 'x', 'x'*500):
            self.send('patch', url, {'name':name_value}, expected=400)
        self.as_user(self.operator)
        self.send('patch', url, {'name':'Sem permissão'}, expected=403)
        self.line.refresh_from_db()
        self.assertEqual(self.line.name, 'Linha 1')

    def test_spare_part_cost_currencies_persist_without_conversion(self):
        part_value = self.send('post', '/api/spare-parts', {'description':'Holder com moedas',
            'averageCost':'53.00', 'averageCostCurrency':'USD', 'lastCost':'350.00', 'lastCostCurrency':'BRL'}, expected=201)
        self.assertEqual(part_value['average_cost_currency'], 'USD')
        self.assertEqual(part_value['last_cost_currency'], 'BRL')
        url = f"/api/spare-parts/{part_value['id']}"
        self.send('patch', url, {'averageCostCurrency':'BRL'})
        item_value = SparePartCode.objects.get(pk=part_value['id'])
        self.assertEqual(str(item_value.average_cost), '53.00')
        self.assertEqual(item_value.average_cost_currency, 'BRL')
        self.send('patch', url, {'lastCostCurrency':'XXX'}, expected=400)
        self.send('post', '/api/spare-parts', {'description':'Custo sem moeda', 'averageCost':10}, expected=400)
        self.send('post', '/api/spare-parts', {'description':'Custo zero sem moeda', 'lastCost':0}, expected=400)

    def test_legacy_cost_currency_remains_unknown(self):
        part_value = SparePartCode.objects.create(code='LEG-MOEDA', description='Peça antiga', average_cost=53)
        self.send('patch', f'/api/spare-parts/{part_value.pk}', {'description':'Descrição atualizada'})
        part_value.refresh_from_db()
        self.assertEqual(part_value.average_cost_currency, '')
        self.assertEqual(str(part_value.average_cost), '53.00')

    def test_spare_part_photo_create_edit_replace_and_access(self):
        foto = {'filename':'holder.png', 'mimeType':'image/png', 'base64':base64.b64encode(b'\x89PNG\r\n\x1a\nfoto inicial').decode()}
        part_value = self.send('post', '/api/spare-parts', {'description':'Holder com foto', 'photo':foto}, expected=201)
        self.assertEqual(part_value['photo_filename'], 'holder.png')
        self.assertNotIn('photo_data', part_value)
        url = f"/api/spare-parts/{part_value['id']}"
        self.send('patch', url, {'description':'Nome atualizado'})
        item_value = SparePartCode.objects.get(pk=part_value['id'])
        self.assertEqual(bytes(item_value.photo_data), b'\x89PNG\r\n\x1a\nfoto inicial')
        foto.update(filename='nova.png', base64=base64.b64encode(b'\x89PNG\r\n\x1a\nfoto nova').decode())
        self.send('patch', url, {'photo':foto})
        self.as_user(self.tech)
        response_value = self.client.get(url + '/photo')
        self.assertEqual(response_value.status_code, 200)
        self.assertEqual(b''.join(response_value.streaming_content), b'\x89PNG\r\n\x1a\nfoto nova')
        self.assertEqual(response_value['Content-Type'], 'image/png')
        self.assertIn('no-store', response_value['Cache-Control'])
        self.as_user(self.operator)
        self.send('get', url + '/photo', expected=403)
        self.assertEqual(Client().get(url + '/photo').status_code, 401)

    def test_invalid_spare_photo_rolls_back_and_preserves_previous_photo(self):
        part_value = SparePartCode.objects.create(code='FOTO-VALIDA', description='Peça original', photo_filename='original.png', photo_mime='image/png', photo_data=b'foto preservada')
        invalida = {'filename':'falsa.png', 'mimeType':'image/png', 'base64':base64.b64encode(b'arquivo invalido').decode()}
        total = SparePartCode.objects.count()
        self.send('post', '/api/spare-parts', {'description':'Não gravar', 'photo':invalida}, expected=400)
        self.assertEqual(SparePartCode.objects.count(), total)
        self.send('patch', f'/api/spare-parts/{part_value.pk}', {'description':'Não alterar', 'photo':invalida}, expected=400)
        part_value.refresh_from_db()
        self.assertEqual((part_value.description, part_value.photo_filename, bytes(part_value.photo_data)), ('Peça original', 'original.png', b'foto preservada'))
        self.send('patch', f'/api/spare-parts/{part_value.pk}', {'photo':None}, expected=400)
        semfoto = self.create_part()
        self.send('get', f"/api/spare-parts/{semfoto['id']}/photo", expected=404)

    def test_order_timestamps_and_partial_fields(self):
        """Atendimento preserva início e campos anteriores e registra o fechamento."""
        self.as_user(self.operator)
        order = self.send('post', '/api/orders', {'equipmentId': self.machine.pk, 'priority': 'MEDIA', 'problemTypeId': self.problem.pk}, expected=201)
        self.as_user(self.tech)
        url = f"/api/orders/{order['id']}"
        self.send('post', url + '/start', {'registration': 'TEC', 'password': 'Strong-Test-Password-123'})
        running = self.send('patch', url, {'status': 'EM_ANDAMENTO', 'rootCause': 'Motor'})
        for blank in ('', '   ', None):
            error = self.send('patch', url, {'status': 'CONCLUIDA', 'correctiveAction': 'Troca do motor',
                                             'preventiveAction': blank}, expected=400)
            self.assertIn('preventive_action', error['details'])
        self.send('patch', url, {'status': 'CONCLUIDA'}, expected=400)
        self.assertEqual(self.send('get', url)['status'], 'EM_ANDAMENTO')
        self.assertIsNone(self.send('get', url)['finished_at'])
        finished = self.send('patch', url, {'status': 'CONCLUIDA', 'correctiveAction': 'Troca do motor',
                                            'preventiveAction': 'Inspecionar o motor mensalmente'})
        self.assertIsNotNone(running['started_at'])
        self.assertEqual(finished['started_at'], running['started_at'])
        self.assertIsNotNone(finished['finished_at'])
        self.assertEqual(finished['root_cause'], 'Motor')

    def test_authenticated_attendance_and_line_downtime(self):
        """Início exige credenciais, mantém o responsável e fixa o total de parada no fechamento."""
        from datetime import timedelta
        from django.utils import timezone
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator,
            problem='Linha parada', created_at=timezone.now() - timedelta(minutes=5))
        url = f'/api/orders/{order.pk}'
        self.as_user(self.operator)
        self.send('post', url + '/start', {'registration': 'TEC', 'password': 'Strong-Test-Password-123'}, expected=403)
        self.as_user(self.tech)
        self.send('patch', url, {'status': 'CONCLUIDA'}, expected=409)
        self.send('post', url + '/start', {'registration': 'TEC', 'password': 'errada'}, expected=403)
        order.refresh_from_db()
        self.assertIsNone(order.started_at)
        started = self.send('post', url + '/start', {'registration': 'TEC', 'password': 'Strong-Test-Password-123'})
        again = self.send('post', url + '/start', {'registration': 'TEC', 'password': 'Strong-Test-Password-123'})
        self.assertEqual(started['started_at'], again['started_at'])
        self.assertEqual(started['assigned_to_name'], self.tech.name)
        self.assertEqual(started['opened_by_name'], self.operator.name)
        self.assertGreaterEqual(started['downtime_minutes'], 5)
        self.as_user(self.admin)
        self.send('post', url + '/start', {'registration': 'ADM', 'password': 'Strong-Test-Password-123'}, expected=409)
        self.send('patch', url, {'status': 'CONCLUIDA'}, expected=409)
        self.as_user(self.tech)
        finished = self.send('patch', url, {'status': 'CONCLUIDA', 'correctiveAction': 'Substituição',
                                            'rootCause': 'Motor danificado', 'preventiveAction': 'Inspeção mensal'})
        self.assertGreaterEqual(finished['downtime_seconds'], 300)
        self.send('patch', url, {'status': 'ABERTA'}, expected=409)
        self.assertEqual(self.send('get', url)['downtime_seconds'], finished['downtime_seconds'])
        self.as_user(self.operator)
        rows = self.send('get', f'/api/orders?lineId={self.line.pk}')
        self.assertEqual(rows[0]['id'], order.pk)
        self.assertEqual(rows[0]['finished_at'], finished['finished_at'])
        self.assertEqual(self.send('get', f'/api/orders?lineId={self.other_line.pk}'), [])

    def test_spare_parts_stock_compatibility_and_permissions(self):
        """Cadastro de peças valida referências de estoque, compatibilidade e permissões."""
        part = self.create_part()
        self.assertEqual(part['equipment_ids'], [self.machine.pk])
        self.send('patch', f"/api/spare-parts/{part['id']}", {'maximumStock': 1}, expected=400)
        self.send('patch', f"/api/spare-parts/{part['id']}", {'description': 'Sensor revisado'})
        self.assertEqual(SparePartCode.objects.get(pk=part['id']).compatibility.count(), 1)
        self.as_user(self.tech)
        self.send('get', '/api/spare-parts')
        self.send('delete', f"/api/spare-parts/{part['id']}", expected=403)
        self.as_user(self.admin)
        self.send('delete', f"/api/spare-parts/{part['id']}")
        self.assertEqual(self.send('get', '/api/spare-parts'), [])

    def test_order_parts_lookup_is_active_scoped_and_staff_only(self):
        """Consulta da OS mostra peças ativas e compatibilidade apenas para os perfis autorizados."""
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Falha na máquina')
        part = self.create_part()
        other = SparePartCode.objects.create(code='OTHER-PART', description='Peça sem vínculo')
        SparePartCode.objects.create(code='INACTIVE-PART', description='Peça desativada', active=False)
        self.as_user(self.tech)
        basis = f'/api/orders/{order.pk}/spare-parts'
        rows = self.send('get', basis)
        self.assertEqual({row['id'] for row in rows}, {part['id'], other.pk})
        self.assertTrue(next(row for row in rows if row['id'] == part['id'])['compatible'])
        self.assertEqual([row['id'] for row in self.send('get', basis + '?compatibleOnly=true')], [part['id']])
        self.assertEqual([row['id'] for row in self.send('get', basis + '?q=UNSAFE')], [part['id']])
        self.as_user(self.operator)
        self.send('get', basis, expected=403)
        self.send('get', f'/api/orders/{order.pk}/purchase-requests', expected=403)

    def test_order_purchase_records_machine_serial_and_preserves_it_in_csv(self):
        """Compra vinculada congela o serial e o preserva na edição e na exportação."""
        EquipmentCode.objects.filter(pk=self.machine.pk).update(serial='SN-ORIGINAL-001')
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Troca do sensor')
        part = self.create_part()
        self.as_user(self.tech)
        purchase = self.send('post', f'/api/orders/{order.pk}/purchase-requests', {
            'purchaseType': 'NACIONAL', 'managerId': self.admin.pk, 'priority': 'ALTA',
            'justification': 'Substituição do sensor desta máquina', 'equipmentSerial': 'SERIAL-FORJADO',
            'items': [{'sparePartId': part['id'], 'quantity': 2}]
        }, expected=201)
        self.assertEqual(purchase['work_order_id'], order.pk)
        self.assertEqual(purchase['equipment_id'], self.machine.pk)
        self.assertEqual(purchase['equipment_serial'], 'SN-ORIGINAL-001')
        EquipmentCode.objects.filter(pk=self.machine.pk).update(serial='SN-ATUALIZADO-002')
        basis = f"/api/spare-purchase/requests/{purchase['id']}"
        updated = self.send('patch', basis, {'items': [{'sparePartId': part['id'], 'quantity': 3}]})
        self.assertEqual(updated['equipment_serial'], 'SN-ORIGINAL-001')
        linked = self.send('get', f'/api/orders/{order.pk}/purchase-requests')
        self.assertEqual(linked[0]['equipment_serial'], 'SN-ORIGINAL-001')
        self.assertEqual(self.send('get', f'/api/orders/{order.pk}')['serial'], 'SN-ATUALIZADO-002')
        self.send('put', f"/api/spare-purchase/parts/{part['id']}/technical", {key: 'Dados técnicos' for key in REQUIRED_TECHNICALCode})
        self.send('post', basis + '/submit')
        csv = self.client.get(basis + '/export.csv').content.decode()
        self.assertIn('Serial da máquina', csv)
        self.assertIn('SN-ORIGINAL-001', csv)
        self.assertNotIn('SN-ATUALIZADO-002', csv)

    def test_order_purchase_rejects_wrong_machine_and_invalid_items(self):
        """Compra rejeita máquina divergente e itens inválidos sem gravação parcial."""
        order = WorkOrderCode.objects.create(equipment=self.machine, opened_by=self.operator, problem='Troca de peça')
        part = self.create_part()
        payload = {'purchaseType': 'NACIONAL', 'managerId': self.admin.pk, 'priority': 'MEDIA',
                   'justification': 'Reposição para a máquina da OS', 'items': [{'sparePartId': part['id'], 'quantity': 1}]}
        endpoint = f'/api/orders/{order.pk}/purchase-requests'
        self.as_user(self.tech)
        self.send('post', endpoint, {**payload, 'equipmentId': self.foreign.pk}, expected=400)
        self.send('post', endpoint, {**payload, 'workOrderId': 999999}, expected=400)
        self.send('post', endpoint, {**payload, 'items': [{'sparePartId': part['id'], 'quantity': -1}]}, expected=400)
        self.assertEqual(PurchaseRequestCode.objects.filter(work_order=order).count(), 0)
        purchase = self.send('post', '/api/spare-purchase/requests', {**payload, 'workOrderId': order.pk}, expected=201)
        self.assertEqual(purchase['equipment_id'], self.machine.pk)
        self.as_user(self.operator)
        self.send('post', endpoint, payload, expected=403)

    def test_purchase_multi_item_snapshot_approval_and_csv(self):
        """Compra aceita vários itens e congela ficha técnica antes da aprovação e do CSV."""
        part = self.create_part()
        purchase = self.create_purchase(part, 'IMPORTACAO')
        basis = f"/api/spare-purchase/requests/{purchase['id']}"
        self.send('post', basis + '/submit', expected=409)
        technical = f"/api/spare-purchase/parts/{part['id']}"
        profile = {key: 'Dados técnicos' for key in REQUIRED_TECHNICALCode}
        profile.update(ncm='12345678', pli_description='Sensor óptico')
        self.send('put', technical + '/technical', profile)
        self.send('post', basis + '/submit', expected=409)
        self.send('post', technical + '/validate', expected=403)
        self.as_user(self.admin)
        self.send('post', technical + '/validate')
        self.as_user(self.tech)
        self.send('post', basis + '/submit')
        self.send('put', technical + '/technical', {'description_en': 'Alteração posterior'})
        profile = SparePartTechnicalCode.objects.get(spare_part_id=part['id'])
        self.assertEqual(profile.fiscal_status, 'PENDENTE')
        self.assertIsNone(profile.fiscal_validated_by)
        detail = self.send('get', basis)
        self.assertEqual(len(detail['items']), 2)
        self.assertEqual(detail['items'][0]['technical_snapshot']['description_en'], 'Dados técnicos')
        self.send('post', basis + '/decision', {'decision': 'APROVADA'}, expected=403)
        self.as_user(self.admin)
        self.send('post', basis + '/decision', {'decision': 'APROVADA', 'comment': 'Comprar'})
        self.assertEqual(PurchaseRequestCode.objects.get(pk=purchase['id']).status, 'APROVADA')
        response = self.client.get(basis + '/export.csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=UNSAFE()", response.content.decode())
        self.assertIn('Dados técnicos', response.content.decode())
        self.assertNotIn('Alteração posterior', response.content.decode())

    def test_purchase_edit_return_scope_and_atomic_invalid_items(self):
        """Edição/devolução respeitam autor e estado e não deixam itens parciais inválidos."""
        part = self.create_part()
        purchase = self.create_purchase(part)
        basis = f"/api/spare-purchase/requests/{purchase['id']}"
        self.send('patch', basis, {'items': [{'sparePartId': part['id'], 'quantity': 7}]})
        self.assertEqual(PurchaseItemCode.objects.get(request_id=purchase['id']).quantity, 7)
        self.send('patch', basis, {'items': [{'sparePartId': part['id'], 'quantity': -1}]}, expected=400)
        self.assertEqual(PurchaseItemCode.objects.get(request_id=purchase['id']).quantity, 7)
        self.as_user(self.operator)
        self.send('get', basis, expected=404)
        foreign_order = WorkOrderCode.objects.create(equipment=self.foreign, opened_by=self.admin, problem='Falha externa')
        self.send('post', '/api/spare-purchase/requests', {'purchaseType': 'NACIONAL', 'managerId': self.admin.pk,
                  'workOrderId': foreign_order.pk, 'priority': 'MEDIA', 'justification': 'Reposição da máquina',
                  'items': [{'sparePartId': part['id'], 'quantity': 1}]}, expected=400)

    def test_invalid_json_methods_and_missing_resources_are_json(self):
        """Erros de JSON, método e recurso ausente seguem o contrato de erro JSON."""
        response = self.client.post('/api/sectors', '{broken', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.send('post', '/api/sectors', [], expected=400)
        self.send('patch', '/api/sectors/999999', {'name': 'Não existe'}, expected=404)
        self.send('get', f'/api/lines/{self.line.pk}/dismantle', expected=405)
        self.send('get', f'/api/users/{self.admin.pk}/password', expected=405)
        self.send('post', f'/api/equipment/{self.machine.pk}', {'model': 'Bypass'}, expected=405)

    def test_part_sheet_search_and_permissions(self):
        """A ficha usa o mesmo ID em todas as telas e busca pelos dados que o usuário conhece."""
        part = SparePartCode.objects.create(code='SP-INTERNO', part_number='N610113699AA', description='Suporte de bicos', manufacturer='Panasonic', photo_filename='peca.png', photo_data=b'binario')
        SparePartTechnicalCode.objects.create(spare_part=part, description_pt='Suporte NPM H16')
        inactive = SparePartCode.objects.create(code='INATIVO', description='Desativada', active=False)
        self.as_user(self.tech)
        for query in ('N610113699AA', 'Suporte', 'Panasonic'):
            rows = self.send('get', '/api/spare-parts?q=' + query)
            self.assertEqual([row['id'] for row in rows], [part.pk])
        self.assertEqual(self.send('get', '/api/spare-parts?q=inexistente'), [])
        sheet = self.send('get', f'/api/spare-parts/{part.pk}/details')
        self.assertEqual(sheet['part_number'], 'N610113699AA')
        self.assertEqual(sheet['technical']['description_pt'], 'Suporte NPM H16')
        self.assertEqual(sheet['photo_filename'], 'peca.png')
        self.assertNotIn('photo_data', sheet)
        self.send('get', f'/api/spare-parts/{inactive.pk}/details', expected=404)
        self.send('get', '/api/spare-parts/999999/details', expected=404)
        self.as_user(self.operator)
        self.send('get', f'/api/spare-parts/{part.pk}/details', expected=403)

    def test_purchase_export_preserves_part_identification(self):
        """O CSV conserva PN, descrição e fabricante registrados no envio para aprovação."""
        part = self.create_part()
        SparePartCode.objects.filter(pk=part['id']).update(part_number='PN-ORIGINAL', description='Descrição original', manufacturer='Fabricante original')
        purchase = self.create_purchase(part)
        profile = {key: 'Dados técnicos' for key in REQUIRED_TECHNICALCode}
        self.send('put', f"/api/spare-purchase/parts/{part['id']}/technical", profile)
        basis = f"/api/spare-purchase/requests/{purchase['id']}"
        self.send('post', basis + '/submit')
        SparePartCode.objects.filter(pk=part['id']).update(part_number='PN-ALTERADO', description='Descrição alterada', manufacturer='Fabricante alterado')
        response = self.client.get(basis + '/export.csv')
        self.assertEqual(response.status_code, 200)
        csv = response.content.decode('utf-8-sig')
        for original in ('PN-ORIGINAL', 'Descrição original', 'Fabricante original'):
            self.assertIn(original, csv)
        self.assertNotIn('PN-ALTERADO', csv)
