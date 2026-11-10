"""Produce a teaching guide from the models without exporting database records."""
import csv
import html
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand

from maintenance.portuguese_names import MODEL_NAMES, TABLE_NAMES


class Command(BaseCommand):
    help = 'Gera guia de tabelas e colunas em português, CSV, Mermaid e consultas de leitura.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        folder = Path(options['output'])
        folder.mkdir(parents=True, exist_ok=True)
        previous_names = {new: old for old, new in TABLE_NAMES.items()}
        records, sections = [], []
        guide = ['# MANTIS: primeiros passos em português', '',
                 'Uma tabela é como uma aba de planilha. Cada linha representa um registro; cada coluna guarda uma informação.',
                 'O ID identifica o registro. Uma coluna terminada em _id aponta para outro cadastro. Exemplo: equipamentos.setor_id aponta para setores.id.', '',
                 '## Caminho do login', '',
                 '1. A tela recebe matricula e senha e chama login().',
                 '2. O serviço envia a solicitação ao Django. As chaves HTTP registration e password são mantidas por compatibilidade.',
                 '3. RegistrationBackend procura a conta na tabela usuarios e verifica o hash da coluna senha_hash.',
                 '4. Após a validação, o servidor emite o token usado nas próximas solicitações. A senha não é guardada em texto.', '',
                 '## Como ler o código', '',
                 'form guarda os campos em edição. save() envia os dados. loadData() consulta o servidor. editingId identifica o registro alterado.',
                 'Os formulários do Django agora se chamam UserForm, SectorForm, EquipmentForm e assim por diante.',
                 'Os atributos ORM e chaves JSON antigos continuam em inglês nesta etapa. db_table e db_column fazem a ponte para o banco em português.',
                 'Exemplo: User.registration lê usuarios.matricula. Equipment.serial lê equipamentos.numero_serie.',
                 'authenticate, get_user, save, clean e ngOnInit são nomes reconhecidos pelos frameworks e foram preservados.',
                 'As classes usadas nas regras agora têm nomes como User, Equipment e WorkOrder, sem criar novas tabelas.',
                 'Os contratos HTTP, nomes de rotas, campos ORM, chaves dentro de documentos JSON e migrações históricas não foram renomeados.',
                 'Os nomes de índices, restrições e sequências existentes podem permanecer em inglês. Isso não altera os dados nem os vínculos.', '',
                 '## Onde estudar cada parte', '',
                 'Frontend: frontend/src/app/features contém as telas; core/services contém Auth e Api; core/models descreve o JSON recebido; shared contém formulários reutilizáveis.',
                 'Backend: maintenance/views.py e maintenance/viewsets.py recebem as chamadas; maintenance/services reúne as regras de montagem, compra e preventiva.',
                 'Modelos de impressão: maintenance/document_templates. Origem do calendário: maintenance/calendar_source.py.',
                 'Comandos: create_admin, adopt_legacy, map_database, prepare_preventive_calendar e document_database.',
                 'Consulte CAMINHOS_CODIGO.json e MODULOS_BACKEND.json para ver os caminhos anteriores e atuais.', '',
                 '## Tabelas e colunas', '']
        escape = html.escape
        for model in sorted(apps.get_app_config('maintenance').get_models(), key=lambda item: item._meta.db_table):
            table = model._meta.db_table
            portuguese_name = MODEL_NAMES.get(model.__name__, model.__name__)
            previous = previous_names.get(table, table)
            guide.extend([f'### {table}', '',
                          f'Tabela anterior: `{previous}`. Nome para estudar: `{portuguese_name}`. Registro Django compatível: `{model.__name__}`.', '',
                          '| Campo no código | Coluna no banco | Referência |', '|---|---|---|'])
            rows = []
            for field in model._meta.concrete_fields:
                if not field.column:
                    continue
                reference = f'{field.related_model._meta.db_table}.{field.target_field.column}' if field.is_relation else ''
                records.append({'tabela': table, 'tabela_anterior': previous, 'modelo_python': model.__name__,
                                'nome_portugues': portuguese_name, 'campo_codigo': field.attname,
                                'coluna_portugues': field.column, 'referencia': reference})
                guide.append(f'| {field.attname} | {field.column} | {reference or "—"} |')
                rows.append('<tr>' + ''.join(f'<td>{escape(value)}</td>' for value in
                                              (field.attname, field.column, reference or '—')) + '</tr>')
            guide.append('')
            sections.append(
                f'<section><h2>{escape(table)}</h2><p>Antes: <code>{escape(previous)}</code> · '
                f'Nome para estudar: <code>{portuguese_name}</code> · Registro Django: '
                f'<code>{model.__name__}</code></p><table><thead><tr><th>Campo no código</th>'
                f'<th>Coluna em português</th><th>Aponta para</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>')
        queries = '''-- Consultas de leitura: execute no pgAdmin ou DBeaver conectado ao MANTIS.
-- O limite evita carregar todos os equipamentos de uma vez.
SELECT id, nome, matricula, perfil, ativo FROM usuarios ORDER BY nome LIMIT 50;
SELECT e.id, e.nome, e.numero_serie, s.nome AS setor
FROM equipamentos e LEFT JOIN setores s ON s.id = e.setor_id
ORDER BY e.id LIMIT 50;
SELECT codigo, descricao, numero_peca, fabricante FROM pecas_reposicao ORDER BY descricao LIMIT 50;
'''
        (folder / 'GUIA_PORTUGUES.md').write_text('\n'.join(guide), encoding='utf-8')
        (folder / 'DICIONARIO_PORTUGUES.json').write_text(json.dumps(records, ensure_ascii=False, indent=2),
                                                          encoding='utf-8')
        with (folder / 'DICIONARIO_PORTUGUES.csv').open('w', encoding='utf-8-sig', newline='') as target:
            writer = csv.DictWriter(target, fieldnames=list(records[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(records)
        (folder / 'CONSULTAS_PORTUGUES.sql').write_text(queries, encoding='utf-8')
        introduction = []
        list_open = False
        for line in guide[2:guide.index('## Tabelas e colunas')]:
            if not line:
                continue
            if len(line) > 2 and line[0].isdigit() and line[1:3] == '. ':
                if not list_open:
                    introduction.append('<ol>')
                    list_open = True
                introduction.append('<li>' + escape(line[3:]) + '</li>')
            else:
                if list_open:
                    introduction.append('</ol>')
                    list_open = False
                introduction.append('<h2>' + escape(line[3:]) + '</h2>' if line.startswith('## ') else '<p>' + escape(line) + '</p>')
        if list_open:
            introduction.append('</ol>')
        document = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MANTIS — código e banco em português</title>
<style>body{font:16px/1.6 system-ui;background:#f3f5f8;color:#172337;margin:0}main{max-width:1080px;margin:auto;padding:30px}h1{line-height:1.2}section,article{background:white;padding:24px;border:1px solid #dce1e9;border-radius:12px;margin:20px 0;overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:9px;border-bottom:1px solid #e4e8ef}th{background:#f3f5f8}code{color:#a80e2d}input{padding:14px;width:100%;box-sizing:border-box;border:1px solid #aab5c5;border-radius:8px}a{color:#a80e2d}.leitura{white-space:pre-wrap}nav{display:flex;gap:18px;flex-wrap:wrap}@media print{input,nav{display:none}section{break-inside:avoid}body{background:white}}</style>
<main><h1>MANTIS: código e banco em português</h1><p>Comece pelo login e siga o caminho dos cadastros até as tabelas.</p>
<nav><a href="ER_MANTIS.html">Entender o ER por áreas</a><a href="GUIA_PORTUGUES.md">Guia em texto</a><a href="DICIONARIO_PORTUGUES.csv">Abrir no Excel</a><a href="CONSULTAS_PORTUGUES.sql">Consultas SQL</a><a href="RELACIONAMENTOS_PORTUGUES.mmd">Diagrama Mermaid</a><a href="CAMINHOS_CODIGO.json">Mapa de pastas</a><a href="PACOTE_PORTUGUES.zip">Baixar arquivos</a></nav>
<article>INTRODUCAO</article><h2>Procure um cadastro ou campo</h2><input type="search" placeholder="Ex.: usuarios, matricula, numero_serie, Equipment" aria-label="Pesquisar no dicionário">SECOES
<script>document.querySelector('input').addEventListener('input',function(){const term=this.value.toLocaleLowerCase('pt-BR');document.querySelectorAll('section').forEach(section=>section.hidden=!section.textContent.toLocaleLowerCase('pt-BR').includes(term))})</script></main></html>'''
        (folder / 'GUIA_PORTUGUES.html').write_text(
            document.replace('INTRODUCAO', ''.join(introduction)).replace('SECOES', ''.join(sections)),
            encoding='utf-8')
        # The ER uses the physical catalog constraints to distinguish optional FKs,
        # N:N associations, and 1:1 relations; the summary above does not decide cardinalities.
        if not (folder / 'catalogo-postgres.json').exists():
            call_command('map_database', output=str(folder), stdout=self.stdout)
        call_command('generate_er', output=str(folder), stdout=self.stdout)
        with ZipFile(folder / 'PACOTE_PORTUGUES.zip', 'w', ZIP_DEFLATED) as package:
            for file in sorted(folder.rglob('*')):
                if file.is_file() and file.suffix in ('.html', '.md', '.csv', '.json', '.mmd', '.sql', '.svg', '.drawio'):
                    package.write(file, str(file.relative_to(folder)))
        self.stdout.write(f'Guia gerado: {len(TABLE_NAMES)} tabelas e {len(records)} colunas, sem exportação de dados pessoais.')
