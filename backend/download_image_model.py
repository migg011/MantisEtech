r"""Baixa o modelo de IA usado na busca de peças por foto.

Uso:  .\.venv\Scripts\python.exe download_image_model.py
"""
import os
import sys
import urllib.request
from pathlib import Path

URL = os.getenv('MANTIS_IMAGE_MODEL_URL',
                'https://huggingface.co/Xenova/dinov2-small/resolve/main/onnx/model_quantized.onnx')
TARGET = Path(os.getenv('MANTIS_IMAGE_MODEL') or Path(__file__).resolve().parent / 'models' / 'dinov2-small.onnx')

if TARGET.is_file() and TARGET.stat().st_size > 1_000_000:
    print(f'Modelo já existe: {TARGET}')
    sys.exit(0)
TARGET.parent.mkdir(parents=True, exist_ok=True)
print(f'Baixando {URL} ...')
temp = TARGET.with_suffix('.part')
urllib.request.urlretrieve(URL, temp)
temp.replace(TARGET)
print(f'Modelo salvo em {TARGET} ({TARGET.stat().st_size // 1_000_000} MB)')
