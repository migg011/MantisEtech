"""Produz um guia didático a partir dos modelos, sem exportar registros do banco."""
import csv
import html
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management import call_command
from maintenance.portuguese_schema import TABELAS, MODELOS


class Command(BaseCommand):
    help = 'Gera guia de tabelas e colunas em português, CSV, Mermaid e consultas de leitura.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        folder_value = Path(options['output'])
        folder_value.mkdir(parents=True, exist_ok=True)
        antigos = {novo: antigo for antigo, novo in TABELAS.items()}
        rows_value, secoes = [], []
        guia = ['# MANTIS: primeiros passos em português', '',
                'Uma tabela é como uma aba de planilha. Cada linha representa um registro; cada coluna guarda uma informação.',
                'O ID identifica o registro. Uma coluna terminada em _id aponta para outro cadastro. Exemplo: equipamentos.setor_id aponta para setores.id.', '',
                '## Caminho do login', '',
                '1. A tela recebe matricula e senha e chama entrar().',
                '2. O serviço envia a solicitação ao Django. As chaves HTTP registration e password são mantidas por compatibilidade.',
                '3. AutenticacaoPorMatricula procura a conta na tabela usuarios e verifica o hash da coluna senha_hash.',
                '4. Após a validação, o servidor emite o token usado nas próximas solicitações. A senha não é guardada em texto.', '',
                '## Como ler o código', '',
                'formulario guarda os campos em edição. salvar() envia os dados. carregarDados() consulta o servidor. idEmEdicao identifica o registro alterado.',
                'Os formulários do Django agora se chamam FormularioUsuario, FormularioSetor, FormularioEquipamento e assim por diante.',
                'Os atributos ORM e chaves JSON antigos continuam em inglês nesta etapa. db_table e db_column fazem a ponte para o banco em português.',
                'Exemplo: User.registration lê usuarios.matricula. Equipment.serial lê equipamentos.numero_serie.',
                'authenticate, get_user, save, clean e ngOnInit são nomes reconhecidos pelos frameworks e foram preservados.',
                'As classes usadas nas regras agora têm nomes como Usuario, Equipamento e OrdemServico. São aliases dos modelos registrados no Django: Usuario e User representam o mesmo modelo, não duas tabelas.',
                'Os contratos HTTP, nomes de rotas, campos ORM, chaves dentro de documentos JSON e migrações históricas não foram renomeados.',
                'Os nomes de índices, restrições e sequências existentes podem permanecer em inglês. Isso não altera os dados nem os vínculos.', '',
                '## Onde estudar cada parte', '',
                'Frontend: mantis/frontend/src/app/funcionalidades contém as telas; nucleo/servicos contém Autenticacao e Api; nucleo/modelos descreve o JSON recebido; compartilhados contém formulários reutilizáveis.',
                'Backend: maintenance/api.py recebe as chamadas; servicos.py contém regras de montagem e compra; preventivas.py, ordens_preventivas.py e agenda_preventiva.py organizam as preventivas.',
                'Modelos de impressão: maintenance/document_templates. Origem do calendário: maintenance/origem_calendario.py.',
                'Comandos: criar_administrador, adotar_legado, mapear_banco, preparar_calendario_preventivo e documentar_portugues. Os comandos antigos ainda encaminham para os novos.',
                'Os arquivos services.py, preventive.py, preventive_orders.py, preventive_schedule.py e calendar_source.py agora são pontes pequenas de compatibilidade; estude os módulos em português.',
                'Consulte CAMINHOS_CODIGO.json e MODULOS_BACKEND.json para ver os caminhos anteriores e atuais.', '',
                '## Tabelas e colunas', '']
        escapar = html.escape
        for modelo in sorted(apps.get_app_config('maintenance').get_models(), key=lambda item: item._meta.db_table):
            tabela = modelo._meta.db_table
            nome_portugues = MODELOS[modelo.__name__]
            guia.extend([f'### {tabela}', '', f'Tabela anterior: `{antigos[tabela]}`. Nome para estudar: `{nome_portugues}`. Registro Django compatível: `{modelo.__name__}`.', '', '| Campo no código | Coluna no banco | Referência |', '|---|---|---|'])
            lines_value = []
            for field_value in modelo._meta.concrete_fields:
                if not field_value.column:
                    continue
                referencia = f'{field_value.related_model._meta.db_table}.{field_value.target_field.column}' if field_value.is_relation else ''
                rows_value.append({'tabela': tabela, 'tabela_anterior': antigos[tabela], 'modelo_python': modelo.__name__, 'nome_portugues': nome_portugues, 'campo_codigo': field_value.attname, 'coluna_portugues': field_value.column, 'referencia': referencia})
                guia.append(f'| {field_value.attname} | {field_value.column} | {referencia or "—"} |')
                lines_value.append('<tr>' + ''.join(f'<td>{escapar(value_value)}</td>' for value_value in (field_value.attname, field_value.column, referencia or '—')) + '</tr>')
            guia.append('')
            secoes.append(f'<section><h2>{escapar(tabela)}</h2><p>Antes: <code>{escapar(antigos[tabela])}</code> · Nome para estudar: <code>{nome_portugues}</code> · Registro Django: <code>{modelo.__name__}</code></p><table><thead><tr><th>Campo no código</th><th>Coluna em português</th><th>Aponta para</th></tr></thead><tbody>{"".join(lines_value)}</tbody></table></section>')
        consultas = '''-- Consultas de leitura: execute no pgAdmin ou DBeaver conectado ao MANTIS.
-- O limite evita carregar todos os equipamentos de uma vez.
SELECT id, nome, matricula, perfil, ativo FROM usuarios ORDER BY nome LIMIT 50;
SELECT e.id, e.nome, e.numero_serie, s.nome AS setor
FROM equipamentos e LEFT JOIN setores s ON s.id = e.setor_id
ORDER BY e.id LIMIT 50;
SELECT codigo, descricao, numero_peca, fabricante FROM pecas_reposicao ORDER BY descricao LIMIT 50;
'''
        (folder_value / 'GUIA_PORTUGUES.md').write_text('\n'.join(guia), encoding='utf-8')
        (folder_value / 'DICIONARIO_PORTUGUES.json').write_text(json.dumps(rows_value, ensure_ascii=False, indent=2), encoding='utf-8')
        with (folder_value / 'DICIONARIO_PORTUGUES.csv').open('w', encoding='utf-8-sig', newline='') as destino:
            escritor = csv.DictWriter(destino, fieldnames=list(rows_value[0]), delimiter=';')
            escritor.writeheader()
            escritor.writerows(rows_value)
        (folder_value / 'CONSULTAS_PORTUGUES.sql').write_text(consultas, encoding='utf-8')
        introducao = []
        lista_aberta = False
        for row_value in guia[2:guia.index('## Tabelas e colunas')]:
            if not row_value:
                continue
            if len(row_value) > 2 and row_value[0].isdigit() and row_value[1:3] == '. ':
                if not lista_aberta:
                    introducao.append('<ol>')
                    lista_aberta = True
                introducao.append('<li>'+escapar(row_value[3:])+'</li>')
            else:
                if lista_aberta:
                    introducao.append('</ol>')
                    lista_aberta = False
                introducao.append('<h2>'+escapar(row_value[3:])+'</h2>' if row_value.startswith('## ') else '<p>'+escapar(row_value)+'</p>')
        if lista_aberta:
            introducao.append('</ol>')
        document_value = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MANTIS — código e banco em português</title>
