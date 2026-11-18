"""Comando manual para criar o primeiro administrador com validação de senha, sem credenciais padrão."""

from getpass import getpass
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from maintenance.models import UserCode

class Command(BaseCommand):
    """Comando manual para criar o primeiro administrador com validação de senha, sem credenciais padrão."""
    help = 'Cria o primeiro administrador, sem credenciais padrão.'
    def handle(self, *args, **options):
        """Coleta os dados no terminal, valida a senha e cria o administrador se ainda não houver um ativo."""
        if UserCode.objects.filter(role='ADMINISTRADOR', active=True).exists():
            raise CommandError('Já existe um administrador ativo. Gerencie os acessos na tela de usuários.')
        name_value = input('Nome: ').strip()
        registration_number = input('Matrícula: ').strip()
        senha = getpass('Senha: ')
        if senha != getpass('Confirme a senha: '):
            raise CommandError('As senhas não coincidem.')
        try:
            validate_password(senha)
            # As chaves abaixo pertencem ao contrato ORM; o banco já usa português.
            UserCode.objects.create_user(registration=registration_number, password=senha, name=name_value, role='ADMINISTRADOR')
        except ValidationError as erro:
            raise CommandError('; '.join(erro.messages))
        self.stdout.write(self.style.SUCCESS('Administrador criado.'))
