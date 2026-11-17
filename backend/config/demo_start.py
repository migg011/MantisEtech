"""Prepara o banco da demonstração antes de iniciar o servidor."""
import os

import django
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import CommandError


def main():
    """Garante migrações, cria o administrador demo (se faltar) e sobe o Waitress."""
    hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if hostname:
        os.environ.setdefault('DJANGO_ALLOWED_HOSTS', f'{hostname},localhost,127.0.0.1')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from maintenance.models import User

    call_command('migrate', interactive=False)
    password = os.environ.pop('MANTIS_DEMO_ADMIN_PASSWORD', '')
    if not User.objects.filter(role='ADMINISTRADOR', active=True).exists():
        if not password:
            raise CommandError('Defina MANTIS_DEMO_ADMIN_PASSWORD para criar o administrador da demonstração.')
        user = User(registration='DEMO', name='Administrador da demonstração', role='ADMINISTRADOR')
        validate_password(password, user)
        user.set_password(password)
        user.full_clean()
        user.save()
    elif os.environ.get('MANTIS_DEMO_RESET_ADMIN_PASSWORD') == 'true':
        user = User.objects.filter(registration='DEMO', role='ADMINISTRADOR', active=True).first()
        if user is None:
            raise CommandError('A conta DEMO precisa estar ativa e ser administradora para redefinir a senha.')
        if not password:
            raise CommandError('Defina MANTIS_DEMO_ADMIN_PASSWORD para redefinir a senha da conta DEMO.')
        if not user.check_password(password):
            validate_password(password, user)
            user.set_password(password)
            user.save(update_fields=['password'])

    if os.environ.get('MANTIS_DEMO_SEED') == 'true':
        call_command('seed_demo')

    port = os.environ.get('PORT', '10000')
    os.execvp('waitress-serve', ['waitress-serve', f'--listen=0.0.0.0:{port}', 'config.demo_wsgi:application'])


if __name__ == '__main__':
    main()
