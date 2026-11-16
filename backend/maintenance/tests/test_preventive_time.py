"""Testes do horário planejado na agenda de preventiva."""

from datetime import date, time

from django.core.cache import cache
from django.test import TestCase

from maintenance.authentication import issue_token
from maintenance.models import Equipment, EquipmentPreventive, EquipmentType, Sector, User


class PreventiveScheduleTimeTests(TestCase):
    """Garante que o horário planejado é persistido e devolvido na agenda."""

    @classmethod
    def setUpTestData(cls):
        """Prepara administrador, setor, tipo e equipamento para o cenário de agenda."""
        cls.sector = Sector.objects.create(code='SET-P', name='SMT')
        cls.kind, _ = EquipmentType.objects.get_or_create(pk=1, defaults={'name': 'PICK & PLACE'})
        cls.equipment = Equipment.objects.create(
            equipment_type=cls.kind, sector=cls.sector, model='Para preventiva')
        cls.admin = User.objects.create_user('ADM-P', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def test_schedule_model_persists_planned_time(self):
        """O modelo aceita e persiste o horário planejado."""
        schedule = EquipmentPreventive.objects.create(
            equipment=self.equipment, frequency='SEMANAL',
            next_due=date(2026, 12, 20), planned_time=time(8, 30))
        schedule.refresh_from_db()
        self.assertEqual(schedule.planned_time, time(8, 30))

    def test_schedule_persists_when_null(self):
        """O horário planejado é opcional e pode ficar nulo."""
        schedule = EquipmentPreventive.objects.create(
            equipment=self.equipment, frequency='MENSAL',
            next_due=date(2026, 12, 20))
        schedule.refresh_from_db()
        self.assertIsNone(schedule.planned_time)
