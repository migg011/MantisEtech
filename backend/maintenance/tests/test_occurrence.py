"""Testa operador e relógio confiáveis e persistência do relato livre da ocorrência."""
from django.test import TestCase, Client
from django.utils import timezone
from maintenance.models import User, Sector, Line, EquipmentType, Equipment, ProblemType, WorkOrder
from maintenance.authentication import issue_token

class OccurrenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sector=Sector.objects.create(code='REL-SET',name='Setor relato')
        line=Line.objects.create(code='REL-LIN',name='Linha relato',sector=sector)
        kind=EquipmentType.objects.create(id=30000,name='Máquina relato')
        cls.machine=Equipment.objects.create(equipment_type=kind,sector=sector,line=line,position=1,model='REL-01')
        cls.operator=User.objects.create_user('REL-OP','Senha-teste-12345',name='Operador relato',role='OPERADOR',line=line)
        cls.admin=User.objects.create_user('REL-ADM','Senha-teste-12345',name='Administrador relato',role='ADMINISTRADOR')
        cls.problem=ProblemType.objects.create(name='Falha de alimentação',priority='ALTA')

    def setUp(self):
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.operator))

    def open_order(self,extra=None):
        data={'equipmentId':self.machine.pk,'problemTypeId':self.problem.pk,**(extra or {})}
        return self.client.post('/api/orders',data,content_type='application/json')

    def test_operator_clock_and_report_persist(self):
        before=timezone.now()
        response=self.open_order({'occurrenceDescription':'  Parou ao alimentar a placa.\nAlarme no painel.  ', 'openedBy':self.admin.pk,'opened_by':self.admin.pk,'createdAt':'2000-01-01T00:00:00Z','startedAt':'2000-01-01T00:00:00Z'})
        self.assertEqual(response.status_code,201,response.content)
        record=WorkOrder.objects.get(pk=response.json()['id'])
        self.assertEqual(record.opened_by,self.operator)
        self.assertGreaterEqual(record.created_at,before)
        self.assertLessEqual(record.created_at,timezone.now())
        self.assertIsNone(record.started_at)
        self.assertEqual(record.occurrence_description,'Parou ao alimentar a placa.\nAlarme no painel.')
        self.assertEqual(record.problem,'Falha de alimentação')
        query=self.client.get(f'/api/orders/{record.pk}').json()
        self.assertEqual(query['opened_by_name'],'Operador relato')
        self.assertEqual(query['occurrence_description'],record.occurrence_description)
        self.problem.name='Nome atualizado';self.problem.save()
        record.refresh_from_db();self.assertEqual(record.problem,'Falha de alimentação')

    def test_old_order_without_report_remains_valid(self):
        response=self.open_order()
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(response.json()['occurrence_description'],'')

    def test_invalid_report_does_not_create_order(self):
        for report in ('x'*3001, ['text'], {'text':'test'}, None):
            with self.subTest(kind=type(report).__name__):
                before=WorkOrder.objects.count()
                self.assertEqual(self.open_order({'occurrenceDescription':report}).status_code,400)
                self.assertEqual(WorkOrder.objects.count(),before)

    def test_service_preserves_original_report(self):
        response=self.open_order({'occurrenceDescription':'Relato original do operador'})
        record=WorkOrder.objects.get(pk=response.json()['id'])
        record.assigned_to=self.admin;record.started_at=timezone.now();record.status='EM_ANDAMENTO';record.save()
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.admin))
        response=self.client.patch(f'/api/orders/{record.pk}',{'status':'EM_ANDAMENTO','occurrenceDescription':'Trocar relato','rootCause':'Sensor obstruído'},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        record.refresh_from_db()
        self.assertEqual(record.occurrence_description,'Relato original do operador')
        self.assertEqual(record.root_cause,'Sensor obstruído')
