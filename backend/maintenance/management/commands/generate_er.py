"""Gera o ER em visões didáticas e formatos editáveis, sem alterar o banco."""
import json

from django.core.management.base import BaseCommand

from maintenance.er_diagrams import generate_er


class Command(BaseCommand):
    help = 'Organiza o ER por áreas a partir do catálogo gerado por map_database.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(generate_er(options['output']), ensure_ascii=False))
