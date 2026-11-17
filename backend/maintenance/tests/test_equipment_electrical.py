"""Testes do upload e download do esquema elétrico como anexo do equipamento."""

import base64

from django.core.cache import cache
from django.test import TestCase

from maintenance.authentication import issue_token
from maintenance.models import Equipment, EquipmentAttachment, EquipmentType, Sector, User


class ElectricalAttachmentTests(TestCase):
    """Cobre os três endpoints de anexo com a categoria Esquema elétrico."""

    @classmethod
    def setUpTestData(cls):
        """Prepara administrador, setor, tipo e equipamento compartilhados pelos cenários."""
        cls.sector = Sector.objects.create(code='SET-E', name='SMT')
        cls.kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        cls.equipment = Equipment.objects.create(
            equipment_type=cls.kind, sector=cls.sector, model='Com esquema')
        cls.admin = User.objects.create_user('ADM-E', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')

    def setUp(self):
        """Autentica o administrador e limpa o cache de tentativas."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def _pdf_base64(self):
        """Devolve um PDF mínimo codificado em base64 para o cenário de upload."""
        return base64.b64encode(b'%PDF-1.4\n%fake\n').decode()

    def test_upload_electrical_attachment(self):
        """O endpoint PUT aceita o anexo com categoria ELECTRICAL e persiste o arquivo."""
        payload = {'base64': self._pdf_base64(), 'filename': 'esquema.pdf',
                   'mimeType': 'application/pdf'}
        response = self.client.put(
            f'/api/equipment/{self.equipment.pk}/attachments/ELECTRICAL',
            payload, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertTrue(EquipmentAttachment.objects.filter(
            equipment=self.equipment, kind='ELECTRICAL').exists())

    def test_download_electrical_attachment(self):
        """O endpoint GET devolve o conteúdo binário do esquema elétrico."""
        EquipmentAttachment.objects.create(
            equipment=self.equipment, kind='ELECTRICAL',
            filename='esquema.pdf', mime_type='application/pdf',
            content=b'%PDF-1.4\n%fake\n', size_bytes=16, uploaded_by=self.admin)
        response = self.client.get(
            f'/api/equipment/{self.equipment.pk}/attachments/ELECTRICAL/download')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_invalid_kind_rejected(self):
        """Uma categoria desconhecida é rejeitada pelo validador do serviço."""
        response = self.client.get(
            f'/api/equipment/{self.equipment.pk}/attachments/BOGUS/download')
        self.assertEqual(response.status_code, 400)
