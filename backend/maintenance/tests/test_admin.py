from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from maintenance.models import User, Sector, Line


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('ADMIN-TEST', 'Strong-Password-123', name='Admin')
        cls.tech = User.objects.create_user('TECH-TEST', 'Strong-Password-123', name='Tech', role='TECNICO')

    def test_admin_login_and_registered_pages(self):
        self.assertTrue(self.client.login(username=self.admin.registration, password='Strong-Password-123'))
        from django.contrib import admin
        for model in admin.site._registry:
            url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_technician_and_inactive_admin_cannot_enter(self):
        for user in (self.tech, self.admin):
            if user == self.admin:
                user.active = False
                user.save(update_fields=['active'])
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_create_user_hashes_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:maintenance_user_add'), {
            'registration': 'NEW', 'name': 'New technician', 'role': 'TECNICO', 'active': 'on',
            'password1': 'Strong-New-Password-123', 'password2': 'Strong-New-Password-123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(registration='NEW').check_password('Strong-New-Password-123'))

    def test_operational_records_cannot_be_written(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('admin:maintenance_sector_add'), {
            'code': 'BYPASS', 'name': 'Bypass',
        }).status_code, 403)
        self.assertFalse(Sector.objects.filter(code='BYPASS').exists())

    def test_admin_cannot_disable_or_demote_self(self):
        self.client.force_login(self.admin)
        for changes in ({'active': ''}, {'role': 'TECNICO'}):
            data = {'registration': self.admin.registration, 'name': 'Admin',
                    'role': 'ADMINISTRADOR', 'active': 'on', **changes}
            response = self.client.post(reverse('admin:maintenance_user_change', args=[self.admin.pk]), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['adminform'].form.errors)
            self.admin.refresh_from_db()
            self.assertTrue(self.admin.active)
            self.assertEqual(self.admin.role, 'ADMINISTRADOR')

    def test_operator_requires_active_line_on_create_and_edit(self):
        self.client.force_login(self.admin)
        line = Line.objects.create(code='INACTIVE', name='Inactive', active=False)
        data = {'registration': 'OP-NEW', 'name': 'Operator', 'role': 'OPERADOR',
                'active': 'on', 'line': line.pk,
                'password1': 'Strong-New-Password-123', 'password2': 'Strong-New-Password-123'}
        response = self.client.post(reverse('admin:maintenance_user_add'), data)
        self.assertIn('line', response.context['adminform'].form.errors)
        self.assertFalse(User.objects.filter(registration='OP-NEW').exists())
        data['registration'] = self.tech.registration
        response = self.client.post(reverse('admin:maintenance_user_change', args=[self.tech.pk]), data)
        self.assertIn('line', response.context['adminform'].form.errors)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.role, 'TECNICO')
        line.active = True
        line.save(update_fields=['active'])
        response = self.client.post(reverse('admin:maintenance_user_change', args=[self.tech.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.line_id, line.pk)


class AdminStaticTests(SimpleTestCase):
    def test_admin_assets_served_without_debug(self):
        from tempfile import TemporaryDirectory
        from django.core.management import call_command
        from django.test import Client, override_settings
        with TemporaryDirectory() as directory:
            with override_settings(DEBUG=False, STATIC_ROOT=directory, WHITENOISE_USE_FINDERS=False):
                call_command('collectstatic', interactive=False, verbosity=0)
                client = Client()
                for path in ('/static/admin/css/base.css', '/static/admin/js/core.js'):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    self.assertTrue(b''.join(response.streaming_content))
                    response.close()
