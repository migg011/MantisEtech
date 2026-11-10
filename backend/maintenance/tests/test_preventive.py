"""Persistência, autorização e isolamento dos checklists e arquivos imprimíveis."""
from django.test import TestCase
from maintenance.authentication import issue_token
from maintenance.models import Equipment, EquipmentType, Line, Sector, User
from maintenance.models import EquipmentPreventive, PreventiveExecution, PreventiveChecklist
from maintenance.services.preventive_schedule import calculate_next_due
from datetime import date
from unittest.mock import patch


class PreventiveTests(TestCase):
    """Verifica as rotas de roteiro, prévia imprimível e permissões, usando dados fictícios no banco de testes."""
    def setUp(self):
        """Cria tipos, máquina, agenda e técnico fictícios; configura o token do cliente e um roteiro de exemplo para cada teste."""
        self.kind = EquipmentType.objects.create(id=90, name='Tipo teste')
        self.other = EquipmentType.objects.create(id=91, name='Outro tipo')
        self.machine = Equipment.objects.create(equipment_type=self.kind, model='<script>alert(1)</script>', serial='SER-123')
        EquipmentPreventive.objects.create(equipment=self.machine, frequency='MENSAL', next_due=date(2026, 10, 26))
        self.tech = User.objects.create_user('TECH', 'test', name='Técnico', role='TECNICO')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.tech)
        self.data = {'equipmentTypeId': self.kind.pk, 'frequency': 'MENSAL', 'items': ['Verificar sensor', '<script>alert(2)</script>']}

    def save(self, data=None):
        """Envia PUT ao catálogo de roteiros com os dados recebidos ou o exemplo padrão e devolve a resposta HTTP para as verificações."""
        return self.client.put('/api/preventive-checklists', data or self.data, content_type='application/json')

    def test_save_reload_and_print_escaped_machine_document(self):
        """Confirma gravação e consulta do roteiro e verifica que o HTML mostra a máquina sem executar textos recebidos como código."""
        self.assertEqual(self.save().status_code, 200)
        response = self.client.get('/api/preventive-checklists', self.data | {'items': ''})
        self.assertEqual(response.json()['items'], self.data['items'])
        response = self.client.get('/api/preventive-checklists/document', self.data | {'equipmentId': self.machine.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertContains(response, 'SER-123')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertContains(response, 'window.print()')

    def test_validation_and_frequency_isolation(self):
        """Rejeita itens e frequências inválidos; confirma que outra frequência não herda itens indevidos e outra máquina não recebe o documento errado."""
        for changes in ({'frequency': 'SEMANAL'}, {'items': []}, {'items': ['']}, {'items': ['x' * 501]}, {'items': [123]}, {'items': ['x'] * 101}):
            self.assertEqual(self.save(self.data | changes).status_code, 400)
        self.assertEqual(self.save().status_code, 200)
        response = self.client.get('/api/preventive-checklists', {'equipmentTypeId': self.kind.pk, 'frequency': 'ANUAL'})
        self.assertEqual(response.json()['items'], [])
        foreign = Equipment.objects.create(equipment_type=self.other)
        response = self.client.get('/api/preventive-checklists/document', self.data | {'equipmentId': foreign.pk})
        self.assertEqual(response.status_code, 404)

    def test_operator_and_anonymous_cannot_access(self):
        """Confirma HTTP 403 para operador e HTTP 401 sem autenticação nas operações de preventiva."""
        sector = Sector.objects.create(code='S', name='Setor')
        line = Line.objects.create(code='L', name='Linha', sector=sector)
        operator = User.objects.create_user('OP', 'test', name='Operador', role='OPERADOR', line=line)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(operator)
        self.assertEqual(self.save().status_code, 403)
        self.assertEqual(self.client.get('/api/preventive-checklists/document', self.data).status_code, 403)
        self.client.defaults.clear()
        self.assertEqual(self.client.get('/api/preventive-checklists', self.data).status_code, 401)


class PreventiveAgendaTests(TestCase):
    """Verifica cadastro de agendas, vencimentos, execução por OS, histórico e regras de calendário."""
    def setUp(self):
        """Fixa a data em 27/10/2026 e prepara máquina e contas fictícias para que os testes não dependam do dia real da execução."""
        frozen = patch('django.utils.timezone.localdate', return_value=date(2026, 10, 27))
        frozen.start()
        self.addCleanup(frozen.stop)
        self.sector = Sector.objects.create(code='PREV', name='Setor preventiva')
        self.kind = EquipmentType.objects.create(id=90, name='Impressora')
        self.admin = User.objects.create_user('ADM', 'test', name='Admin', role='ADMINISTRADOR')
        self.tech = User.objects.create_user('TEC', 'test', name='Técnico', role='TECNICO')
        self.machine = Equipment.objects.create(equipment_type=self.kind, sector=self.sector, name='Impressora 01')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def configure(self, rows, **extra):
        """Envia PATCH com as periodicidades da máquina e eventuais campos adicionais. Retorna a resposta para testar validação e persistência."""
        return self.client.patch(f'/api/equipment/{self.machine.pk}',
            {'preventiveSchedules': rows, **extra}, content_type='application/json')

    def test_equipment_create_edit_name_and_all_frequencies(self):
        """Confere nome e prazos das cinco periodicidades iniciais; valida que editar outro campo sem enviar agendas não apaga as configurações."""
        options = ['QUINZENAL', 'MENSAL', 'TRIMESTRAL', 'SEMESTRAL', 'ANUAL']
        response = self.client.post('/api/equipment', {
            'equipmentTypeId': self.kind.pk, 'sectorId': self.sector.pk, 'name': 'Nova máquina',
            'preventiveSchedules': [{'frequency': value} for value in options]
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['name'], 'Nova máquina')
        schedules = {row['frequency']: row['next_due'] for row in data['preventive_schedules']}
        self.assertEqual(schedules, {'QUINZENAL': '2026-11-11', 'MENSAL': '2026-11-27',
            'TRIMESTRAL': '2027-01-27', 'SEMESTRAL': '2027-04-27', 'ANUAL': '2027-10-27'})
        self.assertEqual(self.configure([{'frequency': 'MENSAL', 'nextDue': '2026-10-20'}], name='Nome editado').status_code, 200)
        # Uma edição de outro campo não apaga a agenda omitida do JSON.
        response = self.client.patch(f'/api/equipment/{self.machine.pk}', {'model': 'Modelo novo'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Nome editado')
        self.assertEqual(response.json()['preventive_schedules'][0]['next_due'], '2026-10-20')
        listing = self.client.get('/api/equipment').json()
        self.assertEqual(next(row for row in listing if row['id'] == self.machine.pk)['name'], 'Nome editado')

    def test_invalid_configuration_does_not_partially_save_machine(self):
        """Envia configurações inválidas e confirma que o nome da máquina e a agenda não são parcialmente gravados."""
        for rows in (None, {}, [{'frequency': 'SEMANAL'}], [{'frequency': []}],
                     [{'frequency': 'ANUAL'}, {'frequency': 'ANUAL'}],
                     [{'frequency': 'MENSAL', 'nextDue': '2026-02-30'}]):
            response = self.configure(rows, name='Não deve salvar')
            self.assertEqual(response.status_code, 400, response.content)
        self.machine.refresh_from_db()
        self.assertEqual(self.machine.name, 'Impressora 01')
        self.assertEqual(EquipmentPreventive.objects.count(), 0)

    def test_status_boundaries_inactive_equipment_and_unconfigured(self):
        """Confere ontem, hoje e amanhã como vencida, vence hoje e em dia; exclui inativos e conta máquinas sem agenda separadamente."""
        self.configure([{'frequency': 'QUINZENAL', 'nextDue': '2026-10-26'},
                        {'frequency': 'MENSAL', 'nextDue': '2026-10-27'},
                        {'frequency': 'SEMESTRAL', 'nextDue': '2026-10-28'}])
        unused = Equipment.objects.create(equipment_type=self.kind, sector=self.sector)
        inactive = Equipment.objects.create(equipment_type=self.kind, sector=self.sector, active=False)
        EquipmentPreventive.objects.create(equipment=inactive, frequency='ANUAL', next_due=date(2020, 1, 1))
        data = self.client.get('/api/preventive-schedules').json()
        self.assertEqual(data['unconfigured_count'], 1)
        self.assertEqual(data['today'], '2026-10-27')
        self.assertEqual([(row['status'], row['days_remaining']) for row in data['schedules']], [('VENCIDA', -1), ('HOJE', 0), ('EM_DIA', 1)])
        self.assertEqual(data['schedules'][0]['equipment_name'], 'Impressora 01')

    def test_completion_reschedules_only_selected_frequency_and_preserves_history(self):
        """Emite e conclui uma OS mensal; confirma que a anual não muda, o histórico não duplica e desativar/reativar preserva os dados anteriores."""
        self.configure([{'frequency': 'MENSAL', 'nextDue': '2026-10-20'}, {'frequency': 'ANUAL', 'nextDue': '2026-12-01'}])
        monthly = self.machine.preventive_schedules.get(frequency='MENSAL')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.tech)
        PreventiveChecklist.objects.create(equipment_type=self.kind, frequency='MENSAL', items=['Verificar sensores'])
        order = self.client.post('/api/preventive-orders', {'scheduleId':monthly.pk, 'expectedDueDate':'2026-10-20', 'plannedDate':'2026-10-20', 'assignedToId':self.tech.pk, 'recurrenceBasis':'EXECUCAO'}, content_type='application/json').json()
        data = {'performedDate': '2026-10-27', 'revision':order['revision'], 'results':[{'status':'REALIZADO'}], 'notes': 'Sensores verificados'}
        response = self.client.post(f"/api/preventive-orders/{order['id']}/complete", data, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['next_due'], '2026-11-27')
        monthly.refresh_from_db()
        self.assertEqual(monthly.last_performed, date(2026, 10, 27))
        self.assertEqual(self.machine.preventive_schedules.get(frequency='ANUAL').next_due, date(2026, 12, 1))
        history = self.client.get('/api/preventive-executions').json()
        self.assertEqual(history[0]['technician_name'], 'Técnico')
        self.assertEqual(history[0]['previous_due'], '2026-10-20')
        self.assertEqual(history[0]['notes'], 'Sensores verificados')
        # Reenvio da mesma conclusão não duplica o histórico.
        self.assertEqual(self.client.post(f"/api/preventive-orders/{order['id']}/complete", data, content_type='application/json').status_code, 409)
        self.assertEqual(PreventiveExecution.objects.count(), 1)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)
        self.assertEqual(self.configure([]).status_code, 200)
        self.assertEqual(self.client.get('/api/preventive-schedules').json()['schedules'], [])
        self.assertEqual(PreventiveExecution.objects.count(), 1)
        self.configure([{'frequency': 'MENSAL'}])
        monthly.refresh_from_db()
        self.assertTrue(monthly.active)
        self.assertEqual(monthly.last_performed, date(2026, 10, 27))
        self.assertEqual(monthly.next_due, date(2026, 11, 27))

    def test_execution_validation_and_calendar_months(self):
        """Confere datas no fim do mês e ano bissexto e rejeita data futura, data inexistente ou observação inválida na conclusão da OS."""
        self.assertEqual(calculate_next_due(date(2026, 1, 31), 'MENSAL'), date(2026, 2, 28))
        self.assertEqual(calculate_next_due(date(2024, 2, 29), 'ANUAL'), date(2025, 2, 28))
        self.assertEqual(calculate_next_due(date(2026, 8, 31), 'SEMESTRAL'), date(2027, 2, 28))
        self.configure([{'frequency': 'MENSAL', 'nextDue': '2026-10-20'}])
        schedule = self.machine.preventive_schedules.get()
        PreventiveChecklist.objects.create(equipment_type=self.kind, frequency='MENSAL', items=['Verificar sensores'])
        order = self.client.post('/api/preventive-orders', {'scheduleId':schedule.pk, 'expectedDueDate':'2026-10-20', 'plannedDate':'2026-10-20', 'assignedToId':self.tech.pk}, content_type='application/json').json()
        for changes in ({'performedDate': '2026-10-28'}, {'performedDate': '2026-02-30'}, {'notes': []}):
            data = {'performedDate': '2026-10-27', 'revision':order['revision'], 'results':[{'status':'REALIZADO'}], **changes}
            self.assertEqual(self.client.post(f"/api/preventive-orders/{order['id']}/complete", data, content_type='application/json').status_code, 400)
        self.assertFalse(PreventiveExecution.objects.exists())

    def test_operator_permissions_and_disabled_frequency_document(self):
        """Bloqueia operador e impressão de frequência não habilitada; confirma a impressão semestral com identificação e prazo, sem criar execução."""
        line = Line.objects.create(code='OP', name='Linha', sector=self.sector)
        operator = User.objects.create_user('OP', 'test', name='Operador', role='OPERADOR', line=line)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(operator)
        for url in ('/api/preventive-schedules', '/api/preventive-executions'):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post('/api/preventive-schedules/1/complete', {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.configure([]).status_code, 403)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.tech)
        data = {'equipmentTypeId': self.kind.pk, 'frequency': 'SEMESTRAL', 'items': ['Verificar sensores']}
        self.assertEqual(self.client.put('/api/preventive-checklists', data, content_type='application/json').status_code, 200)
        params = {**data, 'equipmentId': self.machine.pk}
        self.assertEqual(self.client.get('/api/preventive-checklists/document', params).status_code, 404)
        EquipmentPreventive.objects.create(equipment=self.machine, frequency='SEMESTRAL', next_due=date(2027, 4, 27))
        response = self.client.get('/api/preventive-checklists/document', params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Impressora 01')
        self.assertContains(response, '27/04/2027')
        self.assertFalse(PreventiveExecution.objects.exists())
