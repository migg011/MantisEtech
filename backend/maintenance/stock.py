"""Registra entradas, saídas e ajustes no estoque de uma peça."""
from decimal import Decimal, InvalidOperation
from uuid import UUID
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import SectorStock, SparePartCode, StockMovement

def record_movement(part_id, payload, user, sector=None):
    """Confere os dados, calcula o saldo e salva a movimentação."""
    movement_kind = payload.get('kind')
    if movement_kind not in ('INICIAL','ENTRADA','SAIDA','AJUSTE'):
        raise ValidationError('Selecione um tipo válido de movimentação.')
    try:
        request_key = UUID(str(payload.get('requestKey','')))
        quantity = Decimal(str(payload.get('quantity','')))
        if not quantity.is_finite() or quantity < 0 or quantity >= Decimal('100000000000') or quantity.as_tuple().exponent < -3:
            raise ValueError
    except (ValueError, InvalidOperation, TypeError):
        raise ValidationError('Informe uma quantidade válida, com até três casas decimais, e uma chave de requisição válida.')
    if movement_kind in ('ENTRADA','SAIDA') and quantity <= 0:
        raise ValidationError('Entradas e saídas precisam de quantidade maior que zero.')
    note = payload.get('note','')
    if not isinstance(note,str) or len(note.strip()) > 500:
        raise ValidationError('A observação deve ter até 500 caracteres.')
    # Se não houver observação, usa uma descrição do tipo de movimento.
    note = note.strip() or {'INICIAL':'Primeira contagem do estoque','ENTRADA':'Entrada de peças','SAIDA':'Saída de peças para manutenção','AJUSTE':'Ajuste por contagem do estoque'}[movement_kind]
    date_text=payload.get('movementDate',timezone.localdate().isoformat())
    try:
        if not isinstance(date_text,str) or len(date_text)!=10 or date_text[4]!='-' or date_text[7]!='-': raise ValueError
        movement_date=date.fromisoformat(date_text)
        if movement_date.year<1900 or movement_date>timezone.localdate(): raise ValueError
    except (ValueError,TypeError):
        raise ValidationError('Informe uma data válida, sem ultrapassar a data de hoje.')
    supplier=payload.get('supplier','')
    document_reference=payload.get('documentReference','')
    if not isinstance(supplier,str) or len(supplier.strip())>160 or not isinstance(document_reference,str) or len(document_reference.strip())>100:
        raise ValidationError('Fornecedor: até 160 caracteres. Nota fiscal ou documento: até 100 caracteres.')
    supplier,document_reference=supplier.strip(),document_reference.strip()
    if movement_kind not in ('INICIAL','ENTRADA') and (supplier or document_reference):
        raise ValidationError('Fornecedor e nota fiscal são informações da entrada de peças.')
    with transaction.atomic():
        # Uma movimentação por vez pode alterar o saldo desta peça.
        part = get_object_or_404(SparePartCode.objects.select_for_update(), pk=part_id, active=True)
        prior_movement = StockMovement.objects.filter(request_key=request_key).first()
        if prior_movement:
            if prior_movement.sector_id != (sector.pk if sector else None):
                raise ValidationError('Esta chave já foi utilizada para outro setor.')
            # Se a primeira chamada não tinha data, a repetição também pode vir sem data.
            replayed_date=None if prior_movement.movement_date is None and 'movementDate' not in payload else movement_date
            if (prior_movement.spare_part_id,prior_movement.kind,prior_movement.quantity,prior_movement.note,prior_movement.performed_by_id,prior_movement.movement_date,prior_movement.supplier,prior_movement.document_reference) != (part.pk,movement_kind,quantity,note,user.pk,replayed_date,supplier,document_reference):
                raise ValidationError('Esta chave já foi utilizada para outra movimentação.')
            return prior_movement, False
        if part.unit.strip().upper() == 'UN' and quantity != quantity.to_integral_value():
            raise ValidationError('Informe uma quantidade inteira para UN.')
        sector_stock = SectorStock.objects.filter(spare_part=part, sector=sector).first() if sector else None
        if sector:
            current_balance = sector_stock.quantity if sector_stock else None
        else:
            current_balance = part.stock_quantity
        if movement_kind == 'INICIAL' and current_balance is not None:
            raise ValidationError('O saldo inicial já foi registrado. Use entrada, saída ou contagem de ajuste.')
        if movement_kind != 'INICIAL' and current_balance is None:
            raise ValidationError('Registre a contagem inicial desta peça antes de movimentá-la.')
        new_balance = quantity if movement_kind in ('INICIAL','AJUSTE') else current_balance + (quantity if movement_kind=='ENTRADA' else -quantity)
        if new_balance < 0:
            raise ValidationError('Saldo insuficiente para esta saída.')
        if new_balance >= Decimal('100000000000'):
            raise ValidationError('O saldo resultante excede o limite permitido.')
        aggregate = new_balance
        if sector:
            aggregate = (part.stock_quantity or Decimal(0)) + new_balance - (current_balance or Decimal(0))
            if aggregate >= Decimal('100000000000'):
                raise ValidationError('O saldo total excede o limite permitido.')
            location = payload.get('storageLocation', sector_stock.location if sector_stock else '')
            if not isinstance(location, str) or len(location.strip()) > 160:
                raise ValidationError('Informe uma localização de até 160 caracteres.')
            SectorStock.objects.update_or_create(spare_part=part, sector=sector,
                defaults={'quantity': new_balance, 'location': location.strip()})
        elif SectorStock.objects.filter(spare_part=part).exists():
            raise ValidationError('Selecione o setor da movimentação.')
        movement = StockMovement.objects.create(spare_part=part,sector=sector,kind=movement_kind,quantity=quantity,previous_quantity=current_balance,delta=new_balance-(current_balance or Decimal('0')),resulting_quantity=new_balance,performed_by=user,note=note,movement_date=movement_date,supplier=supplier,document_reference=document_reference,request_key=request_key)
        part.stock_quantity=aggregate
        part.updated_at=timezone.now()
        part.save(update_fields=['stock_quantity','updated_at'])
        return movement, True

def stock_status(part):
    """Compara o saldo com os limites para mostrar a situação da peça."""
    if part.stock_quantity is None: return 'Não informado'
    if part.stock_quantity == 0: return 'Sem estoque'
    if part.stock_quantity <= part.reorder_point: return 'Repor'
    if part.stock_quantity < part.minimum_stock: return 'Abaixo do mínimo'
    return 'Disponível'
