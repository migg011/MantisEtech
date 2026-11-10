"""Prepare the provisional calendar base; it does not import registrations into the database."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from maintenance.calendar_source import prepare_calendar


class Command(BaseCommand):
    help = 'Converte a planilha 2025 em referência de planejamento 2026 sem criar OS ou máquinas.'

    def add_arguments(self, parser):
        """Make the source path explicit so it does not depend on another user's home folder."""
        parser.add_argument('--source', required=True)

    def handle(self, *args, **options):
        """Write only the versioned reference file without changing the supplied spreadsheet."""
        data = prepare_calendar(options['source'])
        target = Path(__file__).resolve().parents[2] / 'document_templates' / 'preventive_calendar_2026.json'
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(json.dumps(data['summary'], ensure_ascii=False))
        self.stdout.write(f'Linhas excluídas: {len(data["excluded_rows"])}')
