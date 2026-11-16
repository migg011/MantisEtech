"""Caso de uso de entrada de peças por nota fiscal: registra várias entradas em uma transação."""
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from .base import Result, operation, request_body
from .common import positive_id
from .stock import record_movement
from ..exceptions import ApiError
from ..models import SparePart


@operation(['POST'], roles=('ADMINISTRADOR',))
def stock_receipt(context):
    """Registra na mesma transação todas as entradas da nota fiscal."""
    data = request_body(context)
    supplier = data.get('supplier')
    reference = data.get('documentReference')
    received = data.get('movementDate')
    items = data.get('items')
    if not isinstance(supplier, str) or not supplier.strip() \
            or not isinstance(reference, str) or not reference.strip():
        raise ApiError('Informe o fornecedor e o número da nota fiscal.')
    if not isinstance(received, str) or not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ApiError('Informe a data de recebimento e de 1 a 100 itens.')
    try:
        base_key = UUID(str(data.get('requestKey', '')))
    except (ValueError, TypeError):
        raise ApiError('Chave de requisição inválida.')
    if any(not isinstance(item, dict) for item in items):
        raise ApiError('Item da nota inválido.')
    recorded, seen = [], set()
    with transaction.atomic():
        for index, item in enumerate(items):
            part_id = positive_id(item.get('partId'), 'Peça')
            if part_id in seen:
                raise ApiError('A nota não pode repetir a mesma peça.')
            seen.add(part_id)
            try:
                quantity = Decimal(str(item.get('quantity', '0')))
                if not quantity.is_finite() or quantity <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError, TypeError):
                raise ApiError('Informe quantidades positivas para os itens da nota.')
            item_key = str(uuid5(base_key, f'item:{index}:{part_id}'))
            payload = {
                'kind': 'ENTRADA', 'quantity': str(quantity),
                'movementDate': received, 'supplier': supplier,
                'documentReference': reference, 'requestKey': item_key,
                'note': item.get('note', ''),
            }
            try:
                movement, _ = record_movement(part_id, payload, context.user)
            except ValidationError as exc:
                raise ApiError(' '.join(exc.messages), 400)
            recorded.append({
                'partId': part_id, 'movementId': movement.pk,
                'quantity': str(quantity), 'resulting': str(movement.resulting_quantity),
            })
    return Result({'items': recorded, 'supplier': supplier, 'documentReference': reference}, status=201)
