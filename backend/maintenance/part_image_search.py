"""Offline identification of catalog parts from a photograph."""
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from statistics import median

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, ImageStat
import zxingcpp

from django.db.models.functions import Length

from . import part_embeddings
from .models import SparePartCode

logger = logging.getLogger(__name__)
MAX_UPLOAD = 6 * 1024 * 1024
INVALID_IMAGE = (OSError, ValueError, Image.DecompressionBombError)


def open_photo(stream):
    with Image.open(stream, formats=['JPEG', 'PNG', 'WEBP']) as photo:
        if photo.width * photo.height > 24_000_000:
            raise ValueError('Image too large')
        photo.thumbnail((1800, 1800))
        return ImageOps.exif_transpose(photo).convert('L')


def fingerprint(photo):
    view = ImageOps.autocontrast(photo).resize((17, 17), Image.Resampling.LANCZOS)
    pixels = view.tobytes()
    return sum(
        (pixels[y * 17 + x] > pixels[(y + dy) * 17 + x + dx]) << (axis * 256 + y * 16 + x)
        for axis, (dx, dy) in enumerate(((1, 0), (0, 1)))
        for y in range(16) for x in range(16)
    )


def foreground_crop(photo):
    # A uniform border lets us separate the part from the surrounding surface.
    sample = photo.copy()
    sample.thumbnail((160, 160))
    width, height = sample.size
    if min(width, height) < 8:
        return photo
    pixels = sample.load()
    border = ([pixels[x, y] for x in range(width) for y in (0, height - 1)]
              + [pixels[x, y] for x in (0, width - 1) for y in range(height)])
    background = median(border)
    deviations = sorted(abs(value - background) for value in border)
    spread = deviations[len(deviations) * 9 // 10]
    if spread > 25:
        return photo
    mask = sample.point([255 if abs(value - background) > max(18, spread * 3)
                         else 0 for value in range(256)])
    box = mask.getbbox()
    if not box:
        return photo
    left, top, right, bottom = box
    if min(right - left, bottom - top) < 6:
        return photo
    return photo.crop((left * photo.width // width, top * photo.height // height,
                       -(-right * photo.width // width), -(-bottom * photo.height // height)))


def visual_fingerprints(photo, angles):
    if photo.getextrema()[1] - photo.getextrema()[0] < 18:
        return ()
    cropped = foreground_crop(photo)
    # Compare like views so a tight crop cannot compete with a full frame.
    return tuple((fingerprint(photo.rotate(angle, expand=True)),
                  fingerprint(cropped.rotate(angle, expand=True))) for angle in angles)


def catalog_fingerprints(photo_data):
    try:
        return visual_fingerprints(open_photo(io.BytesIO(photo_data)), (0,))
    except INVALID_IMAGE:
        return ()


def tesseract_path():
    configured = (os.getenv('MANTIS_TESSERACT') or '').strip().strip('"')
    candidates = [configured, shutil.which('tesseract') or '',
                  r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                  r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']
    return next((path for path in candidates if path and os.path.isfile(path)), '')


def otsu(image):
    """Limiar automático que separa letras do fundo."""
    histogram = image.histogram()
    total = sum(histogram)
    weighted = sum(i * count for i, count in enumerate(histogram))
    best, threshold, background, background_sum = 0.0, 128, 0, 0
    for level in range(256):
        background += histogram[level]
        if not background or background == total:
            continue
        background_sum += level * histogram[level]
        mean_back = background_sum / background
        mean_front = (weighted - background_sum) / (total - background)
        variance = background * (total - background) * (mean_back - mean_front) ** 2
        if variance > best:
            best, threshold = variance, level
    return threshold


def ocr_views(color_photo):
    """Versões da foto para o OCR, cobrindo letras coloridas e fundo escuro."""
    color_photo = ImageOps.exif_transpose(color_photo).convert('RGB')
    if max(color_photo.size) < 1200:
        scale = 1200 / max(color_photo.size)
        color_photo = color_photo.resize((round(color_photo.width * scale), round(color_photo.height * scale)),
                                         Image.Resampling.LANCZOS)
    gray = ImageOps.autocontrast(color_photo.convert('L'))
    # Canal de cor (R, G ou B) onde letra e fundo ficam mais diferentes.
    channel = max(color_photo.split(), key=lambda band: ImageStat.Stat(band).stddev[0])
    views = [gray]
    for source in (ImageOps.autocontrast(channel), gray):
        level = otsu(source)
        binary = source.point(lambda value, level=level: 255 if value > level else 0)
        if ImageStat.Stat(binary).mean[0] < 128:  # fundo escuro: inverte para letra preta no branco
            binary = ImageOps.invert(binary)
        views.append(binary)
    return views


def read_label(photos):
    executable = tesseract_path()
    if not executable:
        logger.warning('OCR: tesseract não encontrado (MANTIS_TESSERACT=%r)', os.getenv('MANTIS_TESSERACT'))
        return '', False
    texts, worked = [], False
    for photo in photos if isinstance(photos, (list, tuple)) else [photos]:
        text, ok = run_tesseract(executable, photo)
        worked = worked or ok
        if text and text not in texts:
            texts.append(text)
    return '\n'.join(texts)[:2000], worked


def run_tesseract(executable, photo):
    # Arquivo temporário em vez de stdin: mais confiável no Windows.
    handle, image_path = tempfile.mkstemp(suffix='.png')
    try:
        with os.fdopen(handle, 'wb') as stream:
            photo.save(stream, format='PNG')
        result = subprocess.run(
            [executable, image_path, 'stdout', '-l', 'eng', '--psm', '11'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )
        if result.returncode != 0:
            logger.warning('OCR: tesseract falhou (%s): %s', result.returncode,
                           result.stderr.decode('utf-8', errors='replace')[:500])
            return '', False
        return result.stdout.decode('utf-8', errors='replace').strip(), True
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning('OCR: erro ao executar tesseract: %s', exc)
        return '', False
    finally:
        try:
            os.remove(image_path)
        except OSError:
            pass


def terms(text):
    return {re.sub(r'[^A-Z0-9]', '', token)
            for token in re.findall(r'[A-Z0-9]+(?:[-_.][A-Z0-9]+)*', text.upper())}


# OCR costuma trocar letras e números parecidos; normaliza antes de comparar.
LOOKALIKES = str.maketrans({'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1',
                            'S': '5', 'Z': '2', 'B': '8', 'G': '6'})


def ocr_key(value):
    return value.translate(LOOKALIKES)


def near(a, b):
    """True quando a e b diferem em no máximo um caractere (troca, inclusão ou exclusão)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + (len(a) == len(b)):] == b[i + 1:]


def label_matches(identifiers, label_keys):
    for identifier in identifiers:
        key = ocr_key(identifier)
        if key in label_keys:
            return True
        # Etiqueta com só parte do código (ex.: 610113699 dentro de N610113699AA).
        # Exige 7+ caracteres para não confundir com números curtos.
        if any(len(term) >= 7 and (term in key or key in term) for term in label_keys):
            return True
        # Tolerância de um caractere só para códigos longos, evitando falsos positivos.
        if len(key) >= 6 and any(near(key, term) for term in label_keys if len(term) >= 5):
            return True
    return False


AI_MIN_SIMILARITY = float(os.getenv('MANTIS_IMAGE_MIN_SIMILARITY', '0.45'))
AI_MAX_RESULTS = 5


def visual_by_ai(upload, queryset, fields, matches):
    """Compara a foto com o catálogo usando os vetores do modelo de IA."""
    upload.seek(0)
    with Image.open(upload) as color_photo:
        color_photo.thumbnail((1200, 1200))
        query = part_embeddings.query_vectors(color_photo)
    scored = []
    rows = queryset.filter(photo_data__isnull=False).annotate(
        photo_size=Length('photo_data')).values(*fields, 'updated_at', 'photo_size')
    for row in rows.iterator():
        key = (row['id'], row['updated_at'], row['photo_size'])
        try:
            vector = part_embeddings.catalog_vector(key, lambda pk=row['id']: bytes(
                SparePartCode.objects.filter(pk=pk).values_list('photo_data', flat=True).get()))
        except INVALID_IMAGE:
            continue
        similarity = float((query @ vector).max())
        scored.append((similarity, row))
    scored.sort(key=lambda item: -item[0])
    for rank, (similarity, row) in enumerate(scored):
        if row['id'] not in matches and (rank >= AI_MAX_RESULTS or similarity < AI_MIN_SIMILARITY):
            continue
        row = {name: row[name] for name in fields}
        result = matches.setdefault(row['id'], {**row, 'evidence': 'visual'})
        result['visual_similarity'] = round(100 * max(similarity, 0))


def visual_by_hash(queryset, fields, query_hashes, matches):
    """Método antigo: só reconhece fotos quase idênticas às do cadastro."""
    photos = queryset.filter(photo_data__isnull=False).values(
        *fields, 'photo_data'
    ).iterator(chunk_size=4)
    for row in photos:
        image_data = bytes(row.pop('photo_data'))
        catalog_hashes = catalog_fingerprints(image_data)
        if not query_hashes or not catalog_hashes:
            continue
        distance = min((query ^ catalog).bit_count()
                       for views in query_hashes for query, catalog in zip(views, catalog_hashes[0]))
        if distance <= 112 or row['id'] in matches:
            result = matches.setdefault(row['id'], {**row, 'evidence': 'visual'})
            result['visual_similarity'] = round(100 * (512 - distance) / 512)


def search_photo(upload, reference):
    if not upload or not 0 < upload.size <= MAX_UPLOAD:
        raise ValidationError('Escolha uma imagem de até 6 MB.')
    try:
        photo = open_photo(upload)
    except INVALID_IMAGE:
        raise ValidationError('Use uma imagem JPG, PNG ou WebP válida, de até 24 megapixels.') from None
    codes = list(dict.fromkeys(code.text[:512] for code in zxingcpp.read_barcodes(photo) if code.text))[:20]
    upload.seek(0)
    with Image.open(upload) as color_photo:
        color_photo.thumbnail((1800, 1800))
        label, ocr_available = read_label(ocr_views(color_photo))
    code_terms = terms(' '.join([reference, *codes]))
    label_terms = terms(label)
    label_keys = {ocr_key(term) for term in label_terms}
    query_hashes = visual_fingerprints(photo, (0, 90, 180, 270))
    queryset = SparePartCode.objects.filter(active=True)
    matches = {}
    fields = ('id', 'code', 'part_number', 'description', 'manufacturer',
              'unit', 'stock_quantity', 'storage_location', 'photo_filename')
    for row in queryset.values(*fields).iterator():
        identifiers = {re.sub(r'[^A-Z0-9]', '', (value or '').upper())
                       for value in (row['code'], row['part_number'])} - {''}
        evidence = 'codigo' if label_matches(identifiers, {ocr_key(term) for term in code_terms}) else 'texto' if label_matches(identifiers, label_keys) else None
        if evidence:
            matches[row['id']] = {**row, 'evidence': evidence, 'visual_similarity': None}

    if part_embeddings.available():
        visual_by_ai(upload, queryset, fields, matches)
    else:
        visual_by_hash(queryset, fields, query_hashes, matches)

    priority = {'codigo': 0, 'texto': 1, 'visual': 2}
    ranked = sorted(matches.values(), key=lambda item: (
        priority[item['evidence']], -(item['visual_similarity'] or 0), item['id'],
    ))
    return {'results': ranked[:12], 'codes': codes, 'label': label, 'ocr_available': ocr_available,
            'ai_available': part_embeddings.available()}
