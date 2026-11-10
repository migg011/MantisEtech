"""Lê a planilha de referência sem executar fórmulas nem gravar equipamentos, usuários ou OS."""
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

NAMESPACES = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_rows(path):
    """Lê apenas valores da aba de OS; ignora as instruções, contatos e dashboards do arquivo."""
    with ZipFile(path) as archive:
        strings = [''.join(node.itertext()) for node in
                   ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NAMESPACES)]
        relationships = {node.attrib['Id']: node.attrib['Target'] for node in
                         ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets = ET.fromstring(archive.read('xl/workbook.xml')).find('s:sheets', NAMESPACES)
        sheet = next(item for item in sheets if item.attrib['name'] == 'Ordens de Serviço')
        target = relationships[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        for row in ET.fromstring(archive.read(member)).findall('s:sheetData/s:row', NAMESPACES):
            cells = {}
            for cell in row:
                value = cell.find('s:v', NAMESPACES)
                text = value.text if value is not None else ''
                if cell.attrib.get('t') == 's':
                    text = strings[int(text)]
                elif cell.attrib.get('t') == 'inlineStr':
                    text = ''.join(cell.find('s:is', NAMESPACES).itertext())
                if text:
                    cells[''.join(filter(str.isalpha, cell.attrib['r']))] = text.strip()
            if int(row.attrib['r']) > 3 and cells.get('B'):
                yield int(row.attrib['r']), cells


def parse_source_datetime(value):
    """Normaliza espaços e anos curtos. Formato americano só é aceito quando o segundo número excede 12, sem ambiguidade."""
    value = re.sub(r'\s*-\s*', ' - ', value or '')
    for pattern in ('%d/%m/%Y - %H:%M', '%d/%m/%y - %H:%M'):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    try:
        if int(value.split('/')[1]) > 12:
            return datetime.strptime(value, '%m/%d/%Y - %H:%M')
    except (ValueError, IndexError):
        pass
    return None


def prepare_calendar(path):
    """Transfere dia/mês/horário para 2026 como proposta. Não reaproveita status de execução de 2025."""
    events, issues = [], []
    for row, cells in read_rows(path):
        planned = parse_source_datetime(cells.get('H'))
        if not planned:
            issues.append({'row': row, 'reference': cells['B'], 'reason': 'Data prevista ausente ou inválida.'})
            continue
        reason = cells.get('C', '')
        normalized = unicodedata.normalize('NFKD', reason).encode('ascii', 'ignore').decode().lower()
        frequency = next((code for text, code in
                          [('bimestral', 'BIMESTRAL'), ('trimestral', 'TRIMESTRAL'), ('anual', 'ANUAL')]
                          if text in normalized), None)
        performed = parse_source_datetime(cells.get('I'))
        warnings = []
        if not frequency:
            warnings.append('Periodicidade não informada na origem.')
        if performed and performed < planned:
            warnings.append('Data realizada anterior à prevista no arquivo de 2025.')
        proposal = planned.replace(year=2026)
        if proposal.weekday() >= 5:
            warnings.append('Proposta cai em fim de semana; revisar disponibilidade.')
        items = [cells.get(column, '') for column in 'LMNOPQRSTU']
        events.append({'id': f'excel-{row}', 'source_row': row, 'reference': cells['B'],
                       'sector': cells.get('A', 'Sem seção'), 'machine': cells.get('D', 'Não informada'),
                       'model': cells.get('E', ''), 'frequency': frequency, 'reason': reason,
                       'date': proposal.date().isoformat(), 'time': proposal.strftime('%H:%M'),
                       'source_date': planned.date().isoformat(), 'technician': cells.get('K', ''),
                       'items': [record for record in items if record and record.upper() != 'N/A'],
                       'warnings': warnings})
    return {'source_file': Path(path).name, 'source_sheet': 'Ordens de Serviço', 'source_year': 2025,
            'planning_year': 2026, 'provisional': True, 'events': events, 'excluded_rows': issues,
            'summary': {'events': len(events),
                        'machines': len({(event['sector'], event['machine'], event['model'])
                                         for event in events}),
                        'missing_frequency': sum(event['frequency'] is None for event in events),
                        'warning_events': sum(bool(event['warnings']) for event in events),
                        'frequencies': dict(Counter(event['frequency'] or 'NAO_INFORMADA'
                                                    for event in events))}}
