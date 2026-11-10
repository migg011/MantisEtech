"""Fluxo completo da OS preventiva e preservação do roteiro emitido."""
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from maintenance.authentication import issue_token
from maintenance.models import User, Sector, Line, EquipmentType, Equipment, EquipmentPreventive, PreventiveChecklist, PreventiveOrder, PreventiveExecution


class PreventiveOrderTests(TestCase):
    """Verifica o ciclo da OS: roteiro específico, emissão, salvamento parcial, conclusão, cancelamento, impressão e autorização."""
    def setUp(self):
        """Fixa a data e prepara máquina com agenda bimestral, roteiro padrão e usuários fictícios, todos isolados do banco real."""
        frozen = patch('django.utils.timezone.localdate', return_value=date(2026, 10, 27))
        frozen.start()
        self.addCleanup(frozen.stop)
        self.kind = EquipmentType.objects.create(id=90, name='Impressora')
        self.sector = Sector.objects.create(code='OS-P', name='Setor')
        self.machine = Equipment.objects.create(equipment_type=self.kind, sector=self.sector, name='Máquina original', serial='SER-01')
        self.schedule = EquipmentPreventive.objects.create(equipment=self.machine, frequency='BIMESTRAL', next_due=date(2026, 10, 20))
        self.recipe = PreventiveChecklist.objects.create(equipment_type=self.kind, frequency='BIMESTRAL', items=['Verificar sensor', 'Lubrificar eixo'])
        self.tech = User.objects.create_user('TEC-OS', 'test', name='Técnico', role='TECNICO')
        self.admin = User.objects.create_user('ADM-OS', 'test', name='Admin', role='ADMINISTRADOR')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.tech)

    def issue(self, expected=201, **extra):
        """Emite uma OS de exemplo com campos substituíveis, confere o status HTTP esperado e devolve seu JSON para os demais passos do teste."""
        response = self.client.post('/api/preventive-orders', {'scheduleId':self.schedule.pk,
            'expectedDueDate':'2026-10-20', 'plannedDate':'2026-10-21', 'plannedTime':'09:00', 'assignedToId':self.tech.pk, **extra}, content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()

    def results(self, order, **extra):
        """Monta resultados realizados para os itens da OS, com a revisão atual e data de exemplo; permite substituir campos para testar situações inválidas."""
        return {'revision':order['revision'], 'performedDate':'2026-10-27',
                'results':[{'status':'REALIZADO','notes':''} for _ in order['items']], **extra}

    def test_snapshot_specific_recipe_and_immutable_reprint(self):
        """Confirma a prioridade do roteiro específico e que renomear a máquina ou editar atividades não muda a OS emitida e sua reimpressão."""
        payload={'equipmentTypeId':self.kind.pk,'equipmentId':self.machine.pk,'frequency':'BIMESTRAL','items':['Tarefa exclusiva']}
        response=self.client.put('/api/preventive-checklists',payload,content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['source'],'EQUIPAMENTO')
        order=self.issue()
        self.assertEqual(order['items'],['Tarefa exclusiva'])
        self.assertEqual(order['status'],'ABERTA')
        self.assertTrue(order['number'].startswith('PREV-'))
        self.machine.name='Nome alterado'
        self.machine.save()
        self.client.put('/api/preventive-checklists',payload | {'items':['Outra tarefa']},content_type='application/json')
        response=self.client.get(f"/api/preventive-orders/{order['id']}/document")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Máquina original')
        self.assertContains(response,'Tarefa exclusiva')
        self.assertNotContains(response,'Outra tarefa')
        self.assertNotContains(response,'Nome alterado')
        self.assertFalse(PreventiveExecution.objects.exists())
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.next_due,date(2026,10,20))
        self.client.put('/api/preventive-checklists',payload | {'useTypeDefault':True},content_type='application/json')
        response=self.client.get('/api/preventive-checklists',payload)
        self.assertEqual(response.json()['items'],self.recipe.items)

    def test_draft_does_not_close_and_revision_prevents_lost_updates(self):
        """Salva parcialmente sem renovar a agenda, rejeita revisão antiga e impede concluir enquanto houver atividade não realizada."""
        order=self.issue()
        payload=self.results(order,results=[{'status':'REALIZADO'}, {'status':'NAO_REALIZADO','notes':'Peça aguardando reposição'}])
        url=f"/api/preventive-orders/{order['id']}"
        response=self.client.patch(url,payload,content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['revision'],2)
        self.assertEqual(self.client.patch(url,payload,content_type='application/json').status_code,409)
        payload['revision']=2
        self.assertEqual(self.client.post(url+'/complete',payload,content_type='application/json').status_code,400)
        self.assertFalse(PreventiveExecution.objects.exists())
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.next_due,date(2026,10,20))

    def test_complete_keeps_calendar_and_records_parts_and_executor(self):
        """Conclui pela regra de calendário e confere prazo, executor, peças, justificativas e impressão segura; rejeita edição ou nova conclusão da mesma OS."""
        order=self.issue()
        parts=[{'description':'Sensor <script>alert(1)</script>','partNumber':'P-123','quantity':2}]
        payload=self.results(order,parts=parts,notes='Conferência final',results=[{'status':'REALIZADO'},{'status':'NA','notes':'Sem lubrificação neste modelo'}])
        url=f"/api/preventive-orders/{order['id']}"
        response=self.client.post(url+'/complete',payload,content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['next_due'],'2026-12-20')
        self.assertEqual(response.json()['executor_name'],'Técnico')
        execution=PreventiveExecution.objects.get()
        self.assertEqual(execution.order_id,order['id'])
        self.assertEqual(execution.technician,self.tech)
        self.assertEqual(self.client.post(url+'/complete',payload,content_type='application/json').status_code,409)
        self.assertEqual(self.client.patch(url,payload,content_type='application/json').status_code,409)
        doc=self.client.get(url+'/document')
        self.assertContains(doc,'P-123')
        self.assertContains(doc,'&lt;script&gt;')
        self.assertNotContains(doc,'<script>')
        self.assertContains(doc,'Sem lubrificação neste modelo')
        self.assertContains(doc,'Assinatura do executor')

    def test_execution_based_recurrence_and_validation(self):
        """Testa a regra pela data executada e rejeita data futura, quantidade inválida, resultados incompletos e conclusão sem atividade realizada."""
        order=self.issue(recurrenceBasis='EXECUCAO')
        url=f"/api/preventive-orders/{order['id']}/complete"
        for change in ({'performedDate':'2026-10-28'}, {'results':[]}, {'results':[{'status':'NA','notes':''}]*2},
                       {'parts':[{'description':'Peça','quantity':0}]}, {'results':[{'status':'NA','notes':'Não aplicável'}]*2}):
            self.assertEqual(self.client.post(url,self.results(order,**change),content_type='application/json').status_code,400)
        response=self.client.post(url,self.results(order),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['next_due'],'2026-12-27')

    def test_duplicate_cancel_and_reissue_preserve_due(self):
        """Impede uma segunda OS aberta, cancela com justificativa e permite nova emissão, mantendo o prazo e sem criar execução."""
        order=self.issue()
        self.issue(expected=409)
        response=self.client.post(f"/api/preventive-orders/{order['id']}/cancel",{'revision':1,'reason':'Reprogramação da manutenção'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'CANCELADA')
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.next_due,date(2026,10,20))
        self.assertFalse(PreventiveExecution.objects.exists())
        reissued=self.issue()
        self.assertNotEqual(reissued['number'],order['number'])

    def test_cannot_change_schedule_while_order_open_and_no_legacy_completion(self):
        """Impede desmarcar ou mudar o vencimento com OS aberta e confirma que a rota antiga não permite concluir sem registrar atividades."""
        self.issue()
        self.client.defaults['HTTP_AUTHORIZATION']='Bearer '+issue_token(self.admin)
        for selections in ([],[{'frequency':'BIMESTRAL','nextDue':'2026-11-01'}]):
            response=self.client.patch(f'/api/equipment/{self.machine.pk}',{'preventiveSchedules':selections},content_type='application/json')
            self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(self.client.post(f'/api/preventive-schedules/{self.schedule.pk}/complete',{},content_type='application/json').status_code,409)

    def test_permissions_and_issue_validation(self):
        """Rejeita previsão, regra e referência de vencimento inválidas; bloqueia operador nas consultas, impressão e conclusão."""
        self.issue(expected=400,plannedTime='99:00')
        self.issue(expected=409,expectedDueDate='2026-10-21')
        self.issue(expected=400,recurrenceBasis='INVALIDA')
        self.assertFalse(PreventiveOrder.objects.exists())
        order=self.issue()
        line=Line.objects.create(code='OP-P',name='Linha',sector=self.sector)
        operator=User.objects.create_user('OP-P','test',name='Operador',role='OPERADOR',line=line)
        self.client.defaults['HTTP_AUTHORIZATION']='Bearer '+issue_token(operator)
        for path in ('/api/preventive-orders','/api/preventive-orders/technicians',f"/api/preventive-orders/{order['id']}",f"/api/preventive-orders/{order['id']}/document"):
            self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.client.post(f"/api/preventive-orders/{order['id']}/complete",self.results(order),content_type='application/json').status_code,403)
