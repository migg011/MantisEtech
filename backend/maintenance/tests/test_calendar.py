"""Garante que a referência não se torne execução real nem cadastro automático."""
from datetime import datetime
from pathlib import Path
import json
from django.test import SimpleTestCase, TestCase
from maintenance.calendar_source import parse_source_datetime
from maintenance.authentication import issue_token
from maintenance.models import User, Equipment, PreventiveOrder, EquipmentPreventive


class SourceCalendarTests(SimpleTestCase):
    def test_date_formats_and_missing_values(self):
        """O arquivo mistura anos curtos e formato americano inequívoco; ausências não viram datas fictícias."""
        expected = datetime(2025, 3, 21, 14, 0)
        self.assertEqual(parse_source_datetime('21/03/2025 -14:00'), expected)
        self.assertEqual(parse_source_datetime('02/06/25 - 15:10'), datetime(2025, 6, 2, 15, 10))
        self.assertEqual(parse_source_datetime('3/27/2025 - 09:00'), datetime(2025, 3, 27, 9, 0))
        self.assertIsNone(parse_source_datetime(None))
        self.assertIsNone(parse_source_datetime('31/02/2025 - 09:00'))

    def test_reference_reconciliation(self):
        """312 datas são aproveitadas e uma linha incompleta permanece explicitamente excluída."""
        path = Path(__file__).resolve().parents[1] / 'document_templates' / 'preventive_calendar_2026.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(data['events']), 312)
        self.assertEqual(len(data['excluded_rows']), 1)
        self.assertEqual(data['summary']['missing_frequency'], 35)
        self.assertEqual(len({event['id'] for event in data['events']}), 312)
        for event in data['events']:
            proposed = datetime.fromisoformat(event['date'])
            source = datetime.fromisoformat(event['source_date'])
            self.assertEqual(proposed.year, 2026)
            self.assertEqual((proposed.month, proposed.day), (source.month, source.day))
            self.assertNotIn('status', event)
            self.assertNotIn('equipment_id', event)


class CalendarAccessTests(TestCase):
    def test_read_only_staff_access(self):
        """A origem só é exposta à equipe autenticada; consultá-la não cria equipamentos, OS ou agendas."""
        self.assertEqual(self.client.get('/api/preventive-calendar-template').status_code, 401)
        tech = User.objects.create_user('CAL', 'Test-Password-123', name='Teste', role='TECNICO')
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(tech)
        before = (Equipment.objects.count(), PreventiveOrder.objects.count(), EquipmentPreventive.objects.count())
        response = self.client.get('/api/preventive-calendar-template')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['provisional'])
        self.assertEqual(before, (Equipment.objects.count(), PreventiveOrder.objects.count(), EquipmentPreventive.objects.count()))
        self.assertEqual(self.client.post('/api/preventive-calendar-template', {}, content_type='application/json').status_code, 405)
