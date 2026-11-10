"""Gera a apresentação offline e o dicionário usando o catálogo extraído, sem consultar ou alterar o banco."""
from pathlib import Path
from html import escape
import json
import re

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'database-catalog.json').read_text(encoding='utf-8'))
TABLES = DATA['tables']
BUSINESS = [table for table in TABLES if table['module'] != 'Infraestrutura Django']

DESCRIPTIONS = {
    'auth_group': 'Grupos nativos de permissões do Django. Não são os perfis ADMINISTRADOR, TECNICO e OPERADOR usados pela API.',
    'auth_group_permissions': 'Associação N:N entre grupos nativos e permissões do Django.',
    'auth_permission': 'Catálogo de permissões nativas geradas pelo Django; não substitui as verificações de perfil da API.',
    'django_content_type': 'Identifica os modelos para a infraestrutura de permissões do Django.',
    'django_migrations': 'Registra as migrações aplicadas. Não guarda o histórico de alterações dos registros de negócio.',
}
NOTES = {
    'equipment': '�? o centro do cadastro físico. Linha e posição podem estar vazias quando a máquina está disponível no repositório. Setor identifica o proprietário; o tipo referencia o catálogo técnico.',
    'users': 'A matrícula autentica a conta; password_hash armazena hash, nunca a senha em texto. role é o perfil efetivo da API. last_login é herdado de AbstractBaseUser e sua presença não comprova que o login por token o atualize.',
    'equipment_preventives': 'Cada equipamento pode ter uma agenda por periodicidade. checklist_items nulo herda o roteiro do tipo; uma lista representa a personalização do equipamento.',
    'preventive_checklists': 'Roteiro padrão por tipo de equipamento e frequência. items é um array JSONB de atividades.',
    'preventive_orders': 'Não possui equipment_id direto: a máquina é alcançada via schedule_id �?' equipment_preventives.equipment_id. A identificação, os itens e os resultados são preservados em JSONB. PREV-000001 é calculado pelo Python a partir do ID; não é uma coluna.',
    'preventive_executions': 'A conclusão grava execução, técnico, prazo anterior e novo prazo. order_id é opcional para permitir históricos anteriores às OS numeradas e, quando preenchido, é único.',
    'work_orders': 'OS corretivas são separadas das OS preventivas. Abertura/parada = created_at; início do atendimento = started_at; fechamento = finished_at. downtime_seconds mede abertura até fechamento.',
    'line_pendencies': 'Preserva máquina, linha e serial de origem. Concluir a OS não resolve automaticamente a pendência.',
    'equipment_movements': 'Histórico de alocação, remoção e desmontagem. Linha e posição atuais ficam em equipment; este histórico registra origem, destino e autor.',
    'equipment_attachments': 'Foto/manual são armazenados em content (BYTEA), e não em uma pasta pública. A restrição equipment + kind permite um arquivo por categoria para cada máquina.',
    'spare_parts': 'Catálogo geral de peças. minimum_stock, maximum_stock e reorder_point são parâmetros; não existe nesta versão um livro de movimentações que mantenha saldo de estoque.',
    'spare_part_compatibility': 'A tabela de compatibilidade já existe no esquema, com chave primária composta por peça e equipamento. A aba Spare Parts da preventiva consulta o catálogo geral e não utiliza nem grava esse vínculo.',
    'spare_part_technical': 'Ficha técnica reutilizável da peça. A PK spare_part_id também é FK: cada peça tem no máximo uma ficha. Campos técnicos foram adicionados dinamicamente no modelo e estão presentes no catálogo físico.',
    'maintenance_part_requisitions': 'Solicitação direta de peça em uma OS corretiva. Não é uma compra nem um registro automático de retirada/consumo de estoque.',
    'spare_purchase_requests': 'Cabeçalho da solicitação. work_order_id e equipment_id são opcionais; a lista geral da preventiva pode gerar compra sem esses vínculos. O FK work_order_id aponta para work_orders, não para preventive_orders.',
    'spare_purchase_request_items': 'Uma compra possui vários itens. technical_snapshot é a cópia JSONB congelada no envio; futuras alterações na ficha da peça não reescrevem essa cópia.',
    'spare_purchase_events': 'Eventos de criação, edição, submissão e decisão, com autor e horário. �? um histórico específico de compras, não uma auditoria genérica de todas as tabelas.',
}
FIELD_HINTS = {
    'action':'Ação registrada no histórico; os códigos dependem do fluxo de movimentação ou compra.',
    'details':'Detalhes adicionais do evento registrado.', 'manager_comment':'Comentário ou justificativa do gestor na decisão.',
    'last_login':'Campo herdado de autenticação; o fluxo por token não implica atualização automática deste valor.',
    'app':'Aplicação à qual a migração pertence.', 'app_label':'Identificador da aplicação Django associada ao modelo.',
    'applied':'Instante em que a migração foi aplicada.', 'codename':'Código nativo da permissão Django.',
    'group_id':'Referência física a auth_group.id na associação de permissões.',
    'permission_id':'Referência física a auth_permission.id na associação de permissões.',
    'manufacturer':'Fabricante informado no cadastro.', 'model':'Modelo comercial ou identificação do modelo.',
    'model_number':'Número de modelo fornecido pelo fabricante.', 'serial':'Número de série do equipamento.',
    'asset_number':'Identificação patrimonial da máquina.', 'manufacturing_date':'Data de fabricação completa, quando disponível.',
    'manufacturing_date_text':'Data de fabricação com precisão parcial: ano, mês/ano ou dia/mês/ano.',
    'length_mm':'Comprimento em milímetros.', 'width_mm':'Largura em milímetros.', 'height_mm':'Altura em milímetros.',
    'weight_kg':'Peso em quilogramas.', 'voltage_v':'Tensão nominal em volts.', 'current_a':'Corrente nominal em ampères.',
    'frequency_hz':'Frequência elétrica em hertz.', 'power_w':'Potência em watts.', 'pneumatic_pressure_bar':'Pressão pneumática em bar.',
    'description':'Descrição textual do cadastro ou da ocorrência.', 'process_description':'Descrição do processo executado pelo equipamento.',
    'position':'Posição ocupada pela máquina na linha.', 'from_position':'Posição de origem da movimentação.', 'to_position':'Posição de destino da movimentação.',
    'previous_due':'Vencimento anterior preservado no registro da execução.', 'priority':'Prioridade atribuída no catálogo ou no fluxo de manutenção/compra.',
    'safety_instructions':'Orientações de segurança preservadas na emissão da OS preventiva.', 'cancellation_reason':'Justificativa do cancelamento da OS.',
    'resolution':'Solução registrada para resolver a pendência de linha.', 'resolved_at':'Instante da resolução da pendência.',
    'note':'Observação da solicitação.', 'notes':'Observações gerais do registro.', 'item_note':'Observação específica do item de compra.',
    'justification':'Justificativa da necessidade da compra.', 'category':'Categoria de classificação da peça.', 'unit':'Unidade de medida da peça.',
    'part_number':'Código de referência do fabricante; difere do código interno do sistema.', 'storage_location':'Local de armazenagem informado no cadastro.',
    'preferred_supplier':'Fornecedor preferencial em texto; não é FK para um cadastro de fornecedores.',
    'average_cost':'Custo médio informado no cadastro; não é calculado por um livro de estoque nesta versão.', 'last_cost':'�sltimo custo informado no cadastro.',
    'photo_filename':'Nome do arquivo da foto da peça.', 'photo_mime':'Tipo MIME da foto da peça.', 'photo_data':'Conteúdo binário da foto da peça.',
    'datasheet_filename':'Nome do arquivo de ficha técnica da peça.', 'datasheet_data':'Conteúdo binário do arquivo de ficha técnica.',
    'fiscal_validated_at':'Instante da validação fiscal interna registrada.', 'description_en':'Descrição técnica da peça em inglês.',
    'description_pt':'Descrição técnica detalhada em português.', 'pli_description':'Descrição utilizada na documentação PLI.',
    'classification':'Classificação técnica do material.', 'independent_function':'Descrição de funcionamento e autonomia da peça.',
    'connection_details':'Detalhamento das conexões e dispositivos.', 'useful_life':'Vida útil estimada informada na ficha.',
    'asset_classification':'Classificação de ativo fixo ou uso e consumo.', 'main_function':'Função principal da peça.',
    'secondary_function':'Função secundária da peça.', 'raw_material':'Composição ou matéria-prima.', 'intended_use':'Utilização prevista na produção.',
    'application_machine':'Aplicação em máquina, serial ou pedido em texto livre; não cria uma FK de compatibilidade.',
    'mechanical_electrical':'Natureza mecânica ou elétrica.', 'current_type':'Tipo de corrente informado na ficha.',
    'power':'Potência em texto técnico livre da ficha da peça.', 'voltage':'Tensão em texto técnico livre da ficha da peça.',
    'amperage':'Corrente em texto técnico livre da ficha da peça.', 'picture_reference':'Referência da imagem na documentação técnica.',
    'id':'Identificador técnico do registro.', 'active':'Ativo/inativo; usado para desativação lógica onde o fluxo do módulo permite.',
    'created_at':'Instante de criação; TIMESTAMPTZ é convertido para o fuso na apresentação.', 'updated_at':'Instante da última atualização registrada pelo fluxo da aplicação.',
    'code':'Código interno ou de cadastro; conferir a unicidade nas restrições.', 'name':'Nome exibido nas consultas.',
    'registration':'Matrícula usada como identificador de autenticação.', 'password_hash':'Hash de senha; conteúdo deliberadamente não exportado neste mapeamento.',
    'role':'Perfil de acesso validado pela aplicação.', 'status':'Estado do fluxo; os valores aceitos dependem do modelo e dos validadores.',
    'frequency':'Periodicidade da preventiva.', 'next_due':'Próximo vencimento da agenda.', 'last_performed':'�sltima realização registrada.',
    'equipment_snapshot':'Cópia da identificação do equipamento no momento da emissão.', 'technical_snapshot':'Cópia dos dados técnicos no envio da compra.',
    'items':'Lista JSONB de atividades do roteiro.', 'results':'Lista JSONB de resultados e observações por atividade.',
    'parts':'Lista JSONB de peças registradas como substituídas na preventiva; não movimenta estoque.',
    'revision':'Versão de edição para recusar gravações de telas desatualizadas.',
    'checklist_items':'Roteiro específico da agenda; NULL significa herdar o padrão do tipo.',
    'equipment_serial':'Serial preservado no histórico; não depende de uma alteração posterior do cadastro.',
    'planned_date':'Data planejada da OS.', 'planned_time':'Horário planejado da OS.', 'expected_due':'Vencimento de referência congelado na emissão.',
    'performed_date':'Data informada para a realização.', 'performed_time':'Horário informado para a realização.',
    'recurrence_basis':'Regra de cálculo do próximo ciclo: calendário planejado ou data da execução.',
    'assigned_name':'Nome do técnico previsto preservado na OS.', 'executor_name':'Nome do executor preservado no encerramento.',
    'kind':'Categoria do anexo: PHOTO ou MANUAL.', 'filename':'Nome original do anexo.', 'mime_type':'Tipo MIME validado do arquivo.',
    'content':'Conteúdo binário do anexo.', 'size_bytes':'Tamanho do arquivo em bytes.',
    'quantity':'Quantidade solicitada/comprada; limites e positividade são validados no formulário.',
    'minimum_stock':'Parâmetro de estoque mínimo.', 'maximum_stock':'Parâmetro de estoque máximo.', 'reorder_point':'Parâmetro de ponto de reposição.',
    'problem':'Descrição do problema preservada na OS.', 'root_cause':'Diagnóstico da causa raiz.', 'corrective_action':'Solução corretiva registrada.',
    'preventive_action':'Ação para evitar repetição do problema; não é uma programação no calendário.',
    'started_at':'Início efetivo do atendimento técnico.', 'finished_at':'Instante do encerramento.',
    'downtime_seconds':'Duração da parada da OS em segundos, da abertura ao fechamento.',
    'fiscal_status':'Situação da validação fiscal interna da ficha.', 'ncm':'Classificação NCM a validar pela área fiscal.',
    'purchase_type':'Compra nacional ou importação.', 'submitted_at':'Instante do encaminhamento para aprovação.', 'decided_at':'Instante da decisão do gestor.',
}


