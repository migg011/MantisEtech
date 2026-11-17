"""Testes das faixas em tensão, frequência e pressão, e da categoria de esquema elétrico."""

from django.core.cache import cache
from django.test import TestCase

from maintenance.authentication import issue_token
from maintenance.models import Equipment, EquipmentAttachment, EquipmentType, Sector, User


class EquipmentRangeFieldsTests(TestCase):
    """O cadastro aceita faixas de valores nos campos elétricos e pneumáticos."""

    @classmethod
    def setUpTestData(cls):
        """Prepara setor, tipo de equipamento e administrador para o cenário de cadastro técnico."""
        cls.sector = Sector.objects.create(code='SET-R', name='SMT')
        cls.kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        cls.admin = User.objects.create_user('ADM-R', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def test_equipment_accepts_range_in_voltage_frequency_and_pressure(self):
        """O equipamento persiste texto em tensão, frequência e pressão para refletir faixas."""
        equipment = Equipment.objects.create(
            equipment_type=self.kind, sector=self.sector, model='Com faixas',
            voltage_v='220-240', frequency_hz='50/60', pneumatic_pressure_bar='5-7',
        )
        equipment.refresh_from_db()
        self.assertEqual(equipment.voltage_v, '220-240')
        self.assertEqual(equipment.frequency_hz, '50/60')
        self.assertEqual(equipment.pneumatic_pressure_bar, '5-7')

    def test_electrical_attachment_is_accepted(self):
        """A categoria ELECTRICAL é aceita pelo modelo para anexar o esquema elétrico."""
        equipment = Equipment.objects.create(equipment_type=self.kind, sector=self.sector, model='Com esquema')
        attachment = EquipmentAttachment.objects.create(
            equipment=equipment, kind='ELECTRICAL',
            file_name='esquema.pdf', mime_type='application/pdf', content=b'%PDF-1.4',
        )
        attachment.refresh_from_db()
        self.assertEqual(attachment.kind, 'ELECTRICAL')
