"""Lê a planilha de referência sem executar fórmulas nem gravar equipamentos, usuários ou OS."""
from .compatibility_value import adapt_call
from collections import Counter
from datetime import datetime
from pathlib import Path
import unicodedata
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_rows_value(path_value):
    """Lê apenas valores da aba de OS; ignora as instruções, contatos e dashboards do arquivo."""
    with ZipFile(path_value) as archive:
        strings = [''.join(node.itertext()) for node in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        relationships = {node.attrib['Id']: node.attrib['Target'] for node in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets = ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets', NS)
        sheet = next(sheet for sheet in sheets if sheet.attrib['name'] == 'Ordens de Serviço')
        target = relationships[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        for row_value in ET.fromstring(archive.read(member)).findall('s:sheetData/s:row', NS):
            cells = {}
            for cell in row_value:
                value_value = cell.find('s:v', NS)
                text = value_value.text if value_value is not None else ''
                if cell.attrib.get('t') == 's':
                    text = strings[int(text)]
                elif cell.attrib.get('t') == 'inlineStr':
                    text = ''.join(cell.find('s:is', NS).itertext())
                if text:
                    cells[''.join(filter(str.isalpha, cell.attrib['r']))] = text.strip()
            if int(row_value.attrib['r']) > 3 and cells.get('B'):
                yield int(row_value.attrib['r']), cells


def parse_source_datetime_value(value_value):
    """Normaliza espaços e anos curtos. Formato americano só é aceito quando o segundo número excede 12, sem ambiguidade."""
    value_value = re.sub(r'\s*-\s*', ' - ', value_value or '')
    for pattern in ('%d/%m/%Y - %H:%M', '%d/%m/%y - %H:%M'):
        try:
            return datetime.strptime(value_value, pattern)
        except ValueError:
            pass
    try:
        if int(value_value.split('/')[1]) > 12:
            return datetime.strptime(value_value, '%m/%d/%Y - %H:%M')
    except (ValueError, IndexError):
        pass
    return None


def prepare_calendar_value(path_value):
    """Transfere dia/mês/horário para 2026 como proposta. Não reaproveita status de execução de 2025."""
    events_value, issues = [], []
    for row_value, cells in read_rows_value(path_value):
        planned = parse_source_datetime_value(cells.get('H'))
        if not planned:
            issues.append({'row': row_value, 'reference': cells['B'], 'reason': 'Data prevista ausente ou inválida.'})
            continue
        reason = cells.get('C', '')
        normalized = unicodedata.normalize('NFKD', reason).encode('ascii', 'ignore').decode().lower()
        frequency_value = next((code for text, code in [('bimestral', 'BIMESTRAL'), ('trimestral', 'TRIMESTRAL'), ('anual', 'ANUAL')] if text in normalized), None)
        performed_value = parse_source_datetime_value(cells.get('I'))
        warnings = []
        if not frequency_value:
            warnings.append('Periodicidade não informada na origem.')
        if performed_value and performed_value < planned:
            warnings.append('Data realizada anterior à prevista no arquivo de 2025.')
        proposal = planned.replace(year=2026)
        if proposal.weekday() >= 5:
            warnings.append('Proposta cai em fim de semana; revisar disponibilidade.')
        items_value = [cells.get(column, '') for column in 'LMNOPQRSTU']
        events_value.append({'id': f'excel-{row_value}', 'source_row': row_value, 'reference': cells['B'],
                       'sector': cells.get('A', 'Sem seção'), 'machine': cells.get('D', 'Não informada'),
                       'model': cells.get('E', ''), 'frequency': frequency_value, 'reason': reason,
                       'date': proposal.date().isoformat(), 'time': proposal.strftime('%H:%M'),
                       'source_date': planned.date().isoformat(), 'technician': cells.get('K', ''),
                       'items': [item_value for item_value in items_value if item_value and item_value.upper() != 'N/A'], 'warnings': warnings})
    return {'source_file': Path(path_value).name, 'source_sheet': 'Ordens de Serviço', 'source_year': 2025,
            'planning_year': 2026, 'provisional': True, 'events': events_value, 'excluded_rows': issues,
            'summary': {'events': len(events_value), 'machines': len({(event['sector'], event['machine'], event['model']) for event in events_value}),
                        'missing_frequency': sum(event['frequency'] is None for event in events_value),
                        'warning_events': sum(bool(event['warnings']) for event in events_value),
                        'frequencies': dict(Counter(event['frequency'] or 'NAO_INFORMADA' for event in events_value))}}

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
read_rows = adapt_call(read_rows_value, {'path': 'path_value'})
parse_source_datetime = adapt_call(parse_source_datetime_value, {'value': 'value_value'})
prepare_calendar = adapt_call(prepare_calendar_value, {'path': 'path_value'})
