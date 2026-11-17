"""Testes do comando seed_demo que gera os cadastros da apresentação."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from maintenance.models import (
    Equipment, EquipmentPreventive, Feeder, FeederMaintenance, Line, PreventiveOrder,
    Sector, User,
)


class SeedDemoCommandTests(TestCase):
    """Verifica a geração dos cadastros e a proteção contra reexecução."""

    def test_requires_administrator(self):
        """O comando pede um administrador existente antes de semear o banco."""
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=StringIO())

    def test_creates_demo_records(self):
        """Com administrador cadastrado, o comando grava setor, linha, máquinas e OS exemplo."""
        User.objects.create_user('ADM-SEED', 'Strong-Test-Password-123',
                                 name='Admin', role='ADMINISTRADOR')
        out = StringIO()
        call_command('seed_demo', stdout=out)
        self.assertEqual(Sector.objects.filter(code='DEMO-SMT').count(), 1)
        self.assertEqual(Line.objects.filter(code='DEMO-SMT-01').count(), 1)
        self.assertEqual(Equipment.objects.count(), 6)
        self.assertEqual(Feeder.objects.filter(part_number='DEMO-FDR-008').count(), 1)
        self.assertEqual(FeederMaintenance.objects.count(), 1)
        self.assertEqual(EquipmentPreventive.objects.count(), 1)
        self.assertEqual(PreventiveOrder.objects.filter(status='CONCLUIDA').count(), 1)

    def test_skip_when_data_exists(self):
        """Se já existir qualquer cadastro, o comando sai sem alterar o banco."""
        User.objects.create_user('ADM-SEED', 'Strong-Test-Password-123',
                                 name='Admin', role='ADMINISTRADOR')
        Sector.objects.create(code='EXISTING', name='Já existe')
        out = StringIO()
        call_command('seed_demo', stdout=out)
        self.assertIn('Já há cadastros', out.getvalue())
        self.assertEqual(Sector.objects.count(), 1)
