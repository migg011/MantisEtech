from django.test import TestCase
from maintenance.api import issue_token_value
from maintenance.models import ActivityLog, Sector, User


class ActivityLogTests(TestCase):
    def test_only_successful_changes_are_visible_to_admin(self):
        admin = User.objects.create_user('AUD-ADM', 'Test-password-123', name='Audit Admin', role='ADMINISTRADOR')
        sector = Sector.objects.create(code='AUD', name='Setor original')
        technician = User.objects.create_user('AUD-TEC', 'Test-password-123', name='Tecnico', role='TECNICO', sector=sector)
        path = f'/api/sectors/{sector.pk}'
        admin_auth = {'HTTP_AUTHORIZATION': 'Bearer ' + issue_token_value(admin)}
        response = self.client.patch(path, {'name': 'Setor alterado'}, content_type='application/json', **admin_auth)
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.patch(path, {'name': 'X'}, content_type='application/json', **admin_auth)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ActivityLog.objects.count(), 1)
        log = self.client.get('/api/activity-log', {'actor': 'AUD-ADM', 'method': 'PATCH'}, **admin_auth)
        row = log.json()['items'][0]
        self.assertEqual((row['actor_id'], row['actor_registration'], row['target']), (admin.pk, 'AUD-ADM', {'pk': sector.pk}))
        self.assertEqual(self.client.get('/api/activity-log', HTTP_AUTHORIZATION='Bearer ' + issue_token_value(technician)).status_code, 403)
