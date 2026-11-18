r"""Lista código e part number das peças ativas.
Uso:  .\.venv\Scripts\python.exe listar_codigos.py
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from maintenance.models import SparePartCode

for p in SparePartCode.objects.filter(active=True).order_by('id'):
    print(f'id={p.id} | codigo={p.code!r} | part_number={p.part_number!r} | {p.description}')
