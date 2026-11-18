"""Prepara a base provisória do calendário; não importa cadastros para o banco."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from maintenance.calendar_import import prepare_calendar_value


class Command(BaseCommand):
    help = 'Converte a planilha 2025 em referência de planejamento 2026 sem criar OS ou máquinas.'

    def add_arguments(self, parser):
        """O caminho da origem é explícito para não depender da pasta pessoal de outro usuário."""
        parser.add_argument('--source', required=True)

    def handle(self, *args, **options):
        """Grava somente o arquivo de referência versionado, sem modificar a planilha fornecida."""
        data = prepare_calendar_value(options['source'])
        target = Path(__file__).resolve().parents[2] / 'document_templates' / 'preventive_calendar_2026.json'
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(json.dumps(data['summary'], ensure_ascii=False))
        self.stdout.write(f'Linhas excluídas: {len(data["excluded_rows"])}')
