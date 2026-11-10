"""Regras de negócio reutilizáveis; transações evitam gravações parciais e disputas por posições."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import Equipment, EquipmentMovement, Line, PurchaseEvent, PurchaseRequest, Sector, SparePartTechnical, \
    TECHNICAL_FIELDS


@transaction.atomic
def transfer_equipment(equipment_id, origin_id, destination_id, reason, actor):
    """Muda apenas o setor da máquina livre e registra a transferência na mesma transação."""
    destination = Sector.objects.select_for_update().get(pk=destination_id, active=True)
    equipment = Equipment.objects.select_for_update().get(pk=equipment_id, active=True)
    if equipment.sector_id != origin_id:
        raise ValidationError('O setor da máquina mudou. Atualize o repositório antes de transferir.')
    if equipment.line_id is not None:
        raise ValidationError('Retire o equipamento da linha antes de transferi-lo.')
    if equipment.sector_id == destination.pk:
        raise ValidationError('Escolha um setor diferente do setor de origem.')
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
        raise ValidationError('Informe o motivo da transferência com 3 a 500 caracteres.')
    EquipmentMovement.objects.create(equipment=equipment, from_sector_id=equipment.sector_id,
                                     to_sector=destination, action='TRANSFERENCIA', reason=reason.strip(),
                                     performed_by=actor)
    equipment.sector = destination
    equipment.save(update_fields=['sector'])
    return equipment


def generate_internal_code(prefix):
    """Gera um código interno independente do nome exibido na interface."""
    return prefix + '-' + uuid4().hex


@transaction.atomic
def allocate_equipment(line_id, equipment_id, position, actor):
    """Trava linha e equipamento, confere setor e posição e grava alocação e histórico atomicamente."""
    # The locks last until the end of the transaction, serializing disputes over the same assembly.
    line = Line.objects.select_for_update().get(pk=line_id, active=True)
    record = Equipment.objects.select_for_update().get(pk=equipment_id, active=True)
    if record.line_id is not None or record.sector_id != line.sector_id:
        raise ValidationError('Equipamento indisponível ou pertencente a outro setor.')
    if Equipment.objects.filter(line=line, position=position).exists():
        raise ValidationError('A posição já está ocupada.')
    record.line, record.position = line, position
    record.save(update_fields=['line', 'position'])
    EquipmentMovement.objects.create(equipment=record, to_line=line, to_position=position, action='ALOCACAO',
                                     performed_by=actor)


@transaction.atomic
def remove_equipment(line_id, equipment_id, actor):
    """Trava os registros para devolver a máquina ao repositório e manter o histórico consistente."""
    line = Line.objects.select_for_update().get(pk=line_id, active=True)
    record = Equipment.objects.select_for_update().get(pk=equipment_id, line=line, active=True)
    EquipmentMovement.objects.create(equipment=record, from_line=line, from_position=record.position,
                                     action='REMOCAO', performed_by=actor)
    record.line, record.position = None, None
    record.save(update_fields=['line', 'position'])


@transaction.atomic
def dismantle_line(line_id, actor):
    """Registra as retiradas e libera posições em uma transação, sem excluir equipamentos ou ordens."""
    line = Line.objects.select_for_update().get(pk=line_id, active=True)
    items = list(Equipment.objects.select_for_update().filter(line=line))
    for record in items:
        EquipmentMovement.objects.create(equipment=record, from_line=line, from_position=record.position,
                                         action='DESMONTAGEM', performed_by=actor)
    Equipment.objects.filter(line=line).update(line=None, position=None)
    return len(items)


REQUIRED_TECHNICAL_FIELDS = ['description_en', 'description_pt', 'classification', 'independent_function',
                             'useful_life', 'asset_classification', 'main_function', 'raw_material', 'intended_use',
                             'application_machine']


@transaction.atomic
def submit_purchase(pk, actor):
    """Confere ficha e validação fiscal; congela os dados de todos os itens e encaminha ao gestor."""
    purchase = PurchaseRequest.objects.select_for_update().get(pk=pk)
    if purchase.requester_id != actor.pk or purchase.status not in ('RASCUNHO', 'DEVOLVIDA'):
        raise ValidationError('Somente o solicitante pode encaminhar um rascunho ou uma solicitação devolvida.')
    items = list(purchase.items.select_related('spare_part').order_by('pk'))
    if not items:
        raise ValidationError('Adicione pelo menos uma peça.')
    required = REQUIRED_TECHNICAL_FIELDS + (
        ['ncm', 'pli_description'] if purchase.purchase_type == 'IMPORTACAO' else [])
    for record in items:
        sheet = SparePartTechnical.objects.select_for_update().filter(spare_part=record.spare_part).first()
        missing = [TECHNICAL_FIELDS[key] for key in required if
                   not str(getattr(sheet, key, '') or '').strip()]
        if missing:
            raise ValidationError(f'Ficha incompleta de {record.spare_part}: ' + ', '.join(missing))
        if purchase.purchase_type == 'IMPORTACAO' and sheet.fiscal_status != 'VALIDADA':
            raise ValidationError('Importação requer classificação fiscal validada internamente.')
        # The export reads this copy; later changes to the part registration do not rewrite the submission.
        record.technical_snapshot = {key: getattr(sheet, key) for key in TECHNICAL_FIELDS}
        record.technical_snapshot['part_number'] = record.spare_part.part_number
        record.technical_snapshot['description'] = record.spare_part.description
        record.technical_snapshot['manufacturer'] = record.spare_part.manufacturer
        record.save(update_fields=['technical_snapshot'])
    purchase.status = 'EM_APROVACAO'
    purchase.submitted_at = purchase.updated_at = timezone.now()
    purchase.save(update_fields=['status', 'submitted_at', 'updated_at'])
    PurchaseEvent.objects.create(request=purchase, actor=actor, action='SUBMISSAO')


@transaction.atomic
def decide_purchase(pk, actor, decision, comment):
    """Aceita decisão somente do administrador designado quando a compra está em aprovação."""
    purchase = PurchaseRequest.objects.select_for_update().get(pk=pk)
    if actor.role != 'ADMINISTRADOR' or purchase.manager_id != actor.pk or purchase.status != 'EM_APROVACAO':
        raise ValidationError('Solicitação indisponível ou gestor não autorizado.')
    purchase.status, purchase.manager_comment = decision, comment
    purchase.decided_at = purchase.updated_at = timezone.now()
    purchase.save(update_fields=['status', 'manager_comment', 'decided_at', 'updated_at'])
    PurchaseEvent.objects.create(request=purchase, actor=actor, action=decision, details=comment)
