"""Exporta formatos de modelagem a partir do catálogo verificado, sem alterar o PostgreSQL."""
from pathlib import Path
import json
import re
import runpy
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'formatos'
OUT.mkdir(exist_ok=True)
source = runpy.run_path(str(ROOT / 'generate_presentation.py'))
data, tables = source['DATA'], source['TABLES']


def columns_of(rule):
    """Lê as colunas simples das PKs/FKs/UNIQUE preservando a ordem de chaves compostas."""
    match = re.search(r'\(([^)]+)\)', rule['definition'])
    return [name.strip(' "') for name in match.group(1).split(',')] if match else []


def dbml():
    """DBML é um modelo para diagramar. Índices funcionais/parciais e detalhes do SQL ficam no dump físico."""
    lines = ["Project MANTIS {", "  database_type: 'PostgreSQL'", "  Note: 'Modelo do catálogo verificado. Use o SQL físico para reprodução exata de índices e restrições.'", '}', '']
    for table in tables:
        lines.append('Table public.' + table['name'] + ' {')
        pk = next((columns_of(rule) for rule in table['constraints'] if rule['kind']=='p'), [])
        for column in table['columns']:
            settings = ['null' if column['nullable'] else 'not null']
            if pk == [column['name']]:
                settings.append('pk')
            if column['identity'] == 'YES':
                settings.append('increment')
            dtype = source['sql_type'](column)
            if ' ' in dtype:
                dtype = '"'+dtype+'"'
            lines.append(f'  {column["name"]} {dtype} [{", ".join(settings)}]')
        rules = [rule for rule in table['constraints'] if rule['kind'] in ('p','u') and (rule['kind']!='p' or len(pk)>1)]
        if rules:
            lines.append('  indexes {')
            for rule in rules:
                members = columns_of(rule)
                if not members:
                    continue
                value = members[0] if len(members)==1 else '('+', '.join(members)+')'
                flag = 'pk' if rule['kind']=='p' else 'unique'
                lines.append(f"    {value} [{flag}, name: '{rule['name']}']")
            lines.append('  }')
        note = source['purpose'](table).replace('\\','\\\\').replace("'","\\'").replace('\n',' ')
        lines.append(f"  Note: '{note}'")
        lines.extend(['}', ''])
    for table in tables:
        for rule in source['foreign_keys'](table):
            members = columns_of(rule)
            target_columns = re.search(r'REFERENCES [^(]+\(([^)]+)\)',rule['definition']).group(1)
            unique = any(r['kind'] in ('p','u') and columns_of(r)==members for r in table['constraints'])
            # Em uma relação 1:1 DBML, a segunda coluna é a FK. Preservamos a direção real do PostgreSQL.
            if unique:
                lines.append(f'Ref: public.{rule["target"]}.{target_columns} - public.{table["name"]}.{members[0]}')
            else:
                lines.append(f'Ref: public.{table["name"]}.{members[0]} > public.{rule["target"]}.{target_columns}')
    (OUT/'MANTIS_MODEL.dbml').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def drawio():
    """Cada módulo tem uma página editável. A visão geral contém todas as 26 tabelas e as 49 FKs."""
    mxfile=ET.Element('mxfile',host='app.diagrams.net',type='device')
    groups = [('Esquema completo', [table['name'] for table in tables])] + list(data['modules'].items())
    by_name = {table['name']:table for table in tables}
    for number,(module,names) in enumerate(groups):
        diagram=ET.SubElement(mxfile,'diagram',id=f'module-{number}',name=module)
        model=ET.SubElement(diagram,'mxGraphModel',grid='1',gridSize='10',page='1',pageWidth='2200',pageHeight='3000',pageScale='1',tooltips='1',connect='1',arrows='1')
        root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
        external = sorted({rule['target'] for name in names for rule in source['foreign_keys'](by_name[name])} - set(names))
        all_names = names + external
        y_positions=[100]*4
        for index,name in enumerate(all_names):
            table=by_name[name]; lane=index%4; x=40+lane*510; y=y_positions[lane]
            fields = table['columns'] if number else [column for column in table['columns'] if source['keys'](table,column['name'])]
            fields = fields or table['columns'][:2]
            body='\n'.join(f'{source["keys"](table,column["name"]):10} {column["name"]} : {source["sql_type"](column)}' for column in fields)
            label=name+ (' (referência externa)' if name in external else '')+'\n\n'+body
            cell=ET.SubElement(root,'mxCell',id=name,value=label,vertex='1',parent='1',style='rounded=0;whiteSpace=wrap;html=0;align=left;verticalAlign=top;spacing=12;fontFamily=Courier New;fontSize=12;strokeColor=#B8C5D8;fillColor='+('#EDF1F6' if name in external else '#FFFFFF')+';')
            height=70+len(fields)*22
            ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width='420',height=str(height),attrib={'as':'geometry'})
            y_positions[lane] += height+85
        for name in names:
            for rule in source['foreign_keys'](by_name[name]):
                if rule['target'] not in all_names:
                    continue
                label=', '.join(columns_of(rule))
                edge=ET.SubElement(root,'mxCell',id='fk-'+rule['name'],value=label,edge='1',parent='1',source=name,target=rule['target'],style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=open;strokeColor=#8195B0;fontSize=10;labelBackgroundColor=#FFFFFF;')
                ET.SubElement(edge,'mxGeometry',relative='1',attrib={'as':'geometry'})
    ET.indent(mxfile,space='  ')
    ET.ElementTree(mxfile).write(OUT/'MANTIS_RELATIONSHIPS.drawio',encoding='utf-8',xml_declaration=True)


if __name__=='__main__':
    dbml();drawio()
    parsed=ET.parse(OUT/'MANTIS_RELATIONSHIPS.drawio')
    complete=parsed.getroot().find('diagram')
    assert len(complete.findall('.//mxCell[@edge="1"]'))==49
    assert len(complete.findall('.//mxCell[@vertex="1"]'))==26
    assert (OUT/'MANTIS_MODEL.dbml').read_text(encoding='utf-8').count('Table public.')==26
    print('DBML e diagrams.net: 26 tabelas e 49 vínculos, com 7 páginas de diagrama.')
