"""ER didático gerado do catálogo físico, sem criar ou alterar tabelas.

As figuras resumem as ligações principais. O inventário completo conserva todas
as FKs, inclusive as opcionais, as chaves compostas e as referências de autoria.
"""
import html
import json
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


ENTITY_NAMES = {
    'setores':'Setores', 'linhas':'Linhas de produção', 'tipos_equipamento':'Tipos de equipamento',
    'equipamentos':'Equipamentos', 'usuarios':'Usuários', 'anexos_equipamento':'Fotos e manuais',
    'movimentacoes_equipamento':'Movimentações', 'roteiros_preventiva':'Roteiros de preventiva',
    'agendas_preventiva':'Programação preventiva', 'ordens_preventiva':'OS preventivas',
    'execucoes_preventiva':'Execuções preventivas', 'tipos_problema':'Tipos de problema',
    'ordens_servico':'OS corretivas', 'pendencias_linha':'Pendências da linha',
    'solicitacoes_pecas_manutencao':'Solicitações de peças', 'pecas_reposicao':'Catálogo de peças',
    'fichas_tecnicas_pecas':'Fichas técnicas das peças', 'solicitacoes_compra':'Solicitações de compra',
    'itens_solicitacao_compra':'Itens da compra', 'eventos_solicitacao_compra':'Histórico da compra',
    'compatibilidade_pecas_equipamentos':'Compatibilidade antiga',
}

DJANGO_NAMES = {
    'auth_group':'Grupos de permissões',
    'auth_group_permissions':'Permissões dos grupos',
    'auth_permission':'Permissões do Django',
    'django_content_type':'Tipos de registro do Django',
    'django_migrations':'Histórico de migrações',
}


def entity_name(name):
    return ENTITY_NAMES.get(name, DJANGO_NAMES.get(name, name))

