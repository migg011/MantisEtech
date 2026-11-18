"""API e concorrência do estoque; sempre executados em banco de testes."""
import csv
import io
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.utils import timezone
from django.test import TestCase, TransactionTestCase, Client
from django.db import connection, connections, close_old_connections, transaction, IntegrityError
from django.core.exceptions import ValidationError
from maintenance.api import issue_token_value
from maintenance.models import UserCode, SparePartCode, MovimentacaoEstoque, SectorCode, LineCode
from maintenance.models import PurchaseRequest, PurchaseItem
from maintenance.stock import record_movement

class StockAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=UserCode.objects.create_user('ST-ADM','Strong-Test-Password-123',name='Admin estoque',role='ADMINISTRADOR')
        cls.tech=UserCode.objects.create_user('ST-TEC','Strong-Test-Password-123',name='Técnico estoque',role='TECNICO')
        sector=SectorCode.objects.create(code='ST-SET',name='Setor teste')
        line=LineCode.objects.create(code='ST-LIN',name='Linha teste',sector=sector)
        cls.operator=UserCode.objects.create_user('ST-OP','Strong-Test-Password-123',name='Operador estoque',role='OPERADOR',line=line)
        cls.part=SparePartCode.objects.create(code='ST-001',description='Suporte NPM',part_number='N610113699AA',manufacturer='Panasonic',unit='UN',minimum_stock=2,reorder_point=1)

    def setUp(self): self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.admin))
    def post(self,kind,quantity,note='Contagem de teste',key=None,status=201):
        data={'kind':kind,'quantity':quantity,'note':note,'requestKey':key or str(uuid4())}
        response=self.client.post(f'/api/spare-parts/{self.part.pk}/stock-movements',data,content_type='application/json')
        self.assertEqual(response.status_code,status,response.content[:500])
        return response.json(),data

    def test_stock_balances_are_independent_by_sector(self):
        sectors = [SectorCode.objects.create(code=f'CC-{i}', name=f'Setor {i}') for i in range(2)]
        path = f'/api/spare-parts/{self.part.pk}'
        for sector, amount in zip(sectors, (2, 8)):
            response = self.client.post(path + '/stock-movements', {
                'sectorId': sector.pk, 'kind': 'INICIAL', 'quantity': amount,
                'requestKey': str(uuid4()), 'storageLocation': sector.name,
            }, content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
        response = self.client.post(path + '/stock-movements', {
            'sectorId': sectors[0].pk, 'kind': 'SAIDA', 'quantity': 3, 'requestKey': str(uuid4()),
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        for sector, amount in zip(sectors, (2, 8)):
            details = self.client.get(path + '/details', {'sectorId': sector.pk}).json()
            self.assertEqual(Decimal(details['stock_quantity']), amount)
            self.assertEqual(details['storage_location'], sector.name)
            self.assertEqual(len(self.client.get(path + '/stock-movements', {'sectorId': sector.pk}).json()), 1)
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock_quantity, 10)

    def test_linked_receipts_close_purchase_after_all_quantities_arrive(self):
        purchase = PurchaseRequest.objects.create(
            requester=self.tech, manager=self.admin, purchase_type='NACIONAL',
            sector=self.operator.line.sector, status='APROVADA', justification='Reposicao', priority='MEDIA',
        )
        PurchaseItem.objects.create(request=purchase, spare_part=self.part, quantity=3)
        payload = {
            'purchaseRequestId': purchase.pk, 'requestKey': str(uuid4()),
            'movementDate': timezone.localdate().isoformat(),
            'supplier': 'Fornecedor', 'documentReference': 'NF-42',
            'items': [{'partId': self.part.pk, 'quantity': 4, 'previousQuantity': 4}],
        }
        path = '/api/spare-parts/receipts'
        self.assertEqual(self.client.post(path, payload, content_type='application/json').status_code, 400)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'APROVADA')
        self.assertFalse(MovimentacaoEstoque.objects.filter(spare_part=self.part).exists())

        payload['items'][0]['quantity'] = 2
        for _ in range(2):
            response = self.client.post(path, payload, content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
        purchase.refresh_from_db()
        self.part.refresh_from_db()
        self.assertEqual(purchase.status, 'RECEBIDA_PARCIALMENTE')
        self.assertEqual(self.part.stock_quantity, 6)
        self.assertEqual(purchase.events.filter(action='RECEBIMENTO', actor=self.admin).count(), 1)
        detail = self.client.get(f'/api/spare-purchase/requests/{purchase.pk}').json()
        self.assertEqual(Decimal(detail['items'][0]['pending_quantity']), 1)
        payload['requestKey'] = str(uuid4())
        self.assertEqual(self.client.post(path, payload, content_type='application/json').status_code, 409)
        payload['documentReference'] = 'NF-43'
        payload['items'][0]['quantity'] = 1
        self.assertEqual(self.client.post(path, payload, content_type='application/json').status_code, 200)
        purchase.refresh_from_db()
        self.part.refresh_from_db()
        self.assertEqual(purchase.status, 'RECEBIDA')
        self.assertEqual(self.part.stock_quantity, 7)
        self.assertEqual(MovimentacaoEstoque.objects.filter(
            spare_part=self.part, sector=purchase.sector, kind='ENTRADA',
        ).count(), 2)

    def test_receipt_creates_missing_part_and_posts_all_items_once(self):
        payload = {
            'requestKey': str(uuid4()), 'movementDate': timezone.localdate().isoformat(),
            'supplier': 'Fornecedor teste', 'documentReference': 'NF-41',
            'items': [
                {'partId': self.part.pk, 'quantity': 2, 'previousQuantity': 5},
                {'partNumber': 'NEW-41', 'description': 'Peça nova', 'unit': 'UN', 'quantity': 0},
            ],
        }
        path = '/api/spare-parts/receipts'
        rejected = self.client.post(path, payload, content_type='application/json')
        self.assertEqual(rejected.status_code, 400, rejected.content)
        self.assertFalse(MovimentacaoEstoque.objects.exists())
        self.assertFalse(SparePartCode.objects.filter(part_number='NEW-41').exists())

        payload['items'][1]['quantity'] = 3
        posted = self.client.post(path, payload, content_type='application/json')
        self.assertEqual(posted.status_code, 200, posted.content)
        replayed = self.client.post(path, payload, content_type='application/json')
        self.assertEqual(replayed.json(), posted.json())
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock_quantity, 7)
        self.assertEqual(SparePartCode.objects.get(part_number='NEW-41').stock_quantity, 3)
        self.assertEqual(MovimentacaoEstoque.objects.filter(document_reference='NF-41', kind='ENTRADA').count(), 2)

    def test_initial_entries_exits_adjustment_and_master_edit(self):
        self.part.unit = 'M'
        self.part.save(update_fields=['unit'])
        self.assertIsNone(self.client.get(f'/api/spare-parts/{self.part.pk}/details').json()['stock_quantity'])
        self.post('ENTRADA',1,status=400)
        self.post('INICIAL',10)
        self.post('INICIAL',12,status=400)
        self.post('ENTRADA','2.500')
        self.post('SAIDA','3.250')
        self.post('AJUSTE','7.125')
        self.part.refresh_from_db();self.assertEqual(self.part.stock_quantity,Decimal('7.125'))
        moves=list(MovimentacaoEstoque.objects.order_by('pk'))
        self.assertEqual([m.delta for m in moves],[Decimal('10'),Decimal('2.5'),Decimal('-3.25'),Decimal('-2.125')])
        self.assertEqual(sum(m.delta for m in moves),self.part.stock_quantity)
        history=self.client.get(f'/api/spare-parts/{self.part.pk}/stock-movements').json()
        self.assertEqual(history[0]['performed_by_name'],'Admin estoque')
        self.assertEqual(history[0]['kind'],'AJUSTE')
        response=self.client.patch(f'/api/spare-parts/{self.part.pk}',{'description':'Suporte atualizado'},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.part.refresh_from_db();self.assertEqual(self.part.stock_quantity,Decimal('7.125'))
        self.assertEqual(self.client.patch(f'/api/spare-parts/{self.part.pk}',{'stockQuantity':99},content_type='application/json').status_code,400)
        self.assertEqual(self.client.delete(f'/api/spare-parts/{self.part.pk}').status_code,409)

    def test_unit_pieces_reject_fractional_movements(self):
        self.post('INICIAL', '0.002', status=400)
        self.post('INICIAL', 10)
        for kind in ('ENTRADA', 'SAIDA', 'AJUSTE'):
            self.post(kind, '1.5', status=400)
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock_quantity, 10)
        self.assertEqual(MovimentacaoEstoque.objects.filter(spare_part=self.part).count(), 1)

    def test_idempotency_validation_and_no_partial_write(self):
        self.post('INICIAL',2)
        _,data=self.post('SAIDA',1)
        self.post('SAIDA',1,key=data['requestKey'],status=200)
        self.post('SAIDA',2,key=data['requestKey'],status=400)
        for kind,qty,note in [('SAIDA',2,'Teste'),('ENTRADA',0,'Teste'),('SAIDA',-1,'Teste'),('AJUSTE','NaN','Teste'),('ENTRADA','1.0001','Teste'),('ENTRADA','100000000000','Teste'),('AJUSTE',0,'x'*501),('INVALIDO',1,'Teste')]:
            self.post(kind,qty,note,status=400)
        self.part.refresh_from_db();self.assertEqual(self.part.stock_quantity,1)
        self.assertEqual(MovimentacaoEstoque.objects.count(),2)
        with self.assertRaises(IntegrityError),transaction.atomic():
            SparePartCode.objects.filter(pk=self.part.pk).update(stock_quantity=-1)

    def test_zero_count_permissions_and_inactive_parts(self):
        self.post('INICIAL',0)
        self.assertEqual(self.client.get('/api/spare-parts').json()[0]['stock_status'],'Sem estoque')
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.tech))
        self.assertEqual(self.client.get('/api/spare-parts/inventory').status_code,200)
        self.assertEqual(self.client.get(f'/api/spare-parts/{self.part.pk}/stock-movements').status_code,200)
        self.post('ENTRADA',1,status=403)
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.operator))
        self.assertEqual(self.client.get('/api/spare-parts/inventory.csv').status_code,403)
        self.assertEqual(Client().get('/api/spare-parts/inventory').status_code,401)
        SparePartCode.objects.filter(pk=self.part.pk).update(active=False)
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.admin))
        self.post('ENTRADA',1,status=404)

    def test_inventory_filter_unknown_zero_csv_and_full_catalog(self):
        SparePartCode.objects.bulk_create([SparePartCode(code=f'ST-{n:05}',description=f'Peça {n}',stock_quantity=None) for n in range(501)])
        SparePartCode.objects.create(code='ST-INATIVA',description='Inativa',active=False)
        inv=self.client.get('/api/spare-parts/inventory').json()
        self.assertEqual(inv['total_items'],502)
        self.assertEqual(inv['uninitialized_items'],502)
        self.post('INICIAL',0)
        SparePartCode.objects.filter(pk=self.part.pk).update(description='=FORMULA()',storage_location='+ARMARIO')
        inv=self.client.get('/api/spare-parts/inventory?q=Panasonic').json()
        self.assertEqual(inv['total_items'],1)
        self.assertEqual(inv['uninitialized_items'],0)
        response=self.client.get('/api/spare-parts/inventory.csv?q=N610113699AA')
        self.assertEqual(response.status_code,200)
        rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1][2],"'=FORMULA()")
        self.assertEqual(rows[1][4],"'+ARMARIO")
        self.assertEqual(Decimal(rows[1][6]),0)
        self.assertEqual(rows[1][7],'Sem estoque')
        full=list(csv.reader(io.StringIO(self.client.get('/api/spare-parts/inventory.csv').content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(full),503)
        self.assertTrue(any(row[6]=='' and row[7]=='Não informado' for row in full[1:])) # sem contagem não vira zero

    def test_simple_receipt_date_supplier_document_and_optional_note(self):
        from django.utils import timezone
        from datetime import timedelta
        day=(timezone.localdate()-timedelta(days=1)).isoformat()
        endpoint=f'/api/spare-parts/{self.part.pk}/stock-movements'
        initial={'kind':'INICIAL','quantity':5,'movementDate':day,'note':'','requestKey':str(uuid4())}
        r=self.client.post(endpoint,initial,content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.json()['movement']['note'],'Primeira contagem do estoque')
        data={'kind':'ENTRADA','quantity':2,'movementDate':day,'supplier':'Fornecedor teste','documentReference':'NF-123','note':'','requestKey':str(uuid4())}
        r=self.client.post(endpoint,data,content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.json()['movement']['movement_date'],day)
        self.assertEqual(r.json()['movement']['supplier'],'Fornecedor teste')
        self.assertEqual(r.json()['movement']['document_reference'],'NF-123')
        self.assertEqual(r.json()['movement']['note'],'Entrada de peças')
        self.assertEqual(self.client.post(endpoint,data,content_type='application/json').status_code,200)
        self.part.refresh_from_db();self.assertEqual(self.part.stock_quantity,7)
        self.assertEqual(MovimentacaoEstoque.objects.count(),2)
        changed={**data,'documentReference':'NF-ALTERADA'}
        self.assertEqual(self.client.post(endpoint,changed,content_type='application/json').status_code,400)
        history=self.client.get(endpoint).json()
        self.assertEqual(history[0]['document_reference'],'NF-123')

    def test_receipt_validation_does_not_change_stock(self):
        from django.utils import timezone
        from datetime import timedelta
        self.post('INICIAL',4)
        endpoint=f'/api/spare-parts/{self.part.pk}/stock-movements'
        basis={'kind':'ENTRADA','quantity':1,'note':''}
        changes=[{'movementDate':(timezone.localdate()+timedelta(days=1)).isoformat()},{'movementDate':'2026-02-30'},{'movementDate':'20261102'},{'supplier':[]},{'supplier':'x'*161},{'documentReference':'x'*101},{'note':[]},{'kind':'SAIDA','supplier':'Fornecedor indevido'}]
        for extra in changes:
            data={**basis,**extra,'requestKey':str(uuid4())}
            r=self.client.post(endpoint,data,content_type='application/json')
            self.assertEqual(r.status_code,400,r.content)
        self.part.refresh_from_db();self.assertEqual(self.part.stock_quantity,4)
        self.assertEqual(MovimentacaoEstoque.objects.count(),1)

    def test_old_movement_without_receipt_date_is_preserved_and_replayable(self):
        key=uuid4()
        SparePartCode.objects.filter(pk=self.part.pk).update(stock_quantity=3)
        MovimentacaoEstoque.objects.create(spare_part=self.part,kind='INICIAL',quantity=3,previous_quantity=None,delta=3,resulting_quantity=3,performed_by=self.admin,note='Contagem antiga',request_key=key)
        self.post('INICIAL',3,'Contagem antiga',key=str(key),status=200)
        old=MovimentacaoEstoque.objects.get(request_key=key)
        self.assertIsNone(old.movement_date)
        self.assertEqual(old.supplier,'')
        self.assertEqual(MovimentacaoEstoque.objects.count(),1)

@skipUnless(connection.vendor=='postgresql','Requer bloqueio real do PostgreSQL.')
class StockConcurrencyTests(TransactionTestCase):
    def test_two_exits_cannot_spend_the_same_stock(self):
        actor=UserCode.objects.create_user('ST-RACE','Strong-Test-Password-123',name='Admin',role='ADMINISTRADOR')
        part=SparePartCode.objects.create(code='ST-RACE',description='Peça concorrente')
        record_movement(part.pk,{'kind':'INICIAL','quantity':1,'note':'Saldo inicial de teste','requestKey':str(uuid4())},actor)
        def attempt(_):
            close_old_connections()
            try:
                record_movement(part.pk,{'kind':'SAIDA','quantity':1,'note':'Saída de teste','requestKey':str(uuid4())},actor)
                return True
            except ValidationError: return False
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),[False,True]);part.refresh_from_db()
        self.assertEqual(part.stock_quantity,0)
        self.assertEqual(part.stock_movements.count(),2)

    def test_same_command_in_parallel_is_applied_once(self):
        actor=UserCode.objects.create_user('ST-REPLAY','Strong-Test-Password-123',name='Admin',role='ADMINISTRADOR')
        part=SparePartCode.objects.create(code='ST-REPLAY',description='Peça concorrente')
        data={'kind':'INICIAL','quantity':3,'note':'Saldo inicial de teste','requestKey':str(uuid4())}
        def attempt(_):
            close_old_connections()
            try:return record_movement(part.pk,data,actor)[1]
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),[False,True]);part.refresh_from_db()
        self.assertEqual(part.stock_quantity,3);self.assertEqual(part.stock_movements.count(),1)
