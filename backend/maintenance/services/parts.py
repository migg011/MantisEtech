"""Casos de uso de pecas do Mantis, separados do transporte HTTP."""

import base64
import binascii
import csv
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .base import Result, operation, request_body
from ..exceptions import ApiError
from .. import forms
from . import registrations, stock
from ..filters import apply_filters, SparePartFilter
from ..models import MaterialCategory, SparePart, SparePartCompatibility, SparePartTechnical, StockMovement, \
    TECHNICAL_FIELDS
from .common import form_data, require_role, positive_id, serialize_record, validate_form
from .common import MAINTENANCE_ROLES


def part_data(part):
    """Acrescenta os IDs de equipamentos compatíveis ao cadastro público da peça."""
    categories = list(part.categories.all())
    return {**serialize_record(part), 'category': categories[0].name if categories else part.category,
            'category_ids': [category.pk for category in categories],
            'categories': [{'id': category.pk, 'name': category.name, 'active': category.active} for category in
                           categories],
            'stock_status': stock.stock_status(part),
            'equipment_ids': list(part.compatibility.values_list('equipment_id', flat=True))}


@operation(['GET'], roles=MAINTENANCE_ROLES)
def part_details(context, pk):
    """Fonte única da ficha de consulta compartilhada por cadastro, OS e compras."""
    part = get_object_or_404(SparePart.objects.defer('photo_data', 'datasheet_data').select_related('technical'),
                             pk=pk, active=True)
    return {**part_data(part),
            'technical': serialize_record(part.technical) if hasattr(part, 'technical') else None}


@operation(['GET'], roles=MAINTENANCE_ROLES)
def part_photo(context, pk):
    """Foto autenticada da peça; o conteúdo binário não é incluído nas listas do catálogo."""
    part = get_object_or_404(SparePart, pk=pk, active=True)
    if not part.photo_data:
        raise Http404
    return FileResponse(io.BytesIO(bytes(part.photo_data)), content_type=part.photo_mime,
                        filename=part.photo_filename or 'foto-peca.png')


@operation(['GET', 'POST', 'PATCH', 'DELETE'], roles=MAINTENANCE_ROLES)
def material_categories(context, pk=None):
    """Administradores mantêm a lista; desativar preserva vínculos e histórico."""
    if context.method == 'GET':
        items = MaterialCategory.objects.annotate(part_count=Count('parts', filter=Q(parts__active=True)))
        if context.filters.get('includeInactive') != 'true':
            items = items.filter(active=True)
        return [
            {'id': category.pk, 'name': category.name, 'description': category.description, 'active': category.active,
             'part_count': category.part_count}
            for category in items]
    require_role(context, 'ADMINISTRADOR')
    with transaction.atomic():
        category = get_object_or_404(MaterialCategory.objects.select_for_update(),
                                     pk=pk) if pk else MaterialCategory()
        if context.method == 'DELETE':
            category.active = False
        else:
            data = request_body(context)
            for field, limit in [('name', 100), ('description', 250)]:
                if field in data:
                    if not isinstance(data[field], str) or len(data[field]) > limit:
                        raise ApiError('Nome ou descrição de categoria inválido.')
                    setattr(category, field, ' '.join(data[field].split()))
            if not category.name:
                raise ApiError('Informe o nome da categoria.')
            if 'active' in data:
                if not isinstance(data['active'], bool):
                    raise ApiError('Situação da categoria inválida.')
                category.active = data['active']
            if MaterialCategory.objects.filter(name_key=MaterialCategory.make_key(category.name)).exclude(
                    pk=category.pk).exists():
                raise ApiError('Já existe uma categoria com esse nome.')
        category.save()
        return Result({'id': category.pk, 'name': category.name, 'description': category.description,
                       'active': category.active}, status=200 if pk else 201)


def filter_category(items, context):
    """O mesmo filtro é usado na tela e no relatório completo de inventário."""
    category = context.filters.get('categoryId', '')
    if category:
        code = positive_id(category)
        get_object_or_404(MaterialCategory, pk=code)
        items = items.filter(categories__pk=code)
    return apply_filters(SparePartFilter, context.filters, items).prefetch_related('categories').distinct()


