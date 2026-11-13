"""Casos de uso de comum do Mantis, separados do transporte HTTP."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms.models import model_to_dict

from ..exceptions import ApiError
from ..models import Equipment, PurchaseRequest, WorkOrder

MAINTENANCE_ROLES = ('ADMINISTRADOR', 'TECNICO')
TOKEN_SALT = 'mantis.angular.api.v1'


def require_role(context, *allowed):
    """Bloqueia operações no servidor mesmo se alguém contornar as restrições da interface."""
    if context.user.role not in allowed:
        raise PermissionDenied


def positive_id(value, label='Identificador'):
    """Valida identificadores e posições antes de usá-los em consultas ou movimentações."""
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ApiError(f'{label} inválido.')
    return int(value)


def serialize_record(record, exclude=()):
    """Serializa campos do modelo, omitindo hashes de senha e conteúdo binário dos arquivos."""
    return {field.attname: getattr(record, field.attname) for field in record._meta.concrete_fields
            if field.name not in {'password', 'content', 'photo_data', 'datasheet_data', *exclude}}


def user_data(user, *, login=False):
    """Expõe dados públicos da conta; no login usa lineId, conforme o modelo de usuário Angular."""
    data = {key: getattr(user, key) for key in ('id', 'name', 'registration', 'role', 'line_id', 'sector_id', 'active')}
    if login:
        data['lineId'] = data.pop('line_id')
    return data


def camel_name(name):
    """Converte nomes Python como root_cause para o formato rootCause recebido do Angular."""
    first, *rest = name.split('_')
    return first + ''.join(word.title() for word in rest)


def form_data(form_class, received_data, *, instance=None, aliases=None):
    """Mapeia os campos da tela para os validadores e preserva valores omitidos em edições PATCH."""
    data = model_to_dict(instance, fields=form_class._meta.fields,
                         exclude=form_class._meta.exclude) if instance else {}
    mapping = {camel_name(key): key for key in form_class.base_fields}
    mapping.update(aliases or {})
    for key, value in received_data.items():
        if key in mapping:
            data[mapping[key]] = value
    return data


def validate_form(form):
    """Executa a validação de cadastro pelo serializer, preservando as regras do domínio."""
    from ..serializers import FormValidationSerializer
    validator = FormValidationSerializer(data={}, context={'form': form})
    validator.is_valid(raise_exception=True)
    return form


def visible_equipment(user):
    """Restringe operadores à própria linha e técnicos ao próprio setor; o administrador vê tudo."""
    items = Equipment.objects.filter(active=True).select_related('equipment_type', 'sector', 'line')
    if user.role == 'OPERADOR':
        return items.filter(line_id=user.line_id, line__active=True) if user.line_id else items.none()
    if user.role == 'TECNICO':
        return items.filter(sector_id=user.sector_id) if user.sector_id else items.none()
    return items


def equipment_data(record):
    """Acrescenta nomes de tipo, setor e linha aos campos usados nas listas de equipamentos."""
    from .preventive_schedule import schedule_data
    return {**serialize_record(record), 'type_name': record.equipment_type.name,
            'preventive_schedules': [schedule_data(schedule) for schedule in record.preventive_schedules.all() if
                                     schedule.active],
            'sector_name': record.sector.name if record.sector else None,
            'line_name': record.line.name if record.line else None,
            'has_photo': getattr(record, 'has_photo', None) if getattr(record, 'has_photo',
                                                                         None) is not None else record.attachments.filter(
                kind='PHOTO').exists(),
            'open_order_count': getattr(record, 'open_order_count', 0),
            'in_progress_order_count': getattr(record, 'in_progress_order_count', 0)}


def visible_orders(user):
    """Impede que o operador consulte OS de equipamentos fora de sua linha."""
    items = WorkOrder.objects.select_related('equipment__equipment_type', 'equipment__line', 'opened_by',
                                             'assigned_to')
    return items.filter(equipment__in=visible_equipment(user)) if user.role == 'OPERADOR' else items


def visible_purchases(user):
    """Limita consultas ao solicitante ou gestor; administradores podem consultar todas as compras."""
    items = PurchaseRequest.objects.select_related('requester', 'manager', 'equipment')
    return items if user.is_admin else items.filter(Q(requester=user) | Q(manager=user))