def purpose(table):
    """Descrições próprias para tabelas do framework evitam confundir permissões nativas com perfis da API."""
    return DESCRIPTIONS.get(table['name'], table['purpose'] or '')


def foreign_keys(table):
    return [constraint for constraint in table['constraints'] if constraint['kind'] == 'f']


def keys(table, column):
    """As marcações PK/FK/UNIQUE usam as definições reais, incluindo a PK composta da compatibilidade."""
    marks = []
    for constraint in table['constraints']:
        match = re.search(r'\(([^)]+)\)', constraint['definition'])
        columns = [value.strip(' "') for value in match.group(1).split(',')] if match else []
        if column in columns:
            label = {'p':'PK','f':'FK','u':'UNIQUE'}.get(constraint['kind'])
            if label:
                if constraint['kind'] == 'u' and len(columns) > 1:
                    label = 'UNIQUE*'
                marks.append(label)
    return ', '.join(marks)


def hint(column):
    if column.get('orm_relation'):
        relation = column['orm_relation']
        return f'Referencia {relation["table"]}.{relation["column"]}; exclusão pelo ORM: {relation["on_delete"]}.'
    return FIELD_HINTS.get(column['name'], str(column.get('label') or column['name']).replace('_',' ').capitalize() + '.')


def sql_type(column):
    if column['type'] == 'character varying':
        return f'varchar({column["length"]})'
    if column['type'] == 'numeric':
        return f'numeric({column["precision"]},{column["scale"]})'
    return {'timestamp with time zone':'timestamptz','time without time zone':'time'}.get(column['type'], column['type'])