<style>body{font:16px/1.6 system-ui;background:#f3f5f8;color:#172337;margin:0}main{max-width:1080px;margin:auto;padding:30px}h1{line-height:1.2}section,article{background:white;padding:24px;border:1px solid #dce1e9;border-radius:12px;margin:20px 0;overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:9px;border-bottom:1px solid #e4e8ef}th{background:#f3f5f8}code{color:#a80e2d}input{padding:14px;width:100%;box-sizing:border-box;border:1px solid #aab5c5;border-radius:8px}a{color:#a80e2d}.leitura{white-space:pre-wrap}nav{display:flex;gap:18px;flex-wrap:wrap}@media print{input,nav{display:none}section{break-inside:avoid}body{background:white}}</style>
<main><h1>MANTIS: código e banco em português</h1><p>Comece pelo login e siga o caminho dos cadastros até as tabelas.</p>
<nav><a href="ER_MANTIS.html">Entender o ER por áreas</a><a href="GUIA_PORTUGUES.md">Guia em texto</a><a href="DICIONARIO_PORTUGUES.csv">Abrir no Excel</a><a href="CONSULTAS_PORTUGUES.sql">Consultas SQL</a><a href="RELACIONAMENTOS_PORTUGUES.mmd">Diagrama Mermaid</a><a href="CAMINHOS_CODIGO.json">Mapa de pastas</a><a href="PACOTE_PORTUGUES.zip">Baixar arquivos</a></nav>
<article>INTRODUCAO</article><h2>Procure um cadastro ou campo</h2><input type="search" placeholder="Ex.: usuarios, matricula, numero_serie, Equipment" aria-label="Pesquisar no dicionário">SECOES
<script>document.querySelector('input').addEventListener('input',function(){const termo=this.value.toLocaleLowerCase('pt-BR');document.querySelectorAll('section').forEach(secao=>secao.hidden=!secao.textContent.toLocaleLowerCase('pt-BR').includes(termo))})</script></main></html>'''
        (folder_value / 'GUIA_PORTUGUES.html').write_text(document_value.replace('INTRODUCAO', ''.join(introducao)).replace('SECOES', ''.join(secoes)), encoding='utf-8')
        # O ER usa as restrições físicas do catálogo para distinguir FK opcional,
        # associação N:N e relação 1:1; o resumo acima não decide cardinalidades.
        if not (folder_value / 'catalogo-postgres.json').exists():
            call_command('mapear_banco', output=str(folder_value), stdout=self.stdout)
        call_command('gerar_er', output=str(folder_value), stdout=self.stdout)
        with ZipFile(folder_value / 'PACOTE_PORTUGUES.zip', 'w', ZIP_DEFLATED) as pacote:
            for arquivo in sorted(folder_value.rglob('*')):
                if arquivo.is_file() and arquivo.suffix in ('.html', '.md', '.csv', '.json', '.mmd', '.sql', '.svg', '.drawio'):
                    pacote.write(arquivo, str(arquivo.relative_to(folder_value)))
        self.stdout.write(f'Guia gerado: {len(TABELAS)} tabelas e {len(rows_value)} colunas, sem exportação de dados pessoais.')
