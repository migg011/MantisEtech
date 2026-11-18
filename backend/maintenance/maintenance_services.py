"""Regras de negócio reutilizáveis; transações evitam gravações parciais e disputas por posições."""
from .compatibility_value import adapt_call

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import EquipmentCode, EquipmentMovementCode, LineCode, SectorCode, PurchaseRequestCode, PurchaseEventCode, SparePartTechnicalCode, TECHNICAL_FIELDS

@transaction.atomic
def transfer_equipment(equipment_id_value, source_id, destination_id, reason_value, actor_value):
    """Muda apenas o setor da máquina livre e registra a transferência na mesma transação."""
    destination = SectorCode.objects.select_for_update().get(pk=destination_id, active=True)
    equipment_value = EquipmentCode.objects.select_for_update().get(pk=equipment_id_value, active=True)
    if equipment_value.sector_id != source_id:
        raise ValidationError('O setor da máquina mudou. Atualize o repositório antes de transferir.')
    if equipment_value.line_id is not None:
        raise ValidationError('Retire o equipamento da linha antes de transferi-lo.')
    if equipment_value.sector_id == destination.pk:
        raise ValidationError('Escolha um setor diferente do setor de origem.')
    if not isinstance(reason_value, str) or not 3 <= len(reason_value.strip()) <= 500:
        raise ValidationError('Informe o motivo da transferência com 3 a 500 caracteres.')
    EquipmentMovementCode.objects.create(equipment=equipment_value, from_sector_id=equipment_value.sector_id,
        to_sector=destination, action='TRANSFERENCIA', reason=reason_value.strip(), performed_by=actor_value)
    equipment_value.sector = destination
    equipment_value.save(update_fields=['sector'])
    return equipment_value

def internal_code_value(prefix_value):
    """Gera um código interno independente do nome exibido na interface."""
    return prefix_value + '-' + uuid4().hex

@transaction.atomic
def allocate_value(line_id_value, equipment_id_value, position_value, actor_value):
    """Trava linha e equipamento, confere setor e posição e grava alocação e histórico atomicamente."""
    # Os bloqueios duram até o fim da transação, serializando disputas pela mesma montagem.
    row_value = LineCode.objects.select_for_update().get(pk=line_id_value, active=True)
    item_value = EquipmentCode.objects.select_for_update().get(pk=equipment_id_value, active=True)
    if item_value.line_id is not None or item_value.sector_id != row_value.sector_id:
        raise ValidationError('Equipamento indisponível ou pertencente a outro setor.')
    if EquipmentCode.objects.filter(line=row_value, position=position_value).exists():
        raise ValidationError('A posição já está ocupada.')
    item_value.line, item_value.position = row_value, position_value
    item_value.save(update_fields=['line', 'position'])
    EquipmentMovementCode.objects.create(equipment=item_value, to_line=row_value, to_position=position_value, action='ALOCACAO', performed_by=actor_value)

@transaction.atomic
def remove_equipment_value(line_id_value, equipment_id_value, actor_value):
    """Trava os registros para devolver a máquina ao repositório e manter o histórico consistente."""
    row_value = LineCode.objects.select_for_update().get(pk=line_id_value, active=True)
    item_value = EquipmentCode.objects.select_for_update().get(pk=equipment_id_value, line=row_value, active=True)
    EquipmentMovementCode.objects.create(equipment=item_value, from_line=row_value, from_position=item_value.position, action='REMOCAO', performed_by=actor_value)
    item_value.line, item_value.position = None, None
    item_value.save(update_fields=['line', 'position'])

@transaction.atomic
def dismantle_value(line_id_value, actor_value):
    """Registra as retiradas e libera posições em uma transação, sem excluir equipamentos ou ordens."""
    row_value = LineCode.objects.select_for_update().get(pk=line_id_value, active=True)
    items_value = list(EquipmentCode.objects.select_for_update().filter(line=row_value))
    for item_value in items_value:
        EquipmentMovementCode.objects.create(equipment=item_value, from_line=row_value, from_position=item_value.position, action='DESMONTAGEM', performed_by=actor_value)
    EquipmentCode.objects.filter(line=row_value).update(line=None, position=None)
    return len(items_value)

REQUIRED_TECHNICALCode = ['description_en', 'description_pt', 'classification', 'independent_function', 'useful_life', 'asset_classification', 'main_function', 'raw_material', 'intended_use', 'application_machine']