RELATIONS = [(table, constraint) for table in TABLES for constraint in foreign_keys(table)]
CAPTURE = DATA['captured_at'][:19].replace('T',' ') + ' · America/Manaus'


def mermaid():
    """O ER completo lista chaves e cardinalidades; os demais campos ficam no dicionário para manter o desenho legível."""
    lines = ['erDiagram']
    for table in TABLES:
        lines.append(f'    {table["name"]} {{')
        for column in table['columns']:
            marks = keys(table,column['name'])
            if marks:
                lines.append(f'        {column["pg_type"]} {column["name"]} {marks.replace("UNIQUE*", "UK").replace("UNIQUE", "UK")}')
        lines.append('    }')
    for table, constraint in RELATIONS:
        columns = re.search(r'FOREIGN KEY \(([^)]+)\)',constraint['definition']).group(1)
        col = next((column for column in table['columns'] if column['name'] == columns.strip('"')),None)
        optional = col and col['nullable']
        # Participar de uma chave composta não torna a FK única sozinha: compatibilidade e agendas continuam N:N/1:N.
        unique = False
        if col:
            for rule in table['constraints']:
                match = re.search(r'\(([^)]+)\)',rule['definition'])
                members = [value.strip(' "') for value in match.group(1).split(',')] if match else []
                if rule['kind'] in ('p','u') and members == [col['name']]:
                    unique = True
        lines.append(f'    {constraint["target"]} {"|o" if optional else "||"}--{"o|" if unique else "o{"} {table["name"]} : "{columns}"')
    return '\n'.join(lines)+'\n'


