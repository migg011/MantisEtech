r"""Diagnóstico da busca de peças por foto.
Uso:  .\.venv\Scripts\python.exe diagnostico_busca.py
"""
import os
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from PIL import Image, ImageDraw
from maintenance import part_embeddings, part_image_search as busca
from maintenance.models import SparePartCode

print('=== 1. OCR (Tesseract) ===')
print('MANTIS_TESSERACT =', repr(os.getenv('MANTIS_TESSERACT')))
print('Encontrado em    =', repr(busca.tesseract_path()))
try:
    teste = Image.new('L', (600, 150), 255)
    ImageDraw.Draw(teste).text((20, 50), 'SKF-6203', fill=0)
    print('Leitura de teste =', busca.read_label(teste.resize((1200, 300))))
except Exception:
    traceback.print_exc()

print('\n=== 2. IA (DINOv2) ===')
print('Modelo           =', part_embeddings.model_path(), part_embeddings.model_path().is_file())
try:
    import onnxruntime
    print('onnxruntime      =', onnxruntime.__version__)
except Exception:
    traceback.print_exc()
print('IA disponível    =', part_embeddings.available())

print('\n=== 3. Catálogo ===')
ativas = SparePartCode.objects.filter(active=True)
print('Peças ativas     =', ativas.count())
print('Com foto         =', ativas.filter(photo_data__isnull=False).count())
