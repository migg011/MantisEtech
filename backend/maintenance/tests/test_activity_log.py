"""Testes do registro de atividades: gravação automática e endpoint de consulta."""

from django.core.cache import cache
from django.test import TestCase

from maintenance.authentication import issue_token
from maintenance.models import ActivityLog, ProblemType, User


class ActivityLogTests(TestCase):
    """Verifica a gravação automática de atividades e os filtros do endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Prepara administrador e técnico para os cenários de auditoria."""
        cls.admin = User.objects.create_user('ADM-AL', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')
        cls.tech = User.objects.create_user('TEC-AL', 'Strong-Test-Password-123',
                                            name='Técnico', role='TECNICO')

    def setUp(self):
        """Autentica o administrador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.admin)

    def test_successful_post_is_logged(self):
        """Uma criação bem-sucedida gera uma linha em ActivityLog."""
        before = ActivityLog.objects.count()
        response = self.client.post('/api/problem-types',
                                    {'name': 'Falha auditada', 'priority': 'MEDIA'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(ActivityLog.objects.count(), before + 1)
        last = ActivityLog.objects.first()
        self.assertEqual(last.actor_registration, 'ADM-AL')
        self.assertEqual(last.method, 'POST')
        self.assertIn('id', last.target)

    def test_get_endpoint_is_not_logged(self):
        """Leituras GET não são gravadas no registro de atividades."""
        before = ActivityLog.objects.count()
        self.client.get('/api/problem-types')
        self.assertEqual(ActivityLog.objects.count(), before)

    def test_activity_log_endpoint_restricted_to_admin(self):
        """O endpoint responde 403 para um técnico não administrador."""
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.tech)
        response = self.client.get('/api/activity-log')
        self.assertEqual(response.status_code, 403)

    def test_activity_log_endpoint_lists_entries(self):
        """O endpoint devolve as linhas recentes com paginação."""
        for i in range(55):
            ActivityLog.objects.create(
                actor_id=self.admin.pk, actor_name='Admin', actor_registration='ADM-AL',
                method='POST', route=f'problem-types/{i}', target={'id': i})
        page = self.client.get('/api/activity-log?page=1').json()
        self.assertEqual(len(page['items']), 50)
        self.assertTrue(page['has_next'])
        self.assertEqual(self.client.get('/api/activity-log?page=2').json()['has_next'], False)

    def test_filter_by_method(self):
        """O filtro method=PATCH restringe as linhas retornadas."""
        ActivityLog.objects.create(
            actor_id=self.admin.pk, actor_name='Admin', actor_registration='ADM-AL',
            method='POST', route='problem-types', target={})
        ActivityLog.objects.create(
            actor_id=self.admin.pk, actor_name='Admin', actor_registration='ADM-AL',
            method='PATCH', route='problem-types/1', target={'id': 1})
        rows = self.client.get('/api/activity-log?method=PATCH').json()['items']
        self.assertTrue(all(row['method'] == 'PATCH' for row in rows))