# Os pares são (tabela filha, coluna FK). Nenhuma linha conceitual é inventada.
VIEWS = [
    {'id':'visao-geral', 'titulo':'Comece por aqui', 'cor':'#ba1735',
     'texto':'O equipamento é o ponto central. A preventiva segue uma programação; a corretiva nasce de um problema. São ordens em tabelas diferentes.',
     'nos':{'setores':(0,0),'linhas':(1,0),'tipos_equipamento':(0,1),'equipamentos':(1,1),'agendas_preventiva':(2,1),'ordens_servico':(1,2),'ordens_preventiva':(2,2)},
     'ligacoes':[('linhas','setor_id'),('equipamentos','linha_id'),('equipamentos','tipo_equipamento_id'),('agendas_preventiva','equipamento_id'),('ordens_servico','equipamento_id'),('ordens_preventiva','agenda_id')],
     'principais':[], 'exemplo':'Exemplo ilustrativo: uma máquina cadastrada pode ter uma agenda mensal. A cada ciclo pode ser emitida uma OS preventiva. Uma falha nessa mesma máquina pode originar uma OS corretiva.'},
    {'id':'estrutura', 'titulo':'Estrutura industrial', 'cor':'#176b76',
     'texto':'Primeiro cadastre o setor e o tipo; depois, o equipamento. A linha organiza a alocação atual da máquina.',
     'nos':{'setores':(0,0),'linhas':(1,0),'tipos_equipamento':(0,1),'equipamentos':(1,1)},
     'ligacoes':[('linhas','setor_id'),('equipamentos','linha_id'),('equipamentos','tipo_equipamento_id'),('equipamentos','setor_id')],
     'principais':['setores','linhas','tipos_equipamento','equipamentos'],
     'exemplo':'A máquina pode estar sem linha e sem posição, disponível no repositório. Setor proprietário e linha de alocação são informações diferentes. O banco permite alguns vínculos vazios que o formulário pode exigir no cadastro.'},
    {'id':'preventivas', 'titulo':'Manutenção preventiva', 'cor':'#6655a2',
     'texto':'O roteiro pertence ao tipo de equipamento. A agenda pertence à máquina. A OS preserva o que foi emitido; a execução registra o que foi concluído.',
     'nos':{'tipos_equipamento':(0,0),'equipamentos':(1,0),'agendas_preventiva':(2,0),'roteiros_preventiva':(0,1),'ordens_preventiva':(1,1),'execucoes_preventiva':(2,1)},
     'ligacoes':[('equipamentos','tipo_equipamento_id'),('roteiros_preventiva','tipo_equipamento_id'),('agendas_preventiva','equipamento_id'),('ordens_preventiva','agenda_id'),('execucoes_preventiva','agenda_id'),('execucoes_preventiva','ordem_preventiva_id')],
     'principais':['roteiros_preventiva','agendas_preventiva','ordens_preventiva','execucoes_preventiva'],
     'exemplo':'Uma agenda pode ter várias OS ao longo do tempo, mas o banco permite somente uma ABERTA por agenda. Cada OS pode ter zero ou uma execução. O roteiro é herdado pela aplicação: não há FK direta da agenda para o roteiro. O calendário provisório de 2026 é um arquivo JSON, fora destas tabelas.'},
    {'id':'corretivas', 'titulo':'Manutenção corretiva', 'cor':'#a45a12',
     'texto':'A OS registra a falha da máquina. Ela pode gerar pendências e solicitações diretas de peças, sem criar uma compra automaticamente.',
     'nos':{'equipamentos':(0,0),'ordens_servico':(1,0),'pendencias_linha':(2,0),'tipos_problema':(0,1),'solicitacoes_pecas_manutencao':(1,1),'pecas_reposicao':(2,1)},
     'ligacoes':[('ordens_servico','equipamento_id'),('ordens_servico','tipo_problema_id'),('pendencias_linha','ordem_servico_id'),('solicitacoes_pecas_manutencao','ordem_servico_id'),('solicitacoes_pecas_manutencao','peca_id')],
     'principais':['tipos_problema','ordens_servico','pendencias_linha','solicitacoes_pecas_manutencao'],
     'exemplo':'Concluir a OS não resolve suas pendências automaticamente. Solicitar uma peça para manutenção não significa registrar uma retirada de estoque nem abrir uma solicitação de compra.'},
    {'id':'compras', 'titulo':'Peças e compras', 'cor':'#2454a3',
     'texto':'As peças ficam em um catálogo geral. A compra reúne itens; cada item escolhe uma peça e informa a quantidade.',
     'nos':{'usuarios':(0,0),'solicitacoes_compra':(1,0),'eventos_solicitacao_compra':(2,0),'pecas_reposicao':(0,1),'itens_solicitacao_compra':(1,1),'fichas_tecnicas_pecas':(0,2)},
     'ligacoes':[('solicitacoes_compra','solicitante_id'),('itens_solicitacao_compra','solicitacao_id'),('itens_solicitacao_compra','peca_id'),('eventos_solicitacao_compra','solicitacao_id'),('fichas_tecnicas_pecas','peca_id')],
     'principais':['pecas_reposicao','fichas_tecnicas_pecas','solicitacoes_compra','itens_solicitacao_compra','eventos_solicitacao_compra'],
     'exemplo':'Uma compra pode ser montada sem máquina e sem OS. Quando preenchida, ordem_servico_id aponta para a OS corretiva. No rascunho a compra pode ter zero itens; para enviar, a aplicação exige pelo menos um. A peça pode ter zero ou uma ficha técnica.'},
    {'id':'historico', 'titulo':'Acesso e histórico', 'cor':'#53677e',
     'texto':'Usuários identificam os responsáveis. Anexos pertencem ao equipamento; movimentações preservam de onde a máquina saiu e para onde foi.',
     'nos':{'usuarios':(0,0),'equipamentos':(1,0),'movimentacoes_equipamento':(2,0),'linhas':(0,1),'anexos_equipamento':(1,1)},
     'ligacoes':[('usuarios','linha_id'),('anexos_equipamento','equipamento_id'),('movimentacoes_equipamento','equipamento_id')],
     'principais':['usuarios','anexos_equipamento','movimentacoes_equipamento'],
     'exemplo':'A linha do usuário pode estar vazia no banco; uma restrição exige linha para o perfil OPERADOR. Em movimentações, origem e destino podem estar vazios. Os vínculos de autoria estão listados abaixo, separados da estrutura principal.'},
    {'id':'compatibilidade', 'titulo':'Compatibilidade existente', 'cor':'#6b7280',
     'texto':'Esta associação já existe no esquema, mas não é exigida nem gravada pela aba Spare Parts da preventiva.',
     'nos':{'equipamentos':(0,0),'compatibilidade_pecas_equipamentos':(1,0),'pecas_reposicao':(2,0)},
     'ligacoes':[('compatibilidade_pecas_equipamentos','equipamento_id'),('compatibilidade_pecas_equipamentos','peca_id')],
     'principais':['compatibilidade_pecas_equipamentos'],
     'exemplo':'A chave primária é a combinação equipamento_id + peca_id. Ela impede repetir o mesmo par; não torna uma peça exclusiva de uma máquina. O catálogo e a lista de compra continuam independentes deste vínculo.'},
]


