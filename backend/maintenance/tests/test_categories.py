"""Classificação múltipla, permissões e filtros de inventário em banco isolado."""
import csv, io
from django.test import TestCase, Client
from maintenance.authentication import issue_token
from maintenance.models import User, SparePart, MaterialCategory

class CategoriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_user('CAT-ADM','Teste-123456',name='Administrador',role='ADMINISTRADOR')
        cls.tech=User.objects.create_user('CAT-TEC','Teste-123456',name='Técnico',role='TECNICO')
        cls.npm=MaterialCategory.objects.get_or_create(name_key=MaterialCategory.make_key('NPM'),defaults={'name':'NPM'})[0]
        cls.nxt=MaterialCategory.objects.get_or_create(name_key=MaterialCategory.make_key('NXT'),defaults={'name':'NXT'})[0]
        cls.part=SparePart.objects.create(code='CAT-1',description='Suporte',part_number='PN-1')
        cls.other=SparePart.objects.create(code='CAT-2',description='Outro item',part_number='PN-2')

    def setUp(self):
        self.client=Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.admin))

    def patch(self, data, status=200):
        response=self.client.patch(f'/api/spare-parts/{self.part.pk}',data,content_type='application/json')
        self.assertEqual(response.status_code,status,response.content)
        return response

    def test_multiple_categories_filter_and_inventory(self):
        r=self.patch({'categoryIds':[self.npm.pk,self.nxt.pk,self.npm.pk]})
        self.assertCountEqual(r.json()['category_ids'],[self.npm.pk,self.nxt.pk])
        for c in (self.npm,self.nxt):
            r=self.client.get('/api/spare-parts',{'categoryId':c.pk})
            self.assertEqual([p['id'] for p in r.json()],[self.part.pk])
            inv=self.client.get('/api/spare-parts/inventory',{'categoryId':c.pk}).json()
            self.assertEqual(inv['total_items'],1)
            self.assertEqual(inv['category_name'],c.name)
            self.assertCountEqual(inv['items'][0]['categories'],['NPM','NXT'])
        rows=list(csv.reader(io.StringIO(self.client.get('/api/spare-parts/inventory.csv',{'categoryId':self.npm.pk}).content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0][-1],'Categorias')
        self.assertIn('NPM',rows[1][-1])
        self.assertEqual(len(self.client.get('/api/spare-parts').json()),2)

    def test_omission_preserves_and_empty_list_removes(self):
        self.patch({'categoryIds':[self.npm.pk]})
        self.patch({'description':'Novo nome'})
        self.assertTrue(self.part.categories.filter(pk=self.npm.pk).exists())
        r=self.patch({'categoryIds':[]})
        self.assertEqual(r.json()['category_ids'],[])
        self.assertIsNone(r.json()['category'])

    def test_invalid_payload_does_not_change_part(self):
        for ids in ('NPM',[True],[-1],[999999]):
            self.patch({'categoryIds':ids,'description':'Não salvar'},400)
            self.part.refresh_from_db()
            self.assertEqual(self.part.description,'Suporte')
        self.patch({'category':'Categoria livre inexistente'},400)

    def test_rename_deactivate_preserves_history(self):
        self.patch({'categoryIds':[self.npm.pk]})
        url=f'/api/part-categories/{self.npm.pk}'
        self.assertEqual(self.client.patch(url,{'name':'NPM Panasonic'},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get(f'/api/spare-parts/{self.part.pk}/details').json()['categories'][0]['name'],'NPM Panasonic')
        self.assertEqual(self.client.delete(url).status_code,200)
        self.patch({'categoryIds':[self.npm.pk]})
        r=self.client.patch(f'/api/spare-parts/{self.other.pk}',{'categoryIds':[self.npm.pk]},content_type='application/json')
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.client.get('/api/spare-parts',{'categoryId':self.npm.pk}).json()),1)
        self.assertNotIn(self.npm.pk,[c['id'] for c in self.client.get('/api/part-categories').json()])
        self.assertEqual(self.client.patch(url,{'active':True},content_type='application/json').status_code,200)

    def test_normalized_names_and_permissions(self):
        r=self.client.post('/api/part-categories',{'name':'  Proteção   Pessoal  '},content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.json()['name'],'Proteção Pessoal')
        r=self.client.post('/api/part-categories',{'name':'protecao pessoal'},content_type='application/json')
        self.assertEqual(r.status_code,400,r.content)
        tech=Client(HTTP_AUTHORIZATION='Bearer '+issue_token(self.tech))
        self.assertEqual(tech.get('/api/part-categories').status_code,200)
        self.assertEqual(tech.post('/api/part-categories',{'name':'Teste'},content_type='application/json').status_code,403)
        self.assertEqual(tech.patch(f'/api/part-categories/{self.npm.pk}',{'active':False},content_type='application/json').status_code,403)
        self.assertEqual(Client().get('/api/part-categories').status_code,401)

    def test_invalid_filter(self):
        for url in ('/api/spare-parts','/api/spare-parts/inventory','/api/spare-parts/inventory.csv'):
            self.assertEqual(self.client.get(url,{'categoryId':'abc'}).status_code,400)
            self.assertEqual(self.client.get(url,{'categoryId':999999}).status_code,404)

    def test_conversion_preserves_old_text_without_duplicates(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.db.migrations.loader import MigrationLoader
        from django.test import override_settings
        # A conversão deve usar os modelos históricos, anteriores à tradução do ORM.
        with override_settings(MIGRATION_MODULES={}):
            apps = MigrationLoader(None).project_state([
                ('maintenance', '0019_preservar_categorias'),
            ]).apps
        self.part.category='  Npm  '
        self.part.save(update_fields=['category'])
        self.other.category='Proteção Especial'
        self.other.save(update_fields=['category'])
        migration=import_module('maintenance.migrations.0019_preservar_categorias')
        editor=SimpleNamespace(connection=SimpleNamespace(alias='default'))
        migration.converter(apps,editor)
        migration.converter(apps,editor)
        self.assertEqual(list(self.part.categories.values_list('pk',flat=True)),[self.npm.pk])
        self.assertEqual(self.other.categories.get().name,'Proteção Especial')
        self.assertEqual(MaterialCategory.objects.filter(name_key=MaterialCategory.make_key('npm')).count(),1)
