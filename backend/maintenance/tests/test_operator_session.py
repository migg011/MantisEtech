"""Testes das sessões de operador abertas pelo totem."""

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from maintenance.authentication import issue_token
from maintenance.models import Line, OperatorSession, Sector, User


class OperatorSessionTests(TestCase):
    """Cobre abertura, listagem e fechamento das sessões de operador."""

    @classmethod
    def setUpTestData(cls):
        """Prepara setor, linha e contas usadas nos cenários de sessão do totem."""
        cls.sector = Sector.objects.create(code='SET-T', name='SMT')
        cls.line = Line.objects.create(code='LIN-T', name='Linha do totem', sector=cls.sector)
        cls.admin = User.objects.create_user('ADM-T', 'Strong-Test-Password-123',
                                             name='Admin', role='ADMINISTRADOR')
        cls.operator = User.objects.create_user('OP-T', 'Strong-Test-Password-123',
                                                name='Operador', role='OPERADOR', line=cls.line,
                                                sector=cls.sector)

    def setUp(self):
        """Autentica o operador e limpa o cache para cada cenário."""
        cache.clear()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + issue_token(self.operator)

    def send(self, method, url, data=None, expected=200):
        """Executa a chamada JSON e devolve o corpo com validação de status."""
        response = getattr(self.client, method)(url, data if data is not None else {},
                                                content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content[:400])
        return response.json() if response.content else {}

    def test_open_session_persists_line(self):
        """A abertura grava a sessão com a linha informada e devolve a data de expiração."""
        session = self.send('post', '/api/operator-sessions', {'lineId': self.line.pk}, expected=201)
        self.assertEqual(session['lineId'], self.line.pk)
        self.assertEqual(session['userId'], self.operator.pk)
        self.assertIn('expiresAt', session)
        self.assertEqual(
            OperatorSession.objects.filter(user=self.operator, line=self.line).count(), 1)

    def test_open_session_replaces_previous_active(self):
        """A nova sessão substitui a anterior ainda ativa do mesmo operador."""
        self.send('post', '/api/operator-sessions', {'lineId': self.line.pk}, expected=201)
        self.send('post', '/api/operator-sessions', {'lineId': self.line.pk}, expected=201)
        self.assertEqual(OperatorSession.objects.filter(user=self.operator).count(), 1)

    def test_list_returns_only_active_for_user(self):
        """A listagem devolve apenas as sessões ativas do operador autenticado."""
        OperatorSession.objects.create(
            user=self.operator, line=self.line,
            expires_at=timezone.now() + timedelta(minutes=30))
        OperatorSession.objects.create(
            user=self.admin, line=self.line,
            expires_at=timezone.now() + timedelta(minutes=30))
        OperatorSession.objects.create(
            user=self.operator, line=self.line,
            expires_at=timezone.now() - timedelta(minutes=1))
        rows = self.send('get', '/api/operator-sessions')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['userId'], self.operator.pk)

    def test_close_session_removes_record(self):
        """O endpoint DELETE encerra a sessão aberta pelo próprio operador."""
        session = OperatorSession.objects.create(
            user=self.operator, line=self.line,
            expires_at=timezone.now() + timedelta(minutes=30))
        self.send('delete', f'/api/operator-sessions/{session.pk}')
        self.assertFalse(OperatorSession.objects.filter(pk=session.pk).exists())

    def test_close_session_of_other_user_is_forbidden(self):
        """Um operador não encerra a sessão de outro usuário sem ser administrador."""
        session = OperatorSession.objects.create(
            user=self.admin, line=self.line,
            expires_at=timezone.now() + timedelta(minutes=30))
        self.send('delete', f'/api/operator-sessions/{session.pk}', expected=403)