def complete_views(tables, relations):
    """O inventário torna visíveis todas as entidades, inclusive as de apoio.

    A página inicial é um índice de entidades; as linhas de relacionamento são
    mantidas nas páginas por área e na lista completa, para não encobrir os nomes.
    """
    columns = [
        ['setores','linhas','tipos_equipamento','equipamentos','usuarios','anexos_equipamento','movimentacoes_equipamento'],
        ['roteiros_preventiva','agendas_preventiva','ordens_preventiva','execucoes_preventiva','tipos_problema','ordens_servico','pendencias_linha','solicitacoes_pecas_manutencao'],
        ['pecas_reposicao','fichas_tecnicas_pecas','solicitacoes_compra','itens_solicitacao_compra','eventos_solicitacao_compra','compatibilidade_pecas_equipamentos'],
    ]
    inventory = {'id':'todas-entidades','titulo':'Todas as entidades — 21', 'cor':'#ba1735',
        'texto':'Aqui estão todas as 21 entidades de negócio, incluindo usuários, documentos, movimentações, roteiros, execuções, pendências e compras. As conexões são detalhadas nas páginas por área.',
        'nos':{name:(column,row) for column,names in enumerate(columns) for row,name in enumerate(names)},
        'ligacoes':[], 'principais':[], 'cabecalhos':['Estrutura, usuários e histórico','Manutenção preventiva e corretiva','Peças e compras'],
        'exemplo':'Esta página é o índice visual completo: esquerda = estrutura, acesso e histórico; centro = manutenção; direita = peças e compras. Para seguir as linhas de relacionamento, escolha a página da área. As cinco tabelas internas do Django têm uma página própria.'}
    assert set(inventory['nos'])=={name for name in tables if name not in DJANGO_NAMES}
    internal = {'id':'infraestrutura','titulo':'Tabelas internas — 5', 'cor':'#53677e',
        'texto':'Estas cinco entidades são mantidas pelo Django. Seus nomes físicos continuam originais, mas os títulos abaixo explicam a função em português. Não substituem os perfis Administrador, Técnico e Operador do MANTIS.',
        'nos':{'auth_group':(0,0),'auth_group_permissions':(1,0),'auth_permission':(2,0),'django_content_type':(2,1),'django_migrations':(0,1)},
        'ligacoes':[(r['child'],r['column']) for r in relations if r['infrastructure']],
        'principais':list(DJANGO_NAMES),
        'exemplo':'Grupos e permissões são estruturas nativas do Django. Tipos de registro identificam os modelos. Histórico de migrações registra quais versões da estrutura foram aplicadas; ele não guarda o histórico de edições dos equipamentos.'}
    return [inventory,*VIEWS,internal]


def constraint_columns(definition):
    match = re.search(r'\(([^)]+)\)', definition)
    return [name.strip(' "') for name in match[1].split(',')] if match else []


def read_relations(catalog):
    """Unicidade composta e índice parcial não transformam uma FK isolada em 1:1."""
    tables = {table['name']:table for table in catalog['tables']}
    relations = []
    for table in sorted(tables.values(), key=lambda value:value['name']):
        for rule in sorted(table['constraints'], key=lambda value:value['name']):
            if rule['kind'] != 'f':
                continue
            fields = constraint_columns(rule['definition'])
            assert len(fields) == 1, 'Este catálogo deve ter FKs de uma coluna.'
            column = next(column for column in table['columns'] if column['name'] == fields[0])
            unique = any(constraint['kind'] in ('p','u') and constraint_columns(constraint['definition']) == fields for constraint in table['constraints'])
            relations.append({'id':f'R{len(relations)+1:02}', 'child':table['name'], 'parent':rule['target'],
                             'column':fields[0], 'optional':column['nullable'], 'unique':unique,
                             'infrastructure':table['module']=='Infraestrutura Django'})
    return tables, relations


def relation_sentence(relation):
    parent = entity_name(relation['parent'])
    child = entity_name(relation['child'])
    return (f'Cada registro de {child} aponta para {"zero ou um" if relation["optional"] else "exatamente um"} registro de {parent}. '
            f'Cada registro de {parent} pode ser referenciado por {"zero ou um registro" if relation["unique"] else "zero, um ou vários registros"} de {child}.')


def mermaid(tables, relations, names):
    lines = ['%% Gerado do catálogo físico. PK = chave primária; FK = referência a outra tabela.', 'erDiagram']
    for name in names:
        table = tables[name]
        pk = next((constraint_columns(rule['definition']) for rule in table['constraints'] if rule['kind']=='p'), [])
        fks = {relation['column'] for relation in relations if relation['child']==name}
        lines.append(f'    {name} {{')
        for column in table['columns']:
            markers = (['PK'] if column['name'] in pk else []) + (['FK'] if column['name'] in fks else [])
            keys = (' '+', '.join(markers)) if markers else ''
            lines.append(f'        {column["pg_type"]} {column["name"]}{keys}')
        lines.append('    }')
    for relation in relations:
        if relation['child'] in names and relation['parent'] in names:
            # À esquerda: o pai é obrigatório (||) ou opcional (|o) para o filho.
            lines.append(f'    {relation["parent"]} {"|o" if relation["optional"] else "||"}--{"o|" if relation["unique"] else "o{"} {relation["child"]} : "{relation["column"]}"')
    return '\n'.join(lines)+'\n'


def geometry(view):
    return {name:(55+column*445, 50+row*315) for name,(column,row) in view['nos'].items()}


def field_label(name):
    """Rótulo de apresentação; o identificador físico continua no dicionário técnico."""
    labels = {'id':'Identificador', 'nome':'Nome', 'codigo':'Código', 'periodicidade':'Periodicidade',
               'situacao':'Situação', 'quantidade':'Quantidade', 'numero_serie':'Número de série',
               'setor_id':'Setor vinculado', 'linha_id':'Linha vinculada', 'tipo_equipamento_id':'Tipo de equipamento',
               'equipamento_id':'Equipamento vinculado', 'agenda_id':'Programação vinculada',
               'ordem_preventiva_id':'Ordem preventiva vinculada', 'ordem_servico_id':'Ordem corretiva vinculada',
               'peca_id':'Peça vinculada', 'solicitacao_id':'Compra vinculada', 'solicitante_id':'Usuário solicitante',
               'tipo_problema_id':'Tipo de problema', 'group_id':'Grupo vinculado', 'permission_id':'Permissão vinculada',
               'content_type_id':'Tipo de registro vinculado','name':'Nome','codename':'Código da permissão',
               'app_label':'Aplicação responsável','model':'Modelo registrado','app':'Aplicação', 'applied':'Aplicada em'}
    return labels.get(name, name.removesuffix('_id').replace('_',' ').capitalize())


