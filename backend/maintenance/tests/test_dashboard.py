"""Indicadores do painel conferidos por escopo, período, horários e catálogo completo."""
from datetime import datetime,timedelta,timezone as tz
from unittest.mock import patch
from django.test import TestCase,Client,override_settings
from maintenance.authentication import issue_token
from maintenance.models import User,Sector,Line,EquipmentType,Equipment,WorkOrder,EquipmentPreventive,PreventiveOrder

@override_settings(TIME_ZONE='America/Manaus')
class DashboardAPITests(TestCase):
    def setUp(self):
        self.now=datetime(2026,11,2,16,tzinfo=tz.utc)
        self.clock=patch('maintenance.services.dashboard.timezone.now',return_value=self.now);self.clock.start();self.addCleanup(self.clock.stop)
        sector=Sector.objects.create(code='DS',name='Setor teste')
        self.line=Line.objects.create(code='DL1',name='Linha 1',sector=sector)
        self.other=Line.objects.create(code='DL2',name='Linha 2',sector=sector)
        self.empty=Line.objects.create(code='DL3',name='Linha vazia',sector=sector)
        kind,_=EquipmentType.objects.get_or_create(pk=1,defaults={'name':'Máquina'})
        self.a=Equipment.objects.create(equipment_type=kind,line=self.line,position=1,sector=sector,model='Máquina A',asset_number='ATV-A')
        self.b=Equipment.objects.create(equipment_type=kind,line=self.line,position=2,sector=sector,model='Máquina B')
        self.c=Equipment.objects.create(equipment_type=kind,line=self.other,position=1,sector=sector,model='Máquina externa')
        self.inactive=Equipment.objects.create(equipment_type=kind,line=self.line,position=3,sector=sector,active=False)
        self.admin=User.objects.create_user('DADM','Strong-Test-Password-123',name='Admin',role='ADMINISTRADOR')
        self.tech=User.objects.create_user('DTEC','Strong-Test-Password-123',name='Técnico',role='TECNICO')
        self.operator=User.objects.create_user('DOP','Strong-Test-Password-123',name='Operador',role='OPERADOR',line=self.line)
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.admin))
        self.order(self.a,self.now-timedelta(days=40))
        self.order(self.a,self.now-timedelta(days=2))
        self.order(self.b,self.now-timedelta(days=3),'CONCLUIDA',self.now-timedelta(hours=3),self.now-timedelta(hours=1))
        self.order(self.c,self.now-timedelta(days=1))
        self.order(self.inactive,self.now-timedelta(days=1))
        schedule=EquipmentPreventive.objects.create(equipment=self.b,frequency='MENSAL',next_due=self.now.date())
        self.prev=PreventiveOrder.objects.create(schedule=schedule,expected_due=self.now.date(),planned_date=self.now.date(),frequency='MENSAL',created_by=self.admin,created_at=self.now-timedelta(hours=1),items=['Inspecionar'],safety_instructions='Desenergizar')

    def order(self,equipment,created,status='ABERTA',started=None,finished=None):
        return WorkOrder.objects.create(equipment=equipment,opened_by=self.admin,problem='Teste painel',status=status,created_at=created,started_at=started,finished_at=finished)
    def get(self,query=''):
        r=self.client.get('/api/dashboard'+query);self.assertEqual(r.status_code,200,r.content);return r.json()

    def test_scoped_counts_backlog_and_mttr(self):
        d=self.get(f'?lineId={self.line.pk}&days=7')
        self.assertEqual(d['summary'],{'equipment_total':2,'equipment_active':1,'equipment_fault':1,'open_orders':3,'availability_pct':50.0,'mttr_hours':2.0,'mttr_sample':1,'mtbf_hours':None})
        self.assertEqual(d['distribution'],{'corrective':2,'preventive':1,'predictive':None})
        self.assertEqual(len(d['evolution']),7)
        self.assertEqual(sum(p['opened'] for p in d['evolution']),3)
        self.assertEqual(sum(p['closed'] for p in d['evolution']),1)
        self.assertEqual(d['latest_orders'][0]['number'],self.prev.number)
        self.assertNotIn('Máquina externa',[o['equipment'] for o in d['latest_orders']])

    def test_empty_scope_is_not_false_full_availability(self):
        d=self.get(f'?lineId={self.empty.pk}')
        self.assertEqual(d['summary']['equipment_total'],0)
        self.assertIsNone(d['summary']['availability_pct'])
        self.assertIsNone(d['summary']['mttr_hours'])
        self.assertEqual(d['latest_orders'],[])
        self.assertEqual(d['distribution']['corrective'],0)
        self.assertTrue(all(p['opened']==0 and p['closed']==0 for p in d['evolution']))

    def test_all_counts_are_not_limited_to_200_orders(self):
        before=self.get(f'?lineId={self.line.pk}')
        WorkOrder.objects.bulk_create([WorkOrder(equipment=self.b,opened_by=self.admin,problem='Histórico extenso',created_at=self.now-timedelta(hours=2)) for _ in range(205)])
        d=self.get(f'?lineId={self.line.pk}')
        self.assertEqual(d['summary']['open_orders'],before['summary']['open_orders']+205)
        self.assertEqual(d['distribution']['corrective'],207)
        self.assertEqual(d['summary']['equipment_fault'],2)
        self.assertEqual(len(d['latest_orders']),6)

    def test_daily_series_uses_local_date_and_includes_old_orders_closed_now(self):
        self.order(self.b,datetime(2026,11,2,2,tzinfo=tz.utc)) # 01/11 às 22h em Manaus
        self.order(self.b,self.now-timedelta(days=40),'CONCLUIDA',self.now-timedelta(hours=6),self.now-timedelta(hours=2))
        d=self.get(f'?lineId={self.line.pk}&days=7')
        by_date={r['date']:r for r in d['evolution']}
        self.assertEqual(by_date['2026-11-01']['opened'],1)
        self.assertEqual(by_date['2026-11-02']['opened'],1) # preventiva
        self.assertEqual(by_date['2026-11-02']['closed'],2)
        self.assertEqual(d['summary']['mttr_hours'],3)

    def test_invalid_times_do_not_create_negative_mttr(self):
        WorkOrder.objects.filter(status='CONCLUIDA').delete()
        self.order(self.b,self.now-timedelta(days=1),'CONCLUIDA',self.now-timedelta(hours=1),self.now-timedelta(hours=2))
        d=self.get(f'?lineId={self.line.pk}')
        self.assertIsNone(d['summary']['mttr_hours'])
        self.assertEqual(d['summary']['mttr_sample'],0)

    def test_parameters_and_roles(self):
        self.assertEqual(self.client.get('/api/dashboard?days=365').status_code,400)
        self.assertEqual(self.client.get('/api/dashboard?lineId=abc').status_code,400)
        self.assertEqual(self.client.get('/api/dashboard?lineId=999999').status_code,404)
        self.assertEqual(Client().get('/api/dashboard').status_code,401)
        self.assertEqual(Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.operator)).get('/api/dashboard').status_code,403)
        self.assertEqual(Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.tech)).get('/api/dashboard').status_code,200)
