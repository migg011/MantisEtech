"""Testa operador e relógio confiáveis e persistência do relato livre da ocorrência."""
from django.test import TestCase, Client
from django.utils import timezone
from maintenance.models import UserCode, SectorCode, LineCode, EquipmentTypeCode, EquipmentCode, ProblemTypeCode, WorkOrderCode
from maintenance.api import issue_token_value

class OcorrenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setor=SectorCode.objects.create(code='REL-SET',name='Setor relato')
        row_value=LineCode.objects.create(code='REL-LIN',name='Linha relato',sector=setor)
        tipo=EquipmentTypeCode.objects.create(id=30000,name='Máquina relato')
        cls.maquina=EquipmentCode.objects.create(equipment_type=tipo,sector=setor,line=row_value,position=1,model='REL-01')
        cls.operador=UserCode.objects.create_user('REL-OP','Senha-teste-12345',name='Operador relato',role='OPERADOR',line=row_value,sector=setor)
        cls.admin=UserCode.objects.create_user('REL-ADM','Senha-teste-12345',name='Administrador relato',role='ADMINISTRADOR')
        cls.problema=ProblemTypeCode.objects.create(name='Falha de alimentação',priority='ALTA')

    def setUp(self):
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.operador))
        response = self.client.post('/api/operator-line', {'lineId': self.maquina.line_id}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def abrir(self,extra=None):
        data_value={'equipmentId':self.maquina.pk,'problemTypeId':self.problema.pk,**(extra or {})}
        return self.client.post('/api/orders',data_value,content_type='application/json')

    def test_operador_relogio_e_relato_persistem(self):
        antes=timezone.now()
        response_value=self.abrir({'occurrenceDescription':'  Parou ao alimentar a placa.\nAlarme no painel.  ', 'openedBy':self.admin.pk,'opened_by':self.admin.pk,'createdAt':'2000-01-01T00:00:00Z','startedAt':'2000-01-01T00:00:00Z'})
        self.assertEqual(response_value.status_code,201,response_value.content)
        item_value=WorkOrderCode.objects.get(pk=response_value.json()['id'])
        self.assertEqual(item_value.opened_by,self.operador)
        self.assertGreaterEqual(item_value.created_at,antes)
        self.assertLessEqual(item_value.created_at,timezone.now())
        self.assertIsNone(item_value.started_at)
        self.assertEqual(item_value.occurrence_description,'Parou ao alimentar a placa.\nAlarme no painel.')
        self.assertEqual(item_value.problem,'Falha de alimentação')
        consulta=self.client.get(f'/api/orders/{item_value.pk}').json()
        self.assertEqual(consulta['opened_by_name'],'Operador relato')
        self.assertEqual(consulta['occurrence_description'],item_value.occurrence_description)
        self.problema.name='Nome atualizado';self.problema.save()
        item_value.refresh_from_db();self.assertEqual(item_value.problem,'Falha de alimentação')

    def test_os_antiga_sem_relato_continua_valida(self):
        response_value=self.abrir()
        self.assertEqual(response_value.status_code,201,response_value.content)
        self.assertEqual(response_value.json()['occurrence_description'],'')

    def test_relato_invalido_nao_cria_os(self):
        for relato in ('x'*3001, ['texto'], {'texto':'teste'}, None):
            with self.subTest(tipo=type(relato).__name__):
                antes=WorkOrderCode.objects.count()
                self.assertEqual(self.abrir({'occurrenceDescription':relato}).status_code,400)
                self.assertEqual(WorkOrderCode.objects.count(),antes)

    def test_atendimento_preserva_relato_original(self):
        response_value=self.abrir({'occurrenceDescription':'Relato original do operador'})
        item_value=WorkOrderCode.objects.get(pk=response_value.json()['id'])
        item_value.assigned_to=self.admin;item_value.started_at=timezone.now();item_value.status='EM_ANDAMENTO';item_value.save()
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.admin))
        response_value=self.client.patch(f'/api/orders/{item_value.pk}',{'status':'EM_ANDAMENTO','occurrenceDescription':'Trocar relato','rootCause':'Sensor obstruído'},content_type='application/json')
        self.assertEqual(response_value.status_code,200,response_value.content)
        item_value.refresh_from_db()
        self.assertEqual(item_value.occurrence_description,'Relato original do operador')
        self.assertEqual(item_value.root_cause,'Sensor obstruído')
