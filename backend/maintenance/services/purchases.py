"""Casos de uso de compras do Mantis, separados do transporte HTTP."""

import csv

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .base import Result, operation, request_body
from ..exceptions import ApiError
from .. import forms
from . import registrations
from ..filters import apply_filters, PurchaseFilter
from ..models import PurchaseEvent, PurchaseRequest, TECHNICAL_FIELDS
from .common import visible_purchases, form_data, visible_orders, serialize_record, validate_form


def purchase_data(purchase):
    """Inclui os nomes do solicitante e do gestor para a tabela de acompanhamento Angular."""
    return {**serialize_record(purchase), 'requester_name': purchase.requester.name,
            'manager_name': purchase.manager.name,
            'equipment_model': purchase.equipment.model if purchase.equipment else None}


@operation(['GET', 'POST', 'PATCH'])
def purchases(context, pk=None):
    """Lista/detalha compras ou grava rascunho e itens na mesma transação, preservando autoria e estado."""
    if context.method == 'GET':
        if not pk:
            return [purchase_data(record) for record in
                    apply_filters(PurchaseFilter, context.filters, visible_purchases(context.user))[:200]]
        record = get_object_or_404(visible_purchases(context.user), pk=pk)
        items = []
        for line in record.items.select_related('spare_part', 'spare_part__technical').order_by('pk'):
            sheet = line.spare_part.technical if hasattr(line.spare_part, 'technical') else None
            items.append({**(serialize_record(sheet) if sheet else {}), **serialize_record(line),
                          'code': line.spare_part.code, 'part_number': line.spare_part.part_number,
                          'description': line.spare_part.description, 'manufacturer': line.spare_part.manufacturer})
        return {**purchase_data(record), 'items': items,
                'events': [serialize_record(event) for event in record.events.all()]}
    return save_purchase(context, request_body(context), pk)


def save_purchase(context, received_data, pk=None):
    """Valida e grava o rascunho e os itens; o serial é obtido no servidor, nunca do navegador."""
    with transaction.atomic():
        record = get_object_or_404(PurchaseRequest.objects.select_for_update(), pk=pk) if pk else PurchaseRequest(
            requester=context.user)
        original_equipment_id = record.equipment_id
        if record.requester_id != context.user.pk or record.status not in ('RASCUNHO', 'DEVOLVIDA'):
            raise PermissionDenied
        data = form_data(forms.PurchaseForm, received_data, instance=record if pk else None,
                         aliases={'managerId': 'manager', 'workOrderId': 'work_order',
                                  'equipmentId': 'equipment'})
        record = validate_form(forms.PurchaseForm(data, instance=record, user=context.user)).save(
            commit=False)
        if record.work_order_id and not visible_orders(context.user).filter(pk=record.work_order_id).exists():
            raise PermissionDenied
        if not pk or record.equipment_id != original_equipment_id:
            record.equipment_serial = record.equipment.serial if record.equipment else None
        entries = received_data.get('items')
        if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
            raise ApiError('Informe de 1 a 100 peças.')
        # Validate every item before saving. atomic rolls back the set if any step fails.
        validated_items = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ApiError('Item de compra inválido.')
            mapped = form_data(forms.PurchaseItemForm, entry, aliases={'sparePartId': 'spare_part'})
            validated_items.append(validate_form(forms.PurchaseItemForm(mapped)).save(commit=False))
        record.updated_at = timezone.now()
        record.save()
        record.items.all().delete()
        for line in validated_items:
            line.request = record
            line.save()
        PurchaseEvent.objects.create(request=record, actor=context.user,
                                     action='EDICAO' if pk else 'CRIACAO')
        return Result(purchase_data(record), status=200 if pk else 201)


@operation(['POST'])
def submit_purchase(context, pk):
    """Solicita conferência e congelamento dos dados técnicos; a aprovação será acompanhada no sistema."""
    get_object_or_404(visible_purchases(context.user), pk=pk)
    try:
        registrations.submit_purchase(pk, context.user)
    except ValidationError as exc:
        # TODO integration: the Angular screen also reads missing to list pending fields per part.
        # This return supplies the general message; the structured list still needs alignment.
        raise ApiError(' '.join(exc.messages), 409)
    # Forwarding changes the purchase state; this backend has no e-mail delivery integration.
    return {'ok': True, 'status': 'EM_APROVACAO', 'notification': 'SEM_DESTINATARIO_CONFIGURADO'}


@operation(['POST'], roles=('ADMINISTRADOR',))
def decide_purchase(context, pk):
    """Valida a decisão recebida e delega a autorização do gestor e o registro do evento ao serviço."""
    form = validate_form(forms.DecisionForm(request_body(context)))
    get_object_or_404(visible_purchases(context.user), pk=pk)
    try:
        registrations.decide_purchase(pk, context.user, form.cleaned_data['decision'],
                                      form.cleaned_data['comment'])
    except ValidationError as exc:
        raise ApiError(' '.join(exc.messages), 409)
    return {'id': pk, 'status': form.cleaned_data['decision']}


@operation(['GET'])
def export_purchase(context, pk):
    """Exporta os dados congelados no envio, neutralizando células que poderiam virar fórmulas."""
    record = get_object_or_404(visible_purchases(context.user), pk=pk)
    if record.status not in ('EM_APROVACAO', 'APROVADA'):
        raise ApiError('Encaminhe a solicitação antes de exportar.', 409)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="SC-{pk}-DADOS-TECNICOS.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    columns = {'part_number': 'Part Number', 'description': 'Descrição da peça', 'manufacturer': 'Fabricante',
               'picture_reference': 'Picture', **TECHNICAL_FIELDS}
    writer.writerow(['OS', 'Equipamento', 'Serial da máquina', *columns.values()])
    for line in record.items.select_related('spare_part').order_by('pk'):
        values = [str(record.work_order_id or ''), (record.equipment.model or '') if record.equipment else '',
                  record.equipment_serial or '']
        snapshot = line.technical_snapshot or {}
        values += [str(snapshot.get(key,
                                    getattr(line.spare_part, key, '') if key in ('part_number', 'description',
                                                                                 'manufacturer') else '') or '') for
                   key in columns]
        writer.writerow(
            ["'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value for value in values])
    return response
