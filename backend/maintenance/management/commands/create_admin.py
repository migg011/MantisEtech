"""Manual command to create the first administrator with password validation and no default credentials."""

from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from maintenance.models import User


class Command(BaseCommand):
    """Manual command to create the first administrator with password validation and no default credentials."""
    help = 'Cria o primeiro administrador, sem credenciais padrão.'

    def handle(self, *args, **options):
        """Collect terminal input, validate the password, and create the administrator if none is active."""
        if User.objects.filter(role='ADMINISTRADOR', active=True).exists():
            raise CommandError('Já existe um administrador ativo. Gerencie os acessos na tela de usuários.')
        name = input('Nome: ').strip()
        registration = input('Matrícula: ').strip()
        password = getpass('Senha: ')
        if password != getpass('Confirme a senha: '):
            raise CommandError('As senhas não coincidem.')
        try:
            validate_password(password)
            # The keys below belong to the ORM contract; the database already uses Portuguese.
            User.objects.create_user(registration=registration, password=password, name=name, role='ADMINISTRADOR')
        except ValidationError as error:
            raise CommandError('; '.join(error.messages))
        self.stdout.write(self.style.SUCCESS('Administrador criado.'))