@transaction.atomic
def submit_purchase_value(pk, actor_value):
    """Confere ficha e validação fiscal; congela os dados de todos os itens e encaminha ao gestor."""
    purchase_value = PurchaseRequestCode.objects.select_for_update().get(pk=pk)
    if purchase_value.requester_id != actor_value.pk or purchase_value.status not in ('RASCUNHO', 'DEVOLVIDA'):
        raise ValidationError('Somente o solicitante pode encaminhar um rascunho ou uma solicitação devolvida.')
    items_value = list(purchase_value.items.select_related('spare_part').order_by('pk'))
    if not items_value:
        raise ValidationError('Adicione pelo menos uma peça.')
    required_value = REQUIRED_TECHNICALCode + (['ncm', 'pli_description'] if purchase_value.purchase_type == 'IMPORTACAO' else [])
    for item_value in items_value:
        profile_value = SparePartTechnicalCode.objects.select_for_update().filter(spare_part=item_value.spare_part).first()
        missing = [TECHNICAL_FIELDS[key_value] for key_value in required_value if not str(getattr(profile_value, key_value, '') or '').strip()]
        if missing:
            raise ValidationError(f'Ficha incompleta de {item_value.spare_part}: ' + ', '.join(missing))
        if purchase_value.purchase_type == 'IMPORTACAO' and profile_value.fiscal_status != 'VALIDADA':
            raise ValidationError('Importação requer classificação fiscal validada internamente.')
        # A exportação lê esta cópia; alterações posteriores no cadastro da peça não reescrevem o envio.
        item_value.technical_snapshot = {key_value: getattr(profile_value, key_value) for key_value in TECHNICAL_FIELDS}
        item_value.technical_snapshot['part_number'] = item_value.spare_part.part_number
        item_value.technical_snapshot['description'] = item_value.spare_part.description
        item_value.technical_snapshot['manufacturer'] = item_value.spare_part.manufacturer
        item_value.save(update_fields=['technical_snapshot'])
    purchase_value.status = 'EM_APROVACAO'
    purchase_value.submitted_at = purchase_value.updated_at = timezone.now()
    purchase_value.save(update_fields=['status', 'submitted_at', 'updated_at'])
    PurchaseEventCode.objects.create(request=purchase_value, actor=actor_value, action='SUBMISSAO')

@transaction.atomic
def decide_purchase_value(pk, actor_value, decision_value, comment_value):
    """Aceita decisão somente do administrador designado quando a compra está em aprovação."""
    purchase_value = PurchaseRequestCode.objects.select_for_update().get(pk=pk)
    if actor_value.role != 'ADMINISTRADOR' or purchase_value.manager_id != actor_value.pk or purchase_value.status != 'EM_APROVACAO':
        raise ValidationError('Solicitação indisponível ou gestor não autorizado.')
    if decision_value in ('DEVOLVIDA', 'REJEITADA') and not (comment_value or '').strip():
        raise ValidationError('Informe o motivo para devolver ou rejeitar a solicitacao.')
    purchase_value.status, purchase_value.manager_comment = decision_value, comment_value
    purchase_value.decided_at = purchase_value.updated_at = timezone.now()
    purchase_value.save(update_fields=['status', 'manager_comment', 'decided_at', 'updated_at'])
    PurchaseEventCode.objects.create(request=purchase_value, actor=actor_value, action=decision_value, details=comment_value)

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
internal_code = adapt_call(internal_code_value, {'prefix': 'prefix_value'})
allocate = adapt_call(allocate_value, {'actor': 'actor_value', 'line_id': 'line_id_value', 'equipment_id': 'equipment_id_value', 'position': 'position_value'})
remove_equipment = adapt_call(remove_equipment_value, {'actor': 'actor_value', 'line_id': 'line_id_value', 'equipment_id': 'equipment_id_value'})
dismantle = adapt_call(dismantle_value, {'actor': 'actor_value', 'line_id': 'line_id_value'})
submit_purchase = adapt_call(submit_purchase_value, {'actor': 'actor_value'})
decide_purchase = adapt_call(decide_purchase_value, {'actor': 'actor_value', 'decision': 'decision_value', 'comment': 'comment_value'})
REQUIRED_TECHNICAL = REQUIRED_TECHNICALCode
