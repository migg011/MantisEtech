"""Regras de estoque: bloqueio por peça, auditoria e proteção contra repetição de comando."""
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import SparePart, StockMovement


def record_movement(part_id, data, user):
    kind = data.get('kind')
    if kind not in ('INICIAL', 'ENTRADA', 'SAIDA', 'AJUSTE'):
        raise ValidationError('Selecione um tipo válido de movimentação.')
    try:
        request_key = UUID(str(data.get('requestKey', '')))
        quantity = Decimal(str(data.get('quantity', '')))
        if not quantity.is_finite() or quantity < 0 or quantity >= Decimal(
                '100000000000') or quantity.as_tuple().exponent < -3:
            raise ValueError
    except (ValueError, InvalidOperation, TypeError):
        raise ValidationError(
            'Informe uma quantidade válida, com até três casas decimais, e uma chave de requisição válida.')
    if kind in ('ENTRADA', 'SAIDA') and quantity <= 0:
        raise ValidationError('Entradas e saídas precisam de quantidade maior que zero.')
    note = data.get('note', '')
    if not isinstance(note, str) or len(note.strip()) > 500:
        raise ValidationError('A observação deve ter até 500 caracteres.')
    # Observação é opcional; a descrição automática identifica a operação sem inventar uma justificativa.
    note = note.strip() or {'INICIAL': 'Primeira contagem do estoque', 'ENTRADA': 'Entrada de peças',
                            'SAIDA': 'Saída de peças para manutenção', 'AJUSTE': 'Ajuste por contagem do estoque'}[
        kind]
    date_text = data.get('movementDate', timezone.localdate().isoformat())
    try:
        if not isinstance(date_text, str) or len(date_text) != 10 or date_text[4] != '-' or date_text[
            7] != '-': raise ValueError
        movement_date = date.fromisoformat(date_text)
        if movement_date.year < 1900 or movement_date > timezone.localdate(): raise ValueError
    except (ValueError, TypeError):
        raise ValidationError('Informe uma data válida, sem ultrapassar a data de hoje.')
    supplier = data.get('supplier', '')
    document = data.get('documentReference', '')
    if not isinstance(supplier, str) or len(supplier.strip()) > 160 or not isinstance(document, str) or len(
            document.strip()) > 100:
        raise ValidationError('Fornecedor: até 160 caracteres. Nota fiscal ou documento: até 100 caracteres.')
    supplier, document = supplier.strip(), document.strip()
    if kind not in ('INICIAL', 'ENTRADA') and (supplier or document):
        raise ValidationError('Fornecedor e nota fiscal são informações da entrada de peças.')
    with transaction.atomic():
        # Duas saídas simultâneas leem o saldo em sequência, impedindo estoque negativo.
        part = get_object_or_404(SparePart.objects.select_for_update(), pk=part_id, active=True)
        previous = StockMovement.objects.filter(request_key=request_key).first()
        if previous:
            # Repetições de chamadas antigas, sem data informada, continuam reconhecidas.
            repeated_date = None if previous.movement_date is None and 'movementDate' not in data else movement_date
            if (previous.spare_part_id, previous.kind, previous.quantity, previous.note, previous.performed_by_id,
                previous.movement_date, previous.supplier, previous.document_reference) != (part.pk, kind, quantity,
                                                                                           note, user.pk,
                                                                                           repeated_date, supplier,
                                                                                           document):
                raise ValidationError('Esta chave já foi utilizada para outra movimentação.')
            return previous, False
        balance = part.stock_quantity
        if kind == 'INICIAL' and balance is not None:
            raise ValidationError('O saldo inicial já foi registrado. Use entrada, saída ou contagem de ajuste.')
        if kind != 'INICIAL' and balance is None:
            raise ValidationError('Registre a contagem inicial desta peça antes de movimentá-la.')
        new_balance = quantity if kind in ('INICIAL', 'AJUSTE') else balance + (
            quantity if kind == 'ENTRADA' else -quantity)
        if new_balance < 0:
            raise ValidationError('Saldo insuficiente para esta saída.')
        if new_balance >= Decimal('100000000000'):
            raise ValidationError('O saldo resultante excede o limite permitido.')
        movement = StockMovement.objects.create(spare_part=part, kind=kind, quantity=quantity,
                                                previous_quantity=balance,
                                                delta=new_balance - (balance or Decimal('0')),
                                                resulting_quantity=new_balance, performed_by=user, note=note,
                                                movement_date=movement_date, supplier=supplier,
                                                document_reference=document, request_key=request_key)
        part.stock_quantity = new_balance
        part.updated_at = timezone.now()
        part.save(update_fields=['stock_quantity', 'updated_at'])
        return movement, True


def stock_status(part):
    if part.stock_quantity is None: return 'Não informado'
    if part.stock_quantity == 0: return 'Sem estoque'
    if part.stock_quantity <= part.reorder_point: return 'Repor'
    if part.stock_quantity < part.minimum_stock: return 'Abaixo do mínimo'
    return 'Disponível'