def summarized_fields(view, name, tables):
    table=tables[name]
    pk=next((constraint_columns(r['definition']) for r in table['constraints'] if r['kind']=='p'),[])
    fields=list(pk)
    for child,column in view['ligacoes']:
        if child==name and column not in fields:fields.append(column)
    for column in ('nome','periodicidade','situacao','codigo','quantidade','numero_serie','name','codename','app_label','model','app','applied'):
        if any(c['name']==column for c in table['columns']) and column not in fields:fields.append(column)
    return pk,fields[:4]


def connection_points(parent, child):
    x,y = parent; a,b = child
    if y == b:
        return [(x+320,y+92),(a,b+92)] if x<a else [(x,y+92),(a+320,b+92)]
    if x == a:
        return [(x+160,y+184),(a+160,b)] if y<b else [(x+160,y),(a+160,b+184)]
    # Diagonais usam o corredor entre as linhas para não atravessar cartões.
    start = (x+80,y+184) if y<b else (x+80,y)
    # A chegada diagonal usa outra porta: não encobre o vínculo vertical central.
    end = (a+80,b) if y<b else (a+80,b+184)
    middle = (start[1]+end[1])/2
    return [start,(start[0],middle),(end[0],middle),end]


def generate_svg(view, tables, relations):
    """SVG autossuficiente para leitura e inserção em apresentações, sem serviços externos."""
    coordinates = geometry(view)
    width = max(x for x,y in coordinates.values())+375
    height = max(y for x,y in coordinates.values())+240
    html_escape = html.html_escape
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{view["id"]}-titulo {view["id"]}-descricao"><title id="{view["id"]}-titulo">{html_escape(view["titulo"])}</title><desc id="{view["id"]}-descricao">{html_escape(view["texto"])}</desc>',
               '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#192c43}.fisico,.campo{font-family:Consolas,monospace}.ligacao{stroke:#71849b;stroke-width:2;fill:none}.card{fill:white;stroke:#cbd5e1;stroke-width:1.5}.numero{font-size:13px;font-weight:700;paint-order:stroke;stroke:#f4f7fb;stroke-width:6;stroke-linejoin:round}.referencia{font-size:12px;font-weight:700;fill:#415876;paint-order:stroke;stroke:#f4f7fb;stroke-width:7}.selecionado .ligacao{stroke:#ba1735;stroke-width:4}.selecionado text{fill:#ba1735}.foco .card{stroke:#ba1735;stroke-width:3}</style>',
               f'<rect width="{width}" height="{height}" fill="#f4f7fb"/>']
    for column,title in enumerate(view.get('cabecalhos',[])):
        parts.append(f'<text x="{55+column*445}" y="25" font-size="16" font-weight="700">{html_escape(title)}</text>')
    index = {(relation['child'],relation['column']):relation for relation in relations}
    for key in view['ligacoes']:
        relation = index[key]
        points = connection_points(coordinates[relation['parent']],coordinates[relation['child']])
        (x,y),(a,b) = points[0],points[-1]
        path = 'M '+' L '.join(f'{p[0]},{p[1]}' for p in points)
        middle = points[len(points)//2]
        if len(points)==2:middle=((x+a)/2,(y+b)/2)
        horizontal = y==b
        start_offset = 22 if a>x else -22
        end_offset = -27 if a>x else 27
        if horizontal:
            point1=(x+start_offset,y-11); point2=(a+end_offset,b-11)
        else:
            point1=(x+16,y+(22 if b>y else -14));point2=(a+16,b+(-13 if b>y else 23))
        parts.extend([f'<g data-rel="{relation["id"]}"><title>{html_escape(relation_sentence(relation))} Coluna: {relation["column"]}.</title><path class="ligacao" d="{path}"/>',
                        f'<text class="numero" text-anchor="middle" x="{point1[0]}" y="{point1[1]}">{"0..1" if relation["optional"] else "1"}</text>',
                        f'<text class="numero" text-anchor="middle" x="{point2[0]}" y="{point2[1]}">{"0..1" if relation["unique"] else "0..N"}</text>',
                        f'<text class="referencia" text-anchor="middle" x="{middle[0]}" y="{middle[1]-10}">{relation["id"]}</text></g>'])
    for name,(x,y) in coordinates.items():
        pk,fields = summarized_fields(view,name,tables)
        title_lines=textwrap.wrap(entity_name(name), width=27)
        parts.extend([f'<g data-tabela="{name}"><rect class="card" x="{x}" y="{y}" width="320" height="184" rx="10"/>',
                        f'<path d="M{x+10},{y} H{x+310}" stroke="{view["cor"]}" stroke-width="4"/>'])
        for i,row in enumerate(title_lines):parts.append(f'<text x="{x+16}" y="{y+27+i*20}" font-size="17" font-weight="650">{html_escape(row)}</text>')
        parts.append(f'<text class="fisico" x="{x+16}" y="{y+65}" font-size="11" fill="#66778d">{name}</text>')
        for i,column in enumerate(fields):
            kind = ('PK' if column in pk else '')+(' / FK' if column in pk and any(r['child']==name and r['column']==column for r in relations) else 'FK' if any(r['child']==name and r['column']==column for r in relations) else '')
            parts.append(f'<text x="{x+16}" y="{y+94+i*22}" font-size="12"><title>{column}</title><tspan fill="{view["cor"]}" font-weight="700">{kind:7}</tspan> {field_label(column)}</text>')
        parts.append('</g>')
    return ''.join(parts)+'</svg>'


def generate_drawio(folder, tables, relations, views=None):
    file = ET.Element('mxfile',host='app.diagrams.net',type='device')
    index = {(r['child'],r['column']):r for r in relations}
    for view in views or VIEWS:
        diagram=ET.SubElement(file,'diagram',id=view['id'],name=view['titulo'])
        height=max(row for column,row in view['nos'].values())*315+460
        model=ET.SubElement(diagram,'mxGraphModel',grid='1',page='1',pageWidth='1400',pageHeight=str(max(1200,height)),dx='1400',dy=str(max(1100,height)),pageScale='1')
        root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
        title=ET.SubElement(root,'mxCell',id='titulo-pagina',value=f'<b>{html.html_escape(view["titulo"])}</b><br><font style="font-size:13px">1 = exatamente um · 0..1 = opcional · 0..N = zero ou vários<br>PK = identificador · FK = referência a outro cadastro. Os nomes técnicos aparecem em cinza.</font>',vertex='1',parent='1',style='text;html=1;align=left;verticalAlign=top;fontSize=24;whiteSpace=wrap;overflow=hidden;')
        ET.SubElement(title,'mxGeometry',x='55',y='20',width='1210',height='100',attrib={'as':'geometry'})
        for column,header in enumerate(view.get('cabecalhos',[])):
            band=ET.SubElement(root,'mxCell',id=f'coluna-{column}',value=header,vertex='1',parent='1',style='text;html=0;align=left;verticalAlign=middle;fontSize=15;fontStyle=1;whiteSpace=wrap;')
            ET.SubElement(band,'mxGeometry',x=str(55+column*445),y='120',width='320',height='30',attrib={'as':'geometry'})
        coordinates={name:(x,y+110) for name,(x,y) in geometry(view).items()}
        for name,(x,y) in coordinates.items():
            pk,fields=summarized_fields(view,name,tables)
            lines=[]
            for field in fields:
                marker='PK' if field in pk else 'FK' if any(r['child']==name and r['column']==field for r in relations) else ''
                lines.append(f'<span style="color:{view["cor"]}"><b>{marker}</b></span> {html.html_escape(field_label(field))}')
            label=f'<b style="font-size:18px">{html.html_escape(entity_name(name))}</b><br><span style="font-size:10px;color:#77869a">{name}</span><br><br>'+ '<br>'.join(lines)
            node=ET.SubElement(root,'mxCell',id=name,value=label,vertex='1',parent='1',style=f'rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacing=14;fontFamily=Helvetica;fontSize=13;fillColor=#FFFFFF;strokeWidth=2;strokeColor={view["cor"]};')
            ET.SubElement(node,'mxGeometry',x=str(x),y=str(y),width='320',height='184',attrib={'as':'geometry'})
        for key in view['ligacoes']:
            r=index[key]
            label=f'{r["id"]} · {"0..1" if r["optional"] else "1"} : {"0..1" if r["unique"] else "0..N"}'
            points=connection_points(coordinates[r['parent']],coordinates[r['child']])
            source,destination=points[0],points[-1]; px,py=coordinates[r['parent']];fx,fy=coordinates[r['child']]
            style=f'noEdgeStyle=1;rounded=0;html=0;endArrow=none;strokeWidth=2;strokeColor=#71849B;fontSize=12;labelBackgroundColor=#FFFFFF;exitX={(source[0]-px)/320};exitY={(source[1]-py)/184};exitPerimeter=0;entryX={(destination[0]-fx)/320};entryY={(destination[1]-fy)/184};entryPerimeter=0;'
            edge=ET.SubElement(root,'mxCell',id=r['id'],value=label,edge='1',parent='1',source=r['parent'],target=r['child'],style=style)
            edge_geometry=ET.SubElement(edge,'mxGeometry',relative='1',attrib={'as':'geometry'})
            if len(points)>2:
                xml_points=ET.SubElement(edge_geometry,'Array',attrib={'as':'points'})
                for x,y in points[1:-1]:ET.SubElement(xml_points,'mxPoint',x=str(x),y=str(y))
    ET.indent(file)
    ET.ElementTree(file).write(folder/'ER_MANTIS_EDITAVEL.drawio',encoding='utf-8',xml_declaration=True)
    ET.ElementTree(file).write(folder/'ER_MANTIS_DIDATICO_PORTUGUES.drawio',encoding='utf-8',xml_declaration=True)
    ET.ElementTree(file).write(folder/'ER_MANTIS_COMPLETO_PORTUGUES.drawio',encoding='utf-8',xml_declaration=True)


def generate_er(folder):
    folder=Path(folder);target=folder/'er';target.mkdir(parents=True,exist_ok=True)
    catalog=json.loads((folder/'catalogo-postgres.json').read_text(encoding='utf-8'))
    assert not catalog['missing_model_tables'] and not catalog['missing_model_columns'] and not catalog['pending_migrations'], 'Atualize o catálogo e as migrações antes de gerar o ER.'
    tables,relations=read_relations(catalog)
    views=complete_views(tables,relations)
    business=[t['name'] for t in catalog['tables'] if t['module']!='Infraestrutura Django']
    assert set(business)==set(ENTITY_NAMES)
    assert {name for view in VIEWS for name in view['principais']}==set(business)
    (folder/'RELACIONAMENTOS_PORTUGUES.mmd').write_text(mermaid(tables,relations,business),encoding='utf-8')
    (target/'ER_TECNICO_COMPLETO.mmd').write_text(mermaid(tables,relations,list(tables)),encoding='utf-8')
    generate_drawio(target,tables,relations,views)
    (target/'RELACOES_VERIFICADAS.json').write_text(json.dumps(relations,ensure_ascii=False,indent=2),encoding='utf-8')
    index={(r['child'],r['column']):r for r in relations}
    sections=[];guide=['# ER MANTIS — guia de leitura','',f'Base: catálogo PostgreSQL de {catalog["captured_at"]}.','',
                    'Entidade é uma tabela; atributo é uma coluna; relacionamento é uma referência (FK) entre tabelas.',
                    'PK identifica o registro. FK guarda a chave de outro registro. 1 = exatamente um; 0..1 = opcional, no máximo um; 0..N = zero ou vários.',
                    'Os números ao lado de cada entidade indicam quantos registros daquele lado podem participar para um registro do outro lado.',
                    'As figuras exibem campos e ligações principais. O catálogo completo conserva todos os vínculos e todas as colunas.','']
    html_escape=html.html_escape
    for i,view in enumerate(views):
        svg=generate_svg(view,tables,relations)
        (target/(view['id']+'.svg')).write_text(svg,encoding='utf-8')
        names=list(view['nos'])
        (target/(view['id']+'.mmd')).write_text(mermaid(tables,[index[key] for key in view['ligacoes']],names),encoding='utf-8')
        lines=[]
        for key in view['ligacoes']:
            r=index[key]
            lines.append(f'<button type="button" class="relacao" data-rel="{r["id"]}" aria-pressed="false"><b>{r["id"]}</b><span>{html_escape(relation_sentence(r))}<small>FK: {r["child"]}.{r["column"]} → {r["parent"]}</small></span></button>')
        related=[r for r in relations if r['child'] in view['principais']]
        full_list=''.join(f'<li><code>{r["child"]}.{r["column"]}</code> → <strong>{html_escape(entity_name(r["parent"]))}</strong> · {"opcional" if r["optional"] else "obrigatório"}</li>' for r in related)
        secondary=f'<details><summary>Todos os {len(related)} vínculos das tabelas desta área</summary><ul>{full_list}</ul></details>' if related else ''
        tip='Cartões mostram os campos principais. Selecione uma relação abaixo para destacar a linha.' if view['ligacoes'] else 'Todas as entidades de negócio estão nesta página. As ligações aparecem nas páginas por área.'
        sections.append(f'<section id="{view["id"]}" class="visao" {"hidden" if i else ""}><header><div><span class="etiqueta">VISÃO {i+1} DE {len(views)}</span><h2>{html_escape(view["titulo"])}</h2><p>{html_escape(view["texto"])}</p></div><div class="arquivos"><a href="er/{view["id"]}.svg" download>Imagem SVG</a><a href="er/{view["id"]}.mmd" download>Mermaid</a></div></header><div class="diagrama">{svg}</div><p class="dica">{tip}</p><div class="relacoes">{"".join(lines)}</div><aside>{html_escape(view["exemplo"])}</aside>{secondary}</section>')
        guide.extend([f'## {view["titulo"]}', '', view['texto'], '', view['exemplo'], ''])
        for key in view['ligacoes']:
            r=index[key];guide.append(f'- {r["id"]}: {relation_sentence(r)} FK: `{r["child"]}.{r["column"]}`.')
        guide.append('')
    table_rows=''.join(f'<tr data-busca="{html_escape((r["child"]+" "+r["column"]+" "+r["parent"]).lower())}"><td>{r["id"]}</td><td><code>{r["child"]}<br>{r["column"]}</code></td><td><code>{r["parent"]}</code></td><td>{"0..1" if r["optional"] else "1"}</td><td>{"0..1" if r["unique"] else "0..N"}</td><td>{"Django" if r["infrastructure"] else "Negócio"}</td></tr>' for r in relations)
    buttons=''.join(f'<button type="button" data-visao="{v["id"]}" aria-selected="{"true" if i==0 else "false"}" role="tab" aria-controls="{v["id"]}">{html_escape(v["titulo"])}</button>' for i,v in enumerate(views))
    page=HTML_TEMPLATE.replace('@@ABAS@@',buttons).replace('@@SECOES@@',''.join(sections)).replace('@@RELACOES@@',table_rows).replace('@@CAPTURA@@',html_escape(catalog['captured_at'])).replace('@@TOTAL@@',str(len(relations))).replace('@@NEGOCIO@@',str(sum(not r['infrastructure'] for r in relations)))
    (folder/'ER_MANTIS.html').write_text(page,encoding='utf-8')
    (target/'COMO_LER_O_ER.md').write_text('\n'.join(guide),encoding='utf-8')
    with ZipFile(folder/'PACOTE_ER_MANTIS.zip','w',ZIP_DEFLATED) as package:
        package.write(folder/'ER_MANTIS.html','ER_MANTIS.html')
        package.write(folder/'RELACIONAMENTOS_PORTUGUES.mmd','RELACIONAMENTOS_PORTUGUES.mmd')
        for file in sorted(target.iterdir()):
            if file.suffix in ('.svg','.mmd','.drawio','.json','.md'):
                package.write(file,str(file.relative_to(folder)))
        for file in sorted(folder.iterdir()):
            if file.name not in ('ER_MANTIS.html','RELACIONAMENTOS_PORTUGUES.mmd') and file.suffix in ('.html','.md','.json','.csv','.sql'):
                package.write(file,file.name)
    return {'tabelas_negocio':len(business),'relacoes_negocio':sum(not r['infrastructure'] for r in relations),'relacoes_totais':len(relations),'visoes':len(views)}


HTML_TEMPLATE = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MANTIS — Entenda o relacionamento dos dados</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#192c43;font:15px/1.6 "Segoe UI",Arial,sans-serif}main{max-width:1400px;margin:auto;padding:30px 28px 60px}h1{font-size:34px;letter-spacing:-1px;line-height:1.2;margin:8px 0 14px}h2{font-size:24px;margin:4px 0 8px}p{color:#596b80;margin:8px 0 14px}a{color:#a81431;text-underline-offset:3px}nav,.downloads,.legenda{display:flex;gap:10px;flex-wrap:wrap}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #c72042;outline-offset:3px}.etiqueta{color:#ba1735;font-size:11px;font-weight:750;letter-spacing:1.5px}.intro{max-width:950px}.legenda{margin:22px 0;padding:16px 20px;background:white;border:1px solid #dce3ed;border-radius:10px;gap:14px 25px}.legenda span{font-size:13px}.legenda b{color:#192c43}nav{border-bottom:1px solid #cbd5e1;padding:4px 0 14px;margin-bottom:24px}nav button{border:1px solid transparent;background:transparent;color:#53677e;padding:9px 12px;border-radius:7px;font-size:13px;font-weight:600}nav button[aria-selected="true"]{background:#ba1735;color:white}.downloads{font-size:13px;gap:18px}.visao>header{display:flex;align-items:start;justify-content:space-between;gap:24px}.visao>header p{max-width:900px}.arquivos{display:flex;gap:16px;white-space:nowrap;font-size:13px;padding-top:28px}.diagrama{overflow:auto;background:#f4f7fb;border:1px solid #d8e1ed;border-radius:12px}.diagrama svg{display:block;width:100%;min-width:790px;height:auto;max-height:none}.dica{font-size:12px}.relacoes{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:16px 0}.relacao{display:flex;text-align:left;gap:14px;padding:14px;background:white;border:1px solid #dce3ed;border-radius:8px;color:#354c66;font-size:13px;line-height:1.6}.relacao b{color:#a81431}.relacao small{display:block;color:#718198;font:11px/1.7 Consolas,monospace;overflow-wrap:anywhere;margin-top:6px}.relacao[aria-pressed="true"]{border-color:#ba1735;background:#fff6f7}aside{margin:20px 0;padding:15px 18px;background:#eaf0f8;border-left:3px solid #7891ad;font-size:13px}details{margin:18px 0}summary{cursor:pointer;font-weight:600;font-size:14px}details li{margin:6px 0;font-size:13px}code{font:12px/1.7 Consolas,monospace;overflow-wrap:anywhere}.inventario{margin-top:40px;border-top:1px solid #dce3ed;padding-top:25px}.filtro{width:100%;max-width:620px;padding:12px;border:1px solid #b6c4d5;border-radius:7px;font:inherit;margin:10px 0 18px}.tabela{overflow:auto;background:white;border:1px solid #dce3ed;border-radius:8px}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:12px;text-align:left;border-bottom:1px solid #e6ebf2}th{background:#eaf0f8}footer{font-size:11px;color:#6b7c91;margin-top:25px}[hidden]{display:none!important}@media(max-width:800px){main{padding:22px 16px}h1{font-size:28px}.visao>header{display:block}.arquivos{padding:0 0 14px}.relacoes{grid-template-columns:1fr}.legenda{gap:10px 18px}}@media print{@page{size:A3 landscape;margin:12mm}body{background:white}main{max-width:none;padding:0}nav,.downloads,.arquivos,.filtro,.dica{display:none}.visao[hidden]{display:block!important}.visao{break-before:page}.visao:first-of-type{break-before:avoid}.diagrama{overflow:visible}.diagrama svg{min-width:0;width:100%;max-height:600px}.relacoes{grid-template-columns:1fr 1fr}.relacao{break-inside:avoid}.inventario{break-before:page}}</style></head><body><main>
<span class="etiqueta">MANTIS / ENTIDADE E RELACIONAMENTO</span><h1>Como os dados se conectam</h1><p class="intro">Leia uma área por vez. Cada cartão representa uma tabela; a linha representa uma referência real do banco. Os números junto a cada ponta indicam quantos registros daquele lado podem se relacionar com um registro do outro lado.</p>
<div class="downloads"><a href="GUIA_PORTUGUES.html">Guia do banco</a><a href="er/COMO_LER_O_ER.md" download>Explicação em texto</a><a href="er/ER_MANTIS_COMPLETO_PORTUGUES.drawio" download>Baixar desenho completo em português (9 páginas)</a><a href="er/ER_TECNICO_COMPLETO.mmd" download>ER técnico completo</a><a href="PACOTE_ER_MANTIS.zip" download>Baixar pacote ER</a></div><p class="dica">Para ver o desenho, use as abas abaixo. O arquivo .drawio deve ser baixado e aberto no aplicativo diagrams.net; aberto diretamente no navegador, ele pode mostrar apenas código.</p>
<div class="legenda" aria-label="Legenda"><span><b>PK</b> Identifica o registro</span><span><b>FK</b> Aponta para outra tabela</span><span><b>1</b> Exatamente um</span><span><b>0..1</b> Nenhum ou um</span><span><b>0..N</b> Nenhum, um ou vários</span></div>
<nav role="tablist" aria-label="Áreas do ER">@@ABAS@@</nav>@@SECOES@@
<section class="inventario"><h2>Todos os relacionamentos conferidos</h2><p>@@NEGOCIO@@ vínculos de negócio e 3 vínculos internos do Django, totalizando @@TOTAL@@. Esta lista inclui as referências de autoria e as ligações omitidas dos desenhos para facilitar a leitura. Os números descrevem o que o banco permite; formulários e regras de negócio podem exigir mais.</p><label for="pesquisa">Pesquisar tabela ou coluna</label><br><input class="filtro" id="pesquisa" type="search" placeholder="Ex.: usuarios, responsavel_id, pecas"><div class="tabela"><table><thead><tr><th>Ref.</th><th>Tabela filha / FK</th><th>Tabela pai</th><th>Pais por filho</th><th>Filhos por pai</th><th>Área</th></tr></thead><tbody>@@RELACOES@@</tbody></table></div><p id="quantidade" aria-live="polite">@@TOTAL@@ relacionamentos.</p></section>
<footer>Catálogo verificado: @@CAPTURA@@. A documentação não contém registros pessoais nem altera o banco. As 21 entidades de negócio aparecem nas visões; as 5 tabelas internas do Django também constam do ER técnico completo.</footer>
</main><script>
document.querySelectorAll('[data-visao]').forEach(botao=>botao.addEventListener('click',()=>{document.querySelectorAll('[data-visao]').forEach(outro=>outro.setAttribute('aria-selected',String(outro===botao)));document.querySelectorAll('.visao').forEach(secao=>secao.hidden=secao.id!==botao.dataset.visao)}));
document.querySelector('[role="tablist"]').addEventListener('keydown',evento=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(evento.key))return;const botoes=Array.from(document.querySelectorAll('[data-visao]')),indice=botoes.indexOf(document.activeElement);if(indice<0)return;evento.preventDefault();const proximo=evento.key==='Home'?0:evento.key==='End'?botoes.length-1:(indice+(evento.key==='ArrowRight'?1:-1)+botoes.length)%botoes.length;botoes[proximo].focus();botoes[proximo].click()});
document.querySelectorAll('button[data-rel]').forEach(botao=>botao.addEventListener('click',()=>{const secao=botao.closest('.visao'),ativo=botao.getAttribute('aria-pressed')!=='true';secao.querySelectorAll('button[data-rel]').forEach(outro=>outro.setAttribute('aria-pressed',String(ativo&&outro===botao)));secao.querySelectorAll('svg [data-rel]').forEach(linha=>linha.classList.toggle('selecionado',ativo&&linha.dataset.rel===botao.dataset.rel))}));
document.getElementById('pesquisa').addEventListener('input',function(){const termo=this.value.trim().toLocaleLowerCase('pt-BR');let quantidade=0;document.querySelectorAll('[data-busca]').forEach(linha=>{linha.hidden=!linha.dataset.busca.includes(termo);if(!linha.hidden)quantidade++});document.getElementById('quantidade').textContent=quantidade+' relacionamento(s) encontrado(s).'});
if(location.protocol==='file:')document.querySelectorAll('a[href$=".zip"]').forEach(link=>link.hidden=true);
</script></body></html>'''
