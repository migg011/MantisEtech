"""Reconhecimento visual de peças com um modelo de IA (DINOv2 em ONNX).

Cada foto vira um vetor de 384 números que descreve a aparência da peça.
Fotos da mesma peça, mesmo de ângulo, luz ou cor diferentes, geram vetores
próximos. Se o modelo ou o onnxruntime não estiverem instalados, a busca
continua funcionando com o método antigo (hash de pixels).
"""
import logging
import os
import threading
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

DEFAULT_MODEL = Path(__file__).resolve().parent.parent / 'models' / 'dinov2-small.onnx'
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

_lock = threading.Lock()
_session = None
_failed = False
_cache = {}  # (id, atualizado_em, tamanho) -> vetor da foto do catálogo


def model_path():
    return Path(os.getenv('MANTIS_IMAGE_MODEL') or DEFAULT_MODEL)


def session():
    global _session, _failed
    if _session is not None or _failed:
        return _session
    with _lock:
        if _session is None and not _failed:
            try:
                import onnxruntime
                path = model_path()
                if not path.is_file():
                    raise FileNotFoundError(f'modelo não encontrado em {path}')
                options = onnxruntime.SessionOptions()
                options.intra_op_num_threads = 2
                _session = onnxruntime.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])
            except Exception as exc:  # noqa: BLE001 - qualquer falha desliga só a IA
                _failed = True
                logger.warning('Busca visual por IA desativada: %s', exc)
    return _session


def available():
    return session() is not None


def _tensor(photo):
    import numpy as np
    photo = ImageOps.exif_transpose(photo).convert('RGB')
    photo = ImageOps.fit(photo, (224, 224), Image.Resampling.BICUBIC)
    data = np.asarray(photo, dtype=np.float32) / 255.0
    data = (data - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
    return data.transpose(2, 0, 1)


def embed(photos):
    """Recebe uma lista de imagens PIL e devolve vetores normalizados (N x 384)."""
    import numpy as np
    model = session()
    batch = np.stack([_tensor(photo) for photo in photos])
    name = model.get_inputs()[0].name
    output = model.run(None, {name: batch})[0]
    vectors = output[:, 0, :] if output.ndim == 3 else output  # token CLS
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-8)


def query_vectors(photo):
    """Vetores da foto enviada, em 4 rotações (a peça pode estar deitada)."""
    photo = ImageOps.exif_transpose(photo).convert('RGB')
    return embed([photo.rotate(angle, expand=True) for angle in (0, 90, 180, 270)])


def catalog_vector(key, photo_bytes_loader):
    vector = _cache.get(key)
    if vector is None:
        import io
        with Image.open(io.BytesIO(photo_bytes_loader())) as photo:
            photo.thumbnail((800, 800))
            vector = embed([photo])[0]
        _cache[key] = vector
    return vector