def markdown():
    """O arquivo técnico é texto versionável e pode ser lido sem abrir a apresentação HTML."""
    lines = ['# MANTIS �?" Mapeamento PostgreSQL', '', f'Captura: {CAPTURE}. Banco `{DATA["database"]}`, PostgreSQL {DATA["server_version"]}, schema `{DATA["schema"]}`.',
        '', f'Inventário físico: {len(TABLES)} tabelas, {sum(len(table["columns"]) for table in TABLES)} colunas e {len(RELATIONS)} FKs. {len(BUSINESS)} tabelas de negócio e {len(TABLES)-len(BUSINESS)} de infraestrutura.',
        '', 'Consulta de metadados e contagens em transação REPEATABLE READ / READ ONLY. Não exporta linhas, hashes, credenciais, contatos ou anexos.',
        '', '## Arquitetura e escopo', '', 'Angular �?' API JSON Django �?' ORM/psycopg �?' PostgreSQL. O navegador não se conecta diretamente ao banco. O Express é legado e não participa do fluxo atual.',
        '', 'A implantação local declarada usa postgres:17-alpine, host 127.0.0.1:5434 �?' contêiner:5432 e volume mantis-django_mantis_django_pgdata. Isso descreve o Compose do projeto; o catálogo foi conferido na conexão Django ativa.',
        '', 'O calendário provisório 2026 está em maintenance/document_templates/preventive_calendar_2026.json, fora do PostgreSQL. Não cria máquinas, usuários, agendas ou OS. As agendas reais, inclusive 2027, usam equipment_preventives e preventive_orders.',
        '', '## Módulos e tabelas', '', '| Módulo | Tabelas |', '|---|---|']
    for module, names in DATA['modules'].items():
        lines.append(f'| {module} | '+', '.join(f'`{name}`' for name in names)+' |')
    lines += ['', '## Integridade: aplicação e banco', '',
        '- PK, FK, UNIQUE, CHECK e índices apresentados abaixo foram lidos do PostgreSQL instalado.', '- UNIQUE* indica chave composta: a unicidade vale para a combinação das colunas, não para cada coluna isoladamente.',
        '- PROTECT e CASCADE nos campos Django são políticas do ORM. Confira a definição SQL efetiva: não se deve apresentar PROTECT como cláusula PostgreSQL, nem supor ON DELETE CASCADE físico.',
        '- choices dos modelos orientam validação na aplicação; não constituem, por si só, CHECK SQL.',
        '- Defaults SQL vazios não significam ausência de default na aplicação: vários valores são preenchidos pelo Python.',
        '- Transações e select_for_update protegem fluxos de alocação, preventiva e aprovação; não são triggers.',
        '- Índice único parcial one_open_preventive_order impede duas OS abertas para a mesma agenda.',
        '- Não foram encontradas views nem triggers de usuário no schema public consultado.',
        '', '## Dicionário de dados completo']
    for table in TABLES:
        lines += ['', f'### {table["name"]}', '', f'**Módulo:** {table["module"]} · **Modelo:** {table["model"] or "�?""} · **Registros na captura:** {table["rows"]}.', '',purpose(table),'']
        if table['name'] in NOTES:
            lines += [NOTES[table['name']], '']
        lines += ['| Coluna física | Tipo PostgreSQL | NULL | Chave | Significado / vínculo |', '|---|---|---|---|---|']
        for column in table['columns']:
            lines.append(f'| `{column["name"]}` | `{sql_type(column)}` | {"Sim" if column["nullable"] else "Não"} | {keys(table,column["name"]) or "�?""} | {hint(column).replace("|","/")} |')
        choices = [(column['name'],column.get('choices')) for column in table['columns'] if column.get('choices')]
        if choices:
            lines += ['', '**Valores declarados no ORM (não implicam CHECK SQL):**']
            for name, values in choices:
                lines.append(f'- `{name}`: '+', '.join(f'`{key}` ({label})' for key,label in values)+'.')
        lines += ['', '**Restrições físicas:**', '']
        lines += [f'- `{constraint["name"]}`: `{constraint["definition"]}`.' for constraint in table['constraints']]
        lines += ['', '**Índices físicos:**', '']
        lines += [f'- `{index["definition"]}`.' for index in table['indexes']]
    lines += ['', '## Evolução do esquema', '', f'Migrações aplicadas: {len(DATA["applied_migrations"])}. Pendentes: {len(DATA["pending_migrations"])}. Tabelas/colunas ausentes nos modelos comparados: {len(DATA["missing_model_tables"])} / {len(DATA["missing_model_columns"])}.', '']
    lines += [f'- `{migration}`' for migration in DATA['applied_migrations']]
    lines += ['', '## Fontes e reprodução', '', '- maintenance/models.py: modelo lógico, rótulos e políticas ORM.', '- maintenance/api.py, services.py, preventive.py, preventive_orders.py e preventive_schedule.py: fluxos e validações.', '- maintenance/urls.py e frontend/src/app/app.routes.ts: módulos e rotas.', '- config/settings.py e docker-compose.yml: integração e implantação declarada; segredos não foram exportados.', '- Catálogos pg_class, pg_constraint, pg_indexes, information_schema.columns e django_migrations: evidência física instalada.', '', 'Atualizar o catálogo:', '', '```powershell', 'cd backend', r'.\.venv\Scripts\python.exe manage.py map_database --output ..\..\docs\banco-postgres', '```', '', 'Gerar a apresentação após atualizar o catálogo:', '', '```powershell', r'.\.venv\Scripts\python.exe ..\..\docs\banco-postgres\generate_presentation.py', '```']
    return '\n'.join(lines)+'\n'


def overview_svg():
    """Visão conceitual resumida, com rótulos legíveis; o ER completo é entregue em arquivo separado."""
    nodes = [('sectors','Setores',30,30),('lines','Linhas SMT',280,30),('users','Usuários',800,30),('equipment_types','Tipos de equipamento',30,170),('equipment','Equipamento',390,170),('work_orders','OS corretivas',800,170),('spare_parts','Catálogo de peças',30,330),('equipment_preventives','Agendas preventivas',390,330),('spare_purchase_requests','Solicitações de compra',800,330)]
    edges = [(230,60,280,60),(380,90,490,170),(230,200,390,200),(590,200,800,200),(490,230,490,330),(900,90,900,170),(900,230,900,330)]
    svg = ['<svg viewBox="0 0 1040 430" role="img" aria-label="Visão resumida dos relacionamentos do MANTIS"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#a8b3c4"/></marker></defs>']
    for x1,y1,x2,y2 in edges:
        svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#a8b3c4" stroke-width="2" marker-end="url(#arrow)" fill="none"/>')
    svg.append('<path d="M230,360 L250,360 L250,400 L900,400 L900,390" stroke="#a8b3c4" stroke-width="2" marker-end="url(#arrow)" fill="none"/><text x="560" y="394" fill="#65758b" font-size="10">via itens da compra</text>')
    for name,label,x,y in nodes:
        color = '#fff1f3' if name=='equipment' else '#f7f9fc'
        svg.append(f'<a href="#{name}"><rect x="{x}" y="{y}" width="200" height="60" rx="10" fill="{color}" stroke="#d5dde8"/><text x="{x+12}" y="{y+24}" fill="#253347" font-size="13" font-weight="700">{label}</text><text x="{x+12}" y="{y+43}" fill="#65758b" font-size="10">{name}</text></a>')
    svg.append('<text x="30" y="420" fill="#65758b" font-size="11">Visão resumida por módulo. As FKs e as tabelas intermediárias estão detalhadas no catálogo e no ER completo.</text></svg>')
    return ''.join(svg)


