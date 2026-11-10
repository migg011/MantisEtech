"""Preserva classificações existentes e prepara exemplos para seleção padronizada."""
import hashlib
import unicodedata
from django.db import migrations

def converter(apps, schema_editor):
    Categoria=apps.get_model('maintenance','CategoriaMaterial')
    Peca=apps.get_model('maintenance','SparePart')
    banco=schema_editor.connection.alias
    def categoria(nome):
        nome=' '.join(nome.split())
        texto=unicodedata.normalize('NFKD',nome.casefold())
        texto=''.join(c for c in texto if not unicodedata.combining(c))
        chave=hashlib.sha256(texto.encode()).hexdigest()
        return Categoria.objects.using(banco).get_or_create(name_key=chave,defaults={'name':nome})[0]
    for nome in ('NPM','NXT','Impressoras','Limpeza','Lubrificantes','EPI'):
        categoria(nome)
    for peca in Peca.objects.using(banco).exclude(category__isnull=True).exclude(category='').iterator():
        if peca.category.strip():
            peca.categorias.add(categoria(peca.category))

class Migration(migrations.Migration):
    dependencies=[('maintenance','0018_categorias_materiais')]
    operations=[migrations.RunPython(converter,migrations.RunPython.noop)]
