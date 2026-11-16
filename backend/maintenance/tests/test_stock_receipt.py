"""Testes do endpoint de entrada por nota fiscal."""

import uuid
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from maintenance.authentication import issue_token
from maintenance.models import SparePart, StockMovement, User


class StockReceiptTests(TestCase):
    """Garante que a entrada por nota grava os movimentos na mesma transação."""

    @classmethod
    def setUpTestData(cls):
        """Prepara o administrador e as peças com saldo inicial."""
        cls.admin = User.objects.create_user('ADM-SR', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')
        cls.part_a = SparePart.objects.create(description='Sensor', part_number='SR-A', unit='UN',
                                              stock_quantity=Decimal('10'))
        cls.part_b = SparePart.objects.create(description='Correia', part_number='SR-B', unit='UN',
                                              stock_quantity=Decimal('5'))

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def _payload(self, items):
        """Monta o payload base com fornecedor, nota, data e chave de requisição única."""
        return {
            'supplier': 'Fornecedor X', 'documentReference': 'NF-123',
            'movementDate': timezone.localdate().isoformat(),
            'requestKey': str(uuid.uuid4()), 'items': items,
        }

    def test_receipt_records_all_items(self):
        """A entrada registra um StockMovement por item e devolve os saldos resultantes."""
        response = self.client.post('/api/spare-parts/receipts', self._payload([
            {'partId': self.part_a.pk, 'quantity': '4'},
            {'partId': self.part_b.pk, 'quantity': '2'},
        ]), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content[:400])
        body = response.json()
        self.assertEqual(len(body['items']), 2)
        self.assertEqual(StockMovement.objects.filter(document_reference='NF-123').count(), 2)
        self.part_a.refresh_from_db()
        self.assertEqual(self.part_a.stock_quantity, Decimal('14'))

    def test_receipt_rejects_missing_supplier(self):
        """A validação exige fornecedor e número da nota."""
        payload = self._payload([{'partId': self.part_a.pk, 'quantity': '1'}])
        payload['supplier'] = ''
        response = self.client.post('/api/spare-parts/receipts', payload,
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_receipt_rejects_duplicate_parts(self):
        """A nota não aceita a mesma peça em duas linhas."""
        response = self.client.post('/api/spare-parts/receipts', self._payload([
            {'partId': self.part_a.pk, 'quantity': '1'},
            {'partId': self.part_a.pk, 'quantity': '2'},
        ]), content_type='application/json')
        self.assertEqual(response.status_code, 400)