def html():
    e = escape
    sections = []
    for table in TABLES:
        column_rows = []
        for column in table['columns']:
            column_rows.append(f'<tr><td><code>{e(column["name"])}</code><small>{e(str(column.get("label", "")))}</small></td><td><code>{e(sql_type(column))}</code></td><td>{"Sim" if column["nullable"] else "Não"}</td><td><b class="key">{e(keys(table,column["name"]))}</b></td><td>{e(hint(column))}</td></tr>')
        constraints = ''.join(f'<li><code>{e(constraint["name"])}</code><pre>{e(constraint["definition"])}</pre></li>' for constraint in table['constraints'])
        indexes = ''.join(f'<li><pre>{e(index["definition"])}</pre></li>' for index in table['indexes'])
        choices = ''.join(f'<p><code>{e(column["name"])}</code>: {e(", ".join(str(key)+" ("+str(label)+")" for key,label in column.get("choices",[])))}</p>' for column in table['columns'] if column.get('choices'))
        search = e(' '.join([table['name'],table['module'],purpose(table)]+[column['name'] for column in table['columns']]),quote=True)
        sections.append(f'''<details class="table-card" id="{e(table['name'])}" data-module="{e(table['module'])}" data-search="{search}"><summary><span><strong>{e(table['name'])}</strong><small>{e(table['module'])} · {e(table['model'] or 'Infraestrutura')}</small></span><span class="table-stat">{len(table['columns'])} campos · {table['rows']} registros</span></summary><div class="table-body"><p>{e(purpose(table))}</p><p class="explanation">{e(NOTES.get(table['name'],''))}</p><div class="table-scroll"><table><thead><tr><th>Coluna</th><th>Tipo SQL</th><th>NULL</th><th>Chave</th><th>Significado e vínculo</th></tr></thead><tbody>{''.join(column_rows)}</tbody></table></div>{'<h4>Valores no ORM �?" validação da aplicação</h4>'+choices if choices else ''}<h4>Restrições instaladas no PostgreSQL</h4><ul class="sql-list">{constraints}</ul><details class="indexes"><summary>Ver índices físicos ({len(table['indexes'])})</summary><ul class="sql-list">{indexes}</ul></details></div></details>''')
    modules = ''.join(f'<article class="module-card"><span>{len(names)} {"tabela" if len(names) == 1 else "tabelas"}</span><h3>{e(group)}</h3><ul>'+''.join(f'<li><a href="#{name}">{name}</a></li>' for name in names)+'</ul></article>' for group,names in DATA['modules'].items())
    options = ''.join(f'<option>{e(group)}</option>' for group in list(DATA['modules'])+['Infraestrutura Django'])
    fkrows = ''.join(f'<tr><td><a href="#{table["name"]}">{table["name"]}</a></td><td><code>{e(constraint["definition"])}</code></td><td><a href="#{constraint["target"]}">{constraint["target"]}</a></td></tr>' for table,constraint in RELATIONS)
    flows = [
        ('01','Cadastrar e alocar','sectors �?' lines �?' equipment','O equipamento referencia tipo e setor. A alocação atualiza linha/posição e grava equipment_movements na mesma transação.'),
        ('02','Atender uma OS corretiva','problem_types �?' work_orders �?' line_pendencies','A conta abre a OS; o técnico confirma sua própria identidade para iniciar. O fechamento registra ações e tempo de parada. Pendências têm resolução própria.'),
        ('03','Executar uma preventiva','preventive_checklists �?' equipment_preventives �?' preventive_orders �?' preventive_executions','A agenda escolhe o roteiro do tipo ou um roteiro específico. A OS congela dados e atividades; somente sua conclusão atualiza o próximo vencimento.'),
        ('04','Solicitar peças e comprar','spare_parts �?' spare_purchase_requests �?' spare_purchase_request_items �?' spare_purchase_events','A lista geral cria uma compra com vários itens, sem vínculo obrigatório com máquina. O envio congela fichas; o gestor designado registra a decisão.'),
    ]
    flowhtml = ''.join(f'<article class="flow"><span>{number}</span><div><h3>{title}</h3><code>{chain}</code><p>{text}</p></div></article>' for number,title,chain,text in flows)
    raw = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MANTIS · Mapeamento PostgreSQL</title><style>__CSS__</style></head><body>
<aside class="sidebar"><div class="brand">MANTIS<span>ARQUITETURA DE DADOS</span></div><nav><a href="EXPORT_FORMATS.html">Arquivos para aplicativos</a><a href="#visao">Visão geral</a><a href="#arquitetura">Arquitetura</a><a href="#modulos">Módulos</a><a href="#fluxos">Fluxos do sistema</a><a href="#integridade">Integridade e limites</a><a href="#dicionario">Dicionário de dados</a><a href="#relacoes">Todas as relações</a><a href="#evidencias">Evidências</a></nav><button onclick="window.print()">Imprimir / salvar PDF</button><small>Captura verificada em<br>{e(CAPTURE)}</small></aside>
<main><section id="visao"><div class="eyebrow">MAPEAMENTO DO SISTEMA · POSTGRESQL {e(DATA['server_version'])}</div><h1>Como os dados<br>do MANTIS se conectam</h1><p class="lead">Do cadastro da máquina à manutenção e à compra de peças: uma visão para apresentação e um catálogo técnico completo do banco instalado.</p><div class="metrics"><div><b>{len(BUSINESS)}</b><span>tabelas do MANTIS</span></div><div><b>{len(TABLES)-len(BUSINESS)}</b><span>tabelas Django</span></div><div><b>{sum(len(table['columns']) for table in TABLES)}</b><span>colunas físicas</span></div><div><b>{len(RELATIONS)}</b><span>chaves estrangeiras</span></div></div><p><a href="EXPORT_FORMATS.html">Abrir opções de arquivos para PowerPoint, PDF e ferramentas de banco</a></p><p class="capture">Banco {e(DATA['database'])} · schema public · metadados e contagens, sem conteúdo dos registros.</p></section>
<section id="arquitetura"><div class="eyebrow">01 · VIS�fO DE PONTA A PONTA</div><h2>Interface, regras e persistência</h2><div class="architecture"><article><span>INTERFACE</span><h3>Angular</h3><p>Telas, seleção de equipamentos e formulários.</p></article><b>�?'</b><article><span>API / REGRAS</span><h3>Django</h3><p>Autenticação, validação, autorização e transações.</p></article><b>�?'</b><article><span>ACESSO A DADOS</span><h3>ORM + psycopg</h3><p>Consultas parametrizadas e modelos versionados.</p></article><b>�?'</b><article><span>BANCO</span><h3>PostgreSQL</h3><p>Tabelas, chaves, índices e integridade referencial.</p></article></div><p>O navegador acessa a API; não recebe credenciais nem faz conexão direta com o PostgreSQL. O Express é legado e não participa da execução atual.</p><div class="diagram">{overview_svg()}</div><div class="note"><b>Persistência fora do banco:</b> o modelo provisório do calendário 2026 é um arquivo JSON autenticado pela API. Ele não cria equipamentos, usuários, agendas nem OS. A programação real usa as tabelas de preventivas.</div></section>
<section id="modulos"><div class="eyebrow">02 · ORGANIZA�?�fO FUNCIONAL</div><h2>Seis áreas, uma base integrada</h2><div class="modules">{modules}</div></section>
<section id="fluxos"><div class="eyebrow">03 · ROTEIRO PARA APRESENTAR</div><h2>Quatro jornadas para explicar o sistema</h2>{flowhtml}<div class="note">Uma solicitação direta em <code>maintenance_part_requisitions</code> não é uma compra nem uma movimentação de estoque. OS corretivas e preventivas são entidades distintas.</div></section>
<section id="integridade"><div class="eyebrow">04 · CONFIABILIDADE DOS DADOS</div><h2>O que o banco garante �?" e o que a API valida</h2><div class="two-cols"><article class="info-card"><h3>No PostgreSQL</h3><ul><li>PKs e FKs preservam identidade e referências.</li><li>UNIQUE evita matrícula, série e patrimônio duplicados conforme o esquema.</li><li>Posição na linha e vínculo linha/posição possuem restrições.</li><li>Índice único parcial impede duas OS preventivas abertas por agenda.</li><li>Anexos e fichas usam BYTEA/JSONB conforme a necessidade.</li></ul></article><article class="info-card"><h3>Na aplicação Django</h3><ul><li>Perfil e linha restringem acesso aos dados.</li><li>Validação de quantidades, arquivos e campos obrigatórios.</li><li>Transações e bloqueios protegem operações concorrentes.</li><li>Estado, responsável e revisão são conferidos no atendimento.</li><li>PROTECT/CASCADE são políticas do ORM; a cláusula SQL real está no dicionário.</li></ul></article></div><div class="note"><b>Limites atuais:</b> parâmetros de estoque não são saldo movimentado; não há auditoria genérica de todas as tabelas. Não foram encontradas views ou triggers de usuário no schema public. Os perfis da API vêm de <code>users.role</code>, não de <code>auth_group</code>. A compatibilidade peça�?"máquina existe no esquema, mas não é utilizada pela aba Spare Parts da preventiva.</div></section>
<section id="dicionario"><div class="eyebrow">05 · DICIONÁRIO COMPLETO</div><h2>Tabelas, campos e restrições</h2><p>PK identifica o registro; FK referencia outra tabela; 1:N indica um registro relacionado a vários. NULL indica ausência permitida no banco. UNIQUE* indica participação em uma chave única composta; não garante unicidade da coluna isolada. Valores de <code>choices</code> são regras do ORM e não implicam CHECK SQL. Contagens retratam a captura; não comprovam uso em produção.</p><div class="dictionary-tools"><label>Pesquisar tabela ou coluna<input id="search" placeholder="Ex.: equipment, serial, preventive..."></label><label>Módulo<select id="module"><option value="">Todos os módulos</option>{options}</select></label><button id="expand">Expandir tabelas</button><button id="collapse">Recolher</button></div><p id="matches" class="capture">{len(TABLES)} tabelas</p>{''.join(sections)}</section>
<section id="relacoes"><div class="eyebrow">06 · RELACIONAMENTOS FÍSICOS</div><h2>As {len(RELATIONS)} chaves estrangeiras instaladas</h2><p>A coluna de destino e as regras de exclusão/adiamento aparecem na definição SQL original.</p><div class="table-scroll"><table><thead><tr><th>Tabela de origem</th><th>Definição PostgreSQL</th><th>Tabela referenciada</th></tr></thead><tbody>{fkrows}</tbody></table></div></section>
<section id="evidencias"><div class="eyebrow">07 · BASE T�?CNICA E ATUALIZA�?�fO</div><h2>Verificado no código e no banco</h2><div class="metrics"><div><b>{len(DATA['applied_migrations'])}</b><span>migrações aplicadas</span></div><div><b>{len(DATA['pending_migrations'])}</b><span>migrações pendentes</span></div><div><b>{len(DATA['missing_model_tables'])}</b><span>tabelas ausentes</span></div><div><b>{len(DATA['missing_model_columns'])}</b><span>colunas ausentes</span></div></div><p>Coleta em transação REPEATABLE READ / READ ONLY. Foram comparados os modelos instalados com as tabelas e colunas do schema public; isso não é uma auditoria completa de índices, desempenho, backup ou permissões operacionais.</p><ul><li><code>maintenance/models.py</code>: entidades e relacionamentos lógicos.</li><li><code>api.py, services.py, preventive*.py</code>: fluxos e regras.</li><li><code>pg_class, pg_constraint, pg_indexes, information_schema</code>: estrutura física observada.</li><li><code>django_migrations</code>: evolução aplicada.</li></ul><p>Compose local declarado: PostgreSQL 17 Alpine, host 127.0.0.1:5434 �?' contêiner:5432, volume <code>mantis-django_mantis_django_pgdata</code>. A conexão efetiva foi a configurada no Django.</p><p><a href="portugues/GUIA_PORTUGUES.html">Guia do banco em português</a> · <a href="portugues/DATA_DICTIONARY.csv">Dicionário de dados</a> · <a href="RELATIONSHIPS.mmd">ER completo em Mermaid</a> · <a href="PRESENTATION_QUERIES.sql">Consultas SQL comentadas</a></p><p class="capture">Não contém senhas, hashes, nomes de usuários, dados de equipamentos ou conteúdo de anexos. Inclui somente metadados e contagens agregadas.</p></section></main><script>__JS__</script></body></html>'''
    css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f6fa;color:#243247;font:15px/1.65 system-ui,-apple-system,Segoe UI,sans-serif}.sidebar{position:fixed;inset:0 auto 0 0;width:235px;background:#131c2b;color:white;padding:30px 22px;display:flex;flex-direction:column;gap:24px}.brand{font-size:29px;font-weight:800;letter-spacing:1px}.brand span{display:block;font-size:9px;letter-spacing:2px;color:#99a7bd}.sidebar nav{display:flex;flex-direction:column;gap:5px}.sidebar a{color:#c5cfdd;padding:8px 10px;text-decoration:none;font-size:12px;border-radius:6px}.sidebar a:hover{background:#253247;color:white}.sidebar small{color:#99a7bd;font-size:10px;margin-top:auto}.sidebar button{background:#c8102e;color:white;border:0}main{margin-left:235px;max-width:1500px;padding:46px 50px}section{scroll-margin-top:24px;margin-bottom:56px}.eyebrow{font-size:10px;font-weight:800;letter-spacing:1.8px;color:#bc1230;margin-bottom:14px}h1{font-size:48px;line-height:1.13;letter-spacing:-1.7px;margin:0 0 22px}h2{font-size:27px;line-height:1.25;letter-spacing:-.6px;margin:0 0 20px}h3{font-size:16px;margin:0 0 8px}h4{font-size:13px;margin:22px 0 9px}p{color:#5d6d83}a{color:#a90e29}.lead{font-size:17px;max-width:760px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0}.metrics>div{padding:20px;background:white;border:1px solid #e2e7ee;border-radius:10px}.metrics b{display:block;font-size:31px;line-height:1.2;color:#b6112e}.metrics span{font-size:11px;color:#65758b}.capture{font-size:11px;color:#718097}.architecture{display:flex;gap:12px;align-items:center}.architecture article{background:white;border:1px solid #e2e7ee;padding:17px;border-radius:10px;flex:1;min-width:0}.architecture span{font-size:9px;font-weight:700;color:#8a98ab}.architecture p{font-size:11px;line-height:1.5;margin:0}.architecture b{color:#a9b4c4}.diagram{background:white;border:1px solid #e2e7ee;padding:14px;border-radius:12px;margin:24px 0}.diagram svg{display:block;width:100%;height:auto}.modules{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.module-card,.info-card{background:white;border:1px solid #e2e7ee;border-radius:10px;padding:22px}.module-card>span{font-size:10px;color:#b6112e;font-weight:700}.module-card h3{margin:6px 0 12px}.module-card ul{padding:0;list-style:none;margin:0}.module-card a{font-size:11px;text-decoration:none;overflow-wrap:anywhere;color:#52677f}.flow{display:flex;align-items:start;gap:18px;background:white;border:1px solid #e2e7ee;padding:22px;border-radius:10px;margin:12px 0}.flow>span{font-size:22px;font-weight:800;color:#c8102e}.flow code{font-size:11px;overflow-wrap:anywhere}.flow p{font-size:13px;margin-bottom:0}.note{padding:18px 20px;background:#eaf0f8;border-left:3px solid #879fbd;border-radius:0 8px 8px 0;font-size:12px;color:#415670;margin:20px 0}.two-cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}.info-card li{font-size:12px;margin-bottom:8px}.info-card ul{padding-left:18px}.dictionary-tools{display:flex;gap:12px;align-items:end;position:sticky;top:0;padding:14px;background:#f4f6faf5;z-index:3;border-bottom:1px solid #e2e7ee}.dictionary-tools label{display:flex;flex-direction:column;gap:6px;font-size:11px;font-weight:600;flex:1}input,select,button{font:inherit;font-size:12px;border:1px solid #d2dbe7;border-radius:7px;background:white;padding:10px 12px;color:#344860}button{cursor:pointer;white-space:nowrap}button:hover{filter:brightness(.96)}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid #c8102e;outline-offset:3px}.table-card{border:1px solid #dce4ee;border-radius:9px;background:white;margin:10px 0;scroll-margin-top:95px}.table-card>summary{padding:15px 18px;cursor:pointer;display:flex;justify-content:space-between;gap:15px;align-items:center;list-style:none}.table-card>summary:after{content:'+';font-weight:700;color:#a0aec0}.table-card[open]>summary:after{content:'�^''}.table-card summary strong{font-size:13px;overflow-wrap:anywhere}.table-card summary small{display:block;font-size:10px;color:#7c8ba1}.table-stat{font-size:10px;color:#65758b;margin-left:auto;white-space:nowrap}.table-body{padding:0 18px 20px}.table-body p{font-size:12px}.explanation{background:#f7f9fc;padding:12px;border-radius:7px}.explanation:empty{display:none}.table-scroll{overflow:auto;border:1px solid #e6ebf1;border-radius:7px}table{border-collapse:collapse;width:100%;font-size:11px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #edf1f6;padding:10px 12px}th{background:#f7f9fc;color:#64748b;font-size:10px;white-space:nowrap}td small{display:block;font-size:9px;color:#8a98ab}code{font-family:Consolas,monospace;font-size:.92em}pre{font:11px/1.6 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fb;padding:9px;border-radius:5px}.sql-list{list-style:none;padding:0}.sql-list>li{font-size:10px;margin-bottom:10px}.key{font-size:9px;color:#a90e29}.indexes summary,.source-review summary{font-size:12px;cursor:pointer}[hidden]{display:none!important}@media(max-width:1050px){.sidebar{width:190px;padding:22px 14px}main{margin-left:190px;padding:35px 25px}.modules{grid-template-columns:1fr 1fr}.architecture{gap:6px}.architecture article{padding:10px}.dictionary-tools{flex-wrap:wrap}}@media(max-width:750px){.sidebar{position:relative;width:auto;padding:18px}.sidebar nav{flex-direction:row;overflow:auto;gap:4px}.sidebar nav a{white-space:nowrap}.sidebar small{display:none}main{margin:0;padding:25px 18px}h1{font-size:34px}.metrics{grid-template-columns:1fr 1fr}.architecture{flex-direction:column}.architecture article{width:100%}.architecture>b{transform:rotate(90deg)}.two-cols,.modules{grid-template-columns:1fr}.dictionary-tools{position:static}.table-stat{display:none}.dictionary-tools label{min-width:180px}}@media print{@page{size:A4 landscape;margin:14mm}.sidebar,.dictionary-tools{display:none}main{margin:0;padding:0;max-width:none}body{background:white;font-size:11px}section{break-before:page;margin-bottom:20px}section:first-child{break-before:avoid}.metrics{gap:8px}.table-card,.flow,.module-card{break-inside:avoid}.table-card{border-color:#ccc}h1{font-size:34px}h2{font-size:23px}.table-scroll{overflow:visible}a{color:inherit;text-decoration:none}.table-card[hidden]{display:block!important}pre{font-size:9px}.modules{grid-template-columns:repeat(3,1fr)}.table-stat{display:block}}'''
    js = '''const cards=[...document.querySelectorAll('.table-card')];const search=document.getElementById('search');const moduleSelect=document.getElementById('module');function filter(){const q=search.value.toLocaleLowerCase('pt-BR').trim();let n=0;cards.forEach(card=>{const ok=(!moduleSelect.value||card.dataset.module===moduleSelect.value)&&(!q||card.dataset.search.toLocaleLowerCase('pt-BR').includes(q));card.hidden=!ok;if(ok){n++;if(q)card.open=true}});document.getElementById('matches').textContent=n+' tabela(s) encontrada(s)'}search.addEventListener('input',filter);moduleSelect.addEventListener('change',filter);document.getElementById('expand').onclick=()=>cards.filter(c=>!c.hidden).forEach(c=>c.open=true);document.getElementById('collapse').onclick=()=>cards.forEach(c=>c.open=false);function reveal(){const id=decodeURIComponent(location.hash.slice(1));const target=document.getElementById(id);if(target&&target.classList.contains('table-card')){search.value='';moduleSelect.value='';filter();target.open=true;target.scrollIntoView({behavior:'smooth',block:'start'})}}window.addEventListener('hashchange',reveal);document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',()=>setTimeout(reveal,0)));let beforePrint=[];window.addEventListener('beforeprint',()=>{beforePrint=cards.map(c=>[c,c.open,c.hidden]);cards.forEach(c=>{c.open=true;c.hidden=false})});window.addEventListener('afterprint',()=>beforePrint.forEach(([c,o,h])=>{c.open=o;c.hidden=h}));reveal();'''
    return raw.replace('__CSS__',css).replace('__JS__',js)


if __name__ == '__main__':

    (ROOT/'RELATIONSHIPS.mmd').write_text(mermaid(),encoding='utf-8')
    (ROOT/'DATABASE_PRESENTATION.html').write_text(html(),encoding='utf-8')
    print(f'Gerados: apresentação HTML, dicionário de {len(TABLES)} tabelas e ER de {len(RELATIONS)} FKs.')

