"""Classificação múltipla, permissões e filtros de inventário em banco isolado."""
import csv, io
from django.test import TestCase, Client
from maintenance.api import issue_token_value
from maintenance.models import UserCode, SparePartCode, CategoriaMaterial

class CategoriasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=UserCode.objects.create_user('CAT-ADM','Teste-123456',name='Administrador',role='ADMINISTRADOR')
        cls.tech=UserCode.objects.create_user('CAT-TEC','Teste-123456',name='Técnico',role='TECNICO')
        cls.npm=CategoriaMaterial.objects.get_or_create(name_key=CategoriaMaterial.key_value('NPM'),defaults={'name':'NPM'})[0]
        cls.nxt=CategoriaMaterial.objects.get_or_create(name_key=CategoriaMaterial.key_value('NXT'),defaults={'name':'NXT'})[0]
        cls.part_value=SparePartCode.objects.create(code='CAT-1',description='Suporte',part_number='PN-1')
        cls.outra=SparePartCode.objects.create(code='CAT-2',description='Outro item',part_number='PN-2')

    def setUp(self):
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.admin))

    def patch(self, data_value, status=200):
        response_value=self.client.patch(f'/api/spare-parts/{self.part_value.pk}',data_value,content_type='application/json')
        self.assertEqual(response_value.status_code,status,response_value.content)
        return response_value

    def test_multiplas_categorias_filtro_e_inventario(self):
        r=self.patch({'categoryIds':[self.npm.pk,self.nxt.pk,self.npm.pk]})
        self.assertCountEqual(r.json()['category_ids'],[self.npm.pk,self.nxt.pk])
        for c in (self.npm,self.nxt):
            r=self.client.get('/api/spare-parts',{'categoryId':c.pk})
            self.assertEqual([p['id'] for p in r.json()],[self.part_value.pk])
            inv=self.client.get('/api/spare-parts/inventory',{'categoryId':c.pk}).json()
            self.assertEqual(inv['total_items'],1)
            self.assertEqual(inv['category_name'],c.name)
            self.assertCountEqual(inv['items'][0]['categories'],['NPM','NXT'])
        rows=list(csv.reader(io.StringIO(self.client.get('/api/spare-parts/inventory.csv',{'categoryId':self.npm.pk}).content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0][-1],'Categorias')
        self.assertIn('NPM',rows[1][-1])
        self.assertEqual(len(self.client.get('/api/spare-parts').json()),2)

    def test_omissao_preserva_lista_vazia_remove(self):
        self.patch({'categoryIds':[self.npm.pk]})
        self.patch({'description':'Novo nome'})
        self.assertTrue(self.part_value.categorias.filter(pk=self.npm.pk).exists())
        r=self.patch({'categoryIds':[]})
        self.assertEqual(r.json()['category_ids'],[])
        self.assertIsNone(r.json()['category'])

    def test_payload_invalido_nao_altera_peca(self):
        for ids in ('NPM',[True],[-1],[999999]):
            self.patch({'categoryIds':ids,'description':'Não salvar'},400)
            self.part_value.refresh_from_db()
            self.assertEqual(self.part_value.description,'Suporte')
        self.patch({'category':'Categoria livre inexistente'},400)

    def test_renomear_desativar_preserva_historico(self):
        self.patch({'categoryIds':[self.npm.pk]})
        url=f'/api/part-categories/{self.npm.pk}'
        self.assertEqual(self.client.patch(url,{'name':'NPM Panasonic'},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get(f'/api/spare-parts/{self.part_value.pk}/details').json()['categories'][0]['name'],'NPM Panasonic')
        self.assertEqual(self.client.delete(url).status_code,200)
        self.patch({'categoryIds':[self.npm.pk]})
        r=self.client.patch(f'/api/spare-parts/{self.outra.pk}',{'categoryIds':[self.npm.pk]},content_type='application/json')
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.client.get('/api/spare-parts',{'categoryId':self.npm.pk}).json()),1)
        self.assertNotIn(self.npm.pk,[c['id'] for c in self.client.get('/api/part-categories').json()])
        self.assertEqual(self.client.patch(url,{'active':True},content_type='application/json').status_code,200)

    def test_nomes_padronizados_e_permissoes(self):
        r=self.client.post('/api/part-categories',{'name':'  Proteção   Pessoal  '},content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.json()['name'],'Proteção Pessoal')
        r=self.client.post('/api/part-categories',{'name':'protecao pessoal'},content_type='application/json')
        self.assertEqual(r.status_code,400,r.content)
        tech=Client(HTTP_AUTHORIZATION='Bearer '+issue_token_value(self.tech))
        self.assertEqual(tech.get('/api/part-categories').status_code,200)
        self.assertEqual(tech.post('/api/part-categories',{'name':'Teste'},content_type='application/json').status_code,403)
        self.assertEqual(tech.patch(f'/api/part-categories/{self.npm.pk}',{'active':False},content_type='application/json').status_code,403)
        self.assertEqual(Client().get('/api/part-categories').status_code,401)

    def test_filtro_invalido(self):
        for url in ('/api/spare-parts','/api/spare-parts/inventory','/api/spare-parts/inventory.csv'):
            self.assertEqual(self.client.get(url,{'categoryId':'abc'}).status_code,400)
            self.assertEqual(self.client.get(url,{'categoryId':999999}).status_code,404)

    def test_conversao_preserva_texto_antigo_sem_duplicar(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        self.part_value.category='  Npm  '
        self.part_value.save(update_fields=['category'])
        self.outra.category='Proteção Especial'
        self.outra.save(update_fields=['category'])
        migracao=import_module('maintenance.migrations.0019_preservar_categorias')
        editor=SimpleNamespace(connection=SimpleNamespace(alias='default'))
        migracao.converter(apps,editor)
        migracao.converter(apps,editor)
        self.assertEqual(list(self.part_value.categorias.values_list('pk',flat=True)),[self.npm.pk])
        self.assertEqual(self.outra.categorias.get().name,'Proteção Especial')
        self.assertEqual(CategoriaMaterial.objects.filter(name_key=CategoriaMaterial.key_value('npm')).count(),1)
