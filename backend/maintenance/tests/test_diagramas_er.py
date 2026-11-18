"""Cardinalidades devem refletir FK, nulidade e unicidade reais do PostgreSQL."""
from django.test import SimpleTestCase
from maintenance.er_diagrams import read_relationships, mermaid


class CardinalidadesErTests(SimpleTestCase):
    def tabela(self, name_value, colunas, restricoes):
        return {'name':name_value, 'module':'Negócio', 'columns':[{'name':nome_coluna,'nullable':opcional,'pg_type':'int8'} for nome_coluna,opcional in colunas], 'constraints':[{'name':f'c{i}', 'kind':tipo,'definition':definition,'target':'pais' if tipo=='f' else None} for i,(tipo,definition) in enumerate(restricoes)]}

    def test_fk_opcional_e_chave_composta_continuam_um_para_muitos(self):
        parent_value=self.tabela('pais',[('id',False)],[('p','PRIMARY KEY (id)')])
        child=self.tabela('filhas',[('pai_id',True),('outra_id',False)],[('p','PRIMARY KEY (pai_id, outra_id)'),('f','FOREIGN KEY (pai_id) REFERENCES pais(id)')])
        tables_value,relationships_value=read_relationships({'tables':[parent_value,child]})
        self.assertTrue(relationships_value[0]['opcional'])
        self.assertFalse(relationships_value[0]['unica'])
        self.assertIn('pais |o--o{ filhas', mermaid(tables_value,relationships_value,['pais','filhas']))

    def test_pk_que_tambem_e_fk_e_um_para_um(self):
        parent_value=self.tabela('pais',[('id',False)],[('p','PRIMARY KEY (id)')])
        profile_value=self.tabela('fichas',[('pai_id',False)],[('p','PRIMARY KEY (pai_id)'),('f','FOREIGN KEY (pai_id) REFERENCES pais(id)')])
        tables_value,relationships_value=read_relationships({'tables':[parent_value,profile_value]})
        self.assertTrue(relationships_value[0]['unica'])
        self.assertFalse(relationships_value[0]['opcional'])
        texto=mermaid(tables_value,relationships_value,['pais','fichas'])
        self.assertIn('int8 pai_id PK, FK',texto)
        self.assertIn('pais ||--o| fichas',texto)