@operation(['GET', 'POST', 'PATCH', 'DELETE'], roles=MAINTENANCE_ROLES)
def parts(context, pk=None):
    """Mantém o cadastro mestre e suas compatibilidades; limites de estoque não representam movimentações."""
    if context.method == 'GET':
        items = SparePart.objects.filter(active=True).defer('photo_data', 'datasheet_data').prefetch_related(
            'compatibility')
        items = filter_category(items, context)
        query = context.filters.get('q', '').strip()
        if query:
            items = items.filter(
                Q(part_number__icontains=query) | Q(description__icontains=query) | Q(manufacturer__icontains=query))
        return [part_data(part) for part in items.order_by('part_number', 'description')[:500]]
    require_role(context, 'ADMINISTRADOR')
    with transaction.atomic():
        record = get_object_or_404(SparePart.objects.select_for_update(), pk=pk,
                                   active=True) if pk else SparePart(code=registrations.generate_internal_code('SP'))
        if context.method == 'DELETE':
            if record.stock_quantity is not None and record.stock_quantity > 0:
                raise ApiError('Registre a saída ou ajuste do saldo antes de desativar a peça.', 409)
            record.active, record.updated_at = False, timezone.now()
            record.save(update_fields=['active', 'updated_at'])
            return {'ok': True}
        received_data = request_body(context)
        if any(key in received_data for key in ('stockQuantity', 'stock_quantity')):
            raise ApiError('Altere o saldo pela opção Movimentar estoque, com histórico.')
        # The form receives registration IDs; it never creates categories from free text.
        categories = None
        if 'categoryIds' in received_data:
            ids = received_data['categoryIds']
            if not isinstance(ids, list) or len(ids) > 50 or any(type(i) is not int or i <= 0 for i in ids):
                raise ApiError('Selecione categorias válidas na lista.')
            ids = set(ids)
            categories = list(MaterialCategory.objects.filter(pk__in=ids))
            existing = set(record.categories.values_list('pk', flat=True)) if pk else set()
            if len(categories) != len(ids) or any(not category.active and category.pk not in existing
                                                  for category in categories):
                raise ApiError('Uma categoria não existe ou está inativa. Atualize a lista.')
        elif 'category' in received_data and received_data['category']:
            name = received_data['category']
            if not isinstance(name, str):
                raise ApiError('Selecione uma categoria da lista.')
            category = MaterialCategory.objects.filter(name_key=MaterialCategory.make_key(name), active=True).first()
            if not category:
                raise ApiError('Cadastre a categoria antes de selecionar na peça.')
            categories = [category]
        photo = received_data.get('photo')
        if 'photo' in received_data:
            if not isinstance(photo, dict) or not isinstance(photo.get('filename'), str) or not 1 <= len(
                    photo['filename'].strip()) <= 255:
                raise ApiError('Informe um nome válido para a foto da peça.')
            try:
                photo_content = base64.b64decode(photo.get('base64'), validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise ApiError('Foto em base64 inválida.')
            file = validate_form(
                forms.AttachmentForm({'kind': 'PHOTO'}, {'file': SimpleUploadedFile(photo['filename'], photo_content)}))
            if photo.get('mimeType') != file.cleaned_data['mime_type']:
                raise ApiError('O conteúdo da foto não corresponde ao tipo informado.')
            # Registration and photo are saved together: an invalid photo leaves no partial part in the database.
            record.photo_filename = photo['filename'].strip()
            record.photo_mime = file.cleaned_data['mime_type']
            record.photo_data = photo_content
        data = form_data(forms.SparePartForm, received_data, instance=record if pk else None,
                         aliases={'equipmentIds': 'equipment'})
        if not pk:
            data = {'unit': 'UN', 'minimum_stock': 0, 'reorder_point': 0, **data}
        elif 'equipment' not in data:
            data['equipment'] = list(record.compatibility.values_list('equipment_id', flat=True))
        form = validate_form(forms.SparePartForm(data, instance=record))
        record = form.save(commit=False)
        record.updated_at = timezone.now()
        record.save()
        if categories is not None:
            record.categories.set(categories)
            record.category = categories[0].name if categories else None
            record.save(update_fields=['category'])
        record.compatibility.all().delete()
        SparePartCompatibility.objects.bulk_create(
            [SparePartCompatibility(spare_part=record, equipment=equipment)
             for equipment in form.cleaned_data['equipment']])
        return Result(part_data(record), status=200 if pk else 201)


@operation(['GET', 'POST'], roles=MAINTENANCE_ROLES)
def stock_movements(context, pk):
    """Técnicos consultam; administradores lançam saldo inicial, entrada, saída e ajuste."""
    if context.method == 'POST':
        require_role(context, 'ADMINISTRADOR')
        movement, created = stock.record_movement(pk, request_body(context), context.user)
        return Result({'movement': serialize_record(movement), 'replayed': not created},
                      status=201 if created else 200)
    get_object_or_404(SparePart, pk=pk)
    return [{**serialize_record(movement), 'performed_by_name': movement.performed_by.name} for movement in
            StockMovement.objects.filter(spare_part_id=pk).select_related('performed_by')[:100]]


@operation(['GET'], roles=MAINTENANCE_ROLES)
def parts_inventory(context, output_format='json'):
    """Retrato completo dos itens ativos, sem o limite de 500 linhas do catálogo."""
    items = SparePart.objects.filter(active=True).defer('photo_data', 'datasheet_data').order_by('part_number',
                                                                                               'description',
                                                                                               'pk')
    items = filter_category(items, context)
    query = context.filters.get('q', '').strip()
    if query:
        items = items.filter(
            Q(part_number__icontains=query) | Q(description__icontains=query) | Q(manufacturer__icontains=query))
    generated = timezone.now()
    rows = [{'id': part.pk, 'part_number': part.part_number, 'description': part.description,
             'manufacturer': part.manufacturer, 'storage_location': part.storage_location, 'unit': part.unit,
             'stock_quantity': part.stock_quantity, 'minimum_stock': part.minimum_stock,
             'maximum_stock': part.maximum_stock, 'reorder_point': part.reorder_point,
             'stock_status': stock.stock_status(part), 'categories': [category.name for category in part.categories.all()]}
            for part in items]
    if output_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="INVENTARIO_PECAS.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(
            ['Gerado em', 'Part Number', 'Descrição', 'Fabricante', 'Localização', 'Unidade', 'Saldo disponível',
             'Situação', 'Mínimo', 'Máximo', 'Ponto de reposição', 'Categorias'])

        def cell(value):
            text = '' if value is None else str(value)
            return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text

        for part in rows:
            values = [timezone.localtime(generated).isoformat(), part['part_number'], part['description'],
                      part['manufacturer'], part['storage_location'], part['unit'], part['stock_quantity'],
                      part['stock_status'], part['minimum_stock'], part['maximum_stock'], part['reorder_point'],
                      ', '.join(part['categories'])]
            writer.writerow([cell(value) for value in values])
        return response
    return {'category_id': context.filters.get('categoryId', ''), 'category_name': MaterialCategory.objects.get(
        pk=context.filters['categoryId']).name if context.filters.get('categoryId') else '', 'generated_at': generated,
        'query': query, 'items': rows, 'total_items': len(rows),
        'uninitialized_items': sum(part['stock_quantity'] is None for part in rows)}


@operation(['GET'])
def purchase_parts(context):
    """Fornece peças ativas e situação da ficha para os seletores da tela de compras."""
    return [{**serialize_record(part),
             'fiscal_status': part.technical.fiscal_status if hasattr(part, 'technical') else 'PENDENTE'}
            for part in
            SparePart.objects.filter(active=True).defer('photo_data', 'datasheet_data').select_related('technical')[
                :1000]]


@operation(['GET', 'PUT', 'POST'], roles=MAINTENANCE_ROLES)
def technical_sheet(context, pk, validate=False):
    """Consulta/salva a ficha ou registra validação administrativa; alterações revogam a validação anterior."""
    part = get_object_or_404(SparePart, pk=pk, active=True)
    if validate:
        require_role(context, 'ADMINISTRADOR')
    with transaction.atomic():
        sheet = SparePartTechnical.objects.select_for_update().filter(spare_part=part).first()
        if context.method == 'GET':
            return serialize_record(sheet) if sheet else {'spare_part_id': pk, 'fiscal_status': 'PENDENTE'}
        if validate:
            if sheet is None or not (sheet.ncm or '').strip() or not (sheet.pli_description or '').strip():
                raise ApiError('Preencha NCM e descrição para PLI antes da validação interna.', 409)
            sheet.fiscal_status, sheet.fiscal_validated_by = 'VALIDADA', context.user
            sheet.fiscal_validated_at = timezone.now()
        else:
            received_data = request_body(context)
            if not received_data or set(received_data) - set(TECHNICAL_FIELDS):
                raise ApiError('Campos da ficha técnica inválidos.')
            data = {key: getattr(sheet, key) for key in TECHNICAL_FIELDS} if sheet else {}
            data.update(received_data)
            sheet = validate_form(
                forms.TechnicalForm(data, instance=sheet or SparePartTechnical(spare_part=part))).save(
                commit=False)
            sheet.fiscal_status, sheet.fiscal_validated_by, sheet.fiscal_validated_at = 'PENDENTE', None, None
        sheet.updated_at = timezone.now()
        sheet.save()
        return serialize_record(sheet)
