"""API JSON consumida pelo Angular em mantis/frontend. O backend não renderiza telas.

Os endpoints recebem as requisições, conferem acesso e validam dados. As operações
de montagem e aprovação ficam em servicos.py; as demais views também usam o ORM de models.py. A autenticação
usa tokens Bearer assinados, com oito horas de validade, sem sessão por cookie."""
from .compatibility_value import adapt_call
import base64
import binascii
import csv
import hashlib
import io
from contextlib import nullcontext
import json
from datetime import timedelta
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import Trim
from django.forms.models import model_to_dict
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from . import forms, maintenance_services, stock
from .models import (UserCode, OperatorSession, SectorCode, LineCode, EquipmentTypeCode, EquipmentCode, EquipmentAttachmentCode,
                     WorkOrderCode, ProblemTypeCode, SparePartCode, SparePartCompatibilityCode, SparePartTechnicalCode,
                     PurchaseRequestCode, PurchaseEventCode, PartRequisitionCode, LinePendencyCode, PRIORITIES, TECHNICAL_FIELDS, StockMovement, SectorStock, ActivityLog, MaterialCategory, PreventiveOrder, PreventiveExecution)

STAFFCode = ('ADMINISTRADOR', 'TECNICO')
TOKEN_SALTCode = 'mantis.angular.api.v1'


class APIErrorCode(Exception):
    """Representa um erro esperado da API, com mensagem, status HTTP e detalhes opcionais."""
    def __init__(self, message, status=400, details=None):
        """Guarda mensagem, status HTTP e detalhes de validação para o decorador transformar em JSON."""
        self.message, self.status, self.details = message, status, details


def error_value(message_value, status_value, detail_value_value=None):
    """Padroniza erros JSON para os componentes Angular lerem error e, quando presente, details."""
    data_value = {'error': message_value}
    if detail_value_value is not None:
        data_value['details'] = detail_value_value
    return JsonResponse(data_value, status=status_value)


def bad_request_value(request_value, exception=None):
    """Responde a requisições inválidas com HTTP 400 no tratamento de erros do Django."""
    return error_value('Requisição inválida.', 400)


def forbidden_value(request_value, exception=None):
    """Informa que a conta autenticada não possui permissão para executar a operação."""
    return error_value('Acesso negado.', 403)


def not_found_value(request_value, exception=None):
    """Retorna HTTP 404 sem renderizar uma página de erro da aplicação."""
    return error_value('Recurso não encontrado.', 404)


def server_error_value(request_value):
    """Oculta detalhes internos na resposta de erro de produção."""
    return error_value('Erro interno.', 500)


# Cria o token que identifica o usuário nas próximas requisições.
def issue_token_value(user_value):
    """Assina identidade e hash de autenticação; uma troca de senha invalida tokens anteriores."""
    payload = {'uid': user_value.pk, 'auth': user_value.get_session_auth_hash()}
    if user_value.role == 'OPERADOR':
        now = timezone.now()
        OperatorSession.objects.filter(expires_at__lte=now).delete()
        session = OperatorSession.objects.create(user=user_value, expires_at=now + timedelta(seconds=settings.API_TOKEN_MAX_AGE))
        payload['operator_session'] = str(session.pk)
    return signing.dumps(payload, salt=TOKEN_SALTCode)


def bearer_user_value(request_value):
    """Confere assinatura, expiração e conta ativa antes de autorizar cada requisição."""
    scheme, _, token = request_value.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token or len(token) > 2048:
        raise APIErrorCode('Autenticação necessária.', 401)
    try:
        payload_value = signing.loads(token, salt=TOKEN_SALTCode, max_age=settings.API_TOKEN_MAX_AGE)
        user_value = UserCode.objects.get(pk=payload_value['uid'], active=True)
        if not constant_time_compare(payload_value['auth'], user_value.get_session_auth_hash()):
            raise APIErrorCode('Sessão expirada. Entre novamente.', 401)
        if user_value.role == 'OPERADOR':
            session = OperatorSession.objects.select_related('line').get(
                pk=payload_value['operator_session'], user=user_value, expires_at__gt=timezone.now(),
            )
            request_value.operator_session_id = session.pk
            user_value.operator_line_id = session.line_id if session.line and session.line.active and session.line.sector_id == user_value.sector_id else None
        elif 'operator_session' in payload_value:
            raise APIErrorCode('Seu perfil mudou. Entre novamente.', 401)
        return user_value
    except (signing.BadSignature, ObjectDoesNotExist, KeyError, TypeError, ValueError):
        raise APIErrorCode('Sessão inválida ou expirada. Entre novamente.', 401)


def endpoint_value(methods, *, roles_value=None, public_value=False):
    """Aplica métodos HTTP, autenticação e perfis; converte resultados e erros esperados em JSON."""
    def decorate(view):
        """Recebe a função do endpoint e devolve sua versão protegida pelo tratamento comum da API."""
        @wraps(view)
        def wrapped(request_value, *args, **kwargs):
            """Executa a sequência método HTTP, token, perfil, função de negócio e resposta JSON; converte falhas esperadas em status HTTP."""
            try:
                if request_value.method not in methods:
                    response_value = error_value('Método não permitido.', 405)
                    response_value['Allow'] = ', '.join(methods)
                    return response_value
                # Entrada protegida: a identidade vem da assinatura do token, não de um ID enviado pelo Angular.
                if not public_value:
                    request_value.user = bearer_user_value(request_value)
                    if roles_value:
                        require_role_value(request_value, *roles_value)
                login = view.__name__ == 'login_value_value'
                audit = request_value.method in ('POST', 'PUT', 'PATCH', 'DELETE') and (
                    login or (not public_value and view.__name__ != 'part_image_search')
                )
                with transaction.atomic() if audit else nullcontext():
                    result = view(request_value, *args, **kwargs)
                    response_value = result
                    if not isinstance(result, (HttpResponse, FileResponse)):
                        response_value = JsonResponse(result, safe=not isinstance(result, list))
                    if audit and 200 <= response_value.status_code < 300:
                        actor = request_value.user
                        route = request_value.resolver_match.route
                        target = {name: value for name, value in kwargs.items() if isinstance(value, int)}
                        if response_value.status_code == 201 and not target:
                            created = result if isinstance(result, dict) else json.loads(response_value.content)
                            if isinstance(created, dict) and isinstance(created.get('id'), int):
                                target['id'] = created['id']
                        ActivityLog.objects.create(
                            actor_id=actor.pk, actor_name=actor.name, actor_registration=actor.registration,
                            method=request_value.method, route=route, target=target,
                        )
                response_value['Cache-Control'] = 'no-store'
                return response_value
            except APIErrorCode as exc:
                return error_value(exc.message, exc.status, exc.details)
            except PermissionDenied:
                return forbidden_value(request_value)
            except (Http404, ObjectDoesNotExist):
                return not_found_value(request_value)
            except ValidationError as exc:
                return error_value(' '.join(exc.messages), 400)
            except IntegrityError:
                return error_value('Registro duplicado, posição ocupada ou associação inválida.', 409)
        return wrapped
    return decorate


def require_role_value(request_value, *allowed_value):
    """Bloqueia operações no servidor mesmo se alguém contornar as restrições da interface."""
    if request_value.user.role not in allowed_value:
        raise PermissionDenied


def body_value(request_value):
    """Aceita somente objetos JSON; formulários HTML e corpos malformados são rejeitados."""
    if request_value.content_type != 'application/json':
        raise APIErrorCode('Envie os dados como application/json.', 415)
    try:
        value_value = json.loads(request_value.body)
    except (ValueError, UnicodeDecodeError):
        raise APIErrorCode('JSON inválido.')
    if not isinstance(value_value, dict):
        raise APIErrorCode('O corpo deve ser um objeto JSON.')
    return value_value


def positive_id_value(value_value, label_value='Identificador'):
    """Valida identificadores e posições antes de usá-los em consultas ou movimentações."""
    if isinstance(value_value, bool) or not str(value_value).isdigit() or int(value_value) < 1:
        raise APIErrorCode(f'{label_value} inválido.')
    return int(value_value)


def record_value(item_value, exclude_value=()):
    """Serializa campos do modelo, omitindo hashes de senha e conteúdo binário dos arquivos."""
    return {field_value.attname: getattr(item_value, field_value.attname) for field_value in item_value._meta.concrete_fields
            if field_value.name not in {'password', 'content', 'photo_data', 'datasheet_data', *exclude_value}}


def user_data_value(user_value, *, login_value=False):
    """Expõe dados públicos da conta; no login usa lineId, conforme o modelo de usuário Angular."""
    data_value = {key_value: getattr(user_value, key_value) for key_value in ('id', 'name', 'registration', 'role', 'line_id', 'sector_id', 'active')}
    if login_value:
        data_value.pop('line_id')
        data_value['lineId'] = user_value.operator_line_id
    return data_value


def camel_value(name_value):
    """Converte nomes Python como root_cause para o formato rootCause recebido do Angular."""
    first, *rest = name_value.split('_')
    return first + ''.join(word.title() for word in rest)


def form_data_value(form_class, payload_value, *, instance_value=None, aliases=None):
    """Mapeia os campos da tela para os validadores e preserva valores omitidos em edições PATCH."""
    data_value = model_to_dict(instance_value, fields=form_class._meta.fields, exclude=form_class._meta.exclude) if instance_value else {}
    mapping = {camel_value(key_value): key_value for key_value in form_class.base_fields}
    mapping.update(aliases or {})
    for key_value, value_value in payload_value.items():
        if key_value in mapping:
            data_value[mapping[key_value]] = value_value
    return data_value


def validated_value(form):
    """Executa as validações de servidor e transforma erros de campos em uma resposta HTTP 400."""
    if not form.is_valid():
        detail_value_value = {key_value: [str(message_value) for message_value in messages] for key_value, messages in form.errors.items()}
        raise APIErrorCode(' '.join(message_value for messages in detail_value_value.values() for message_value in messages), details=detail_value_value)
    return form


def sector_scope(items, user, field='sector'):
    """Limita contas operacionais ao setor ativo cadastrado na conta."""
    if user.is_admin:
        return items
    if not user.sector_id:
        return items.none()
    return items.filter(**{f'{field}_id': user.sector_id, f'{field}__active': True})


def visible_equipment_value(user_value):
    """Restringe o operador aos equipamentos ativos de sua linha ativa, sem confiar nos filtros da tela."""
    items_value = EquipmentCode.objects.filter(active=True).select_related('equipment_type', 'sector', 'line')
    items_value = sector_scope(items_value, user_value)
    if user_value.role == 'OPERADOR':
        return items_value.filter(line_id=user_value.operator_line_id, line__active=True)
    return items_value


def equipment_data_value(item_value):
    """Acrescenta nomes de tipo, setor e linha aos campos usados nas listas de equipamentos."""
    from .schedule_rules import schedule_data_value
    return {**record_value(item_value), 'type_name': item_value.equipment_type.name,
            'preventive_schedules': [schedule_data_value(schedule_value) for schedule_value in item_value.preventive_schedules.all() if schedule_value.active],
            'sector_name': item_value.sector.name if item_value.sector else None,
            'line_name': item_value.line.name if item_value.line else None,
            'has_photo': getattr(item_value, 'has_photo', None) if getattr(item_value, 'has_photo', None) is not None else item_value.attachments.filter(kind='PHOTO').exists(),
            'open_order_count': getattr(item_value, 'open_order_count', 0),
            'in_progress_order_count': getattr(item_value, 'in_progress_order_count', 0)}


def visible_orders_value(user_value):
    """Impede que o operador consulte OS de equipamentos fora de sua linha."""
    items_value = WorkOrderCode.objects.select_related('equipment__equipment_type', 'equipment__line', 'opened_by', 'assigned_to')
    if user_value.role == 'OPERADOR':
        return items_value.filter(equipment__in=visible_equipment_value(user_value))
    return sector_scope(items_value, user_value, 'equipment__sector')


def visible_purchases_value(user_value):
    """Limita consultas ao solicitante ou gestor; administradores podem consultar todas as compras."""
    items_value = PurchaseRequestCode.objects.select_related('requester', 'manager', 'equipment')
    if user_value.is_admin:
        return items_value
    scoped = sector_scope(items_value, user_value, 'equipment__sector')
    return (scoped | items_value.filter(equipment__isnull=True)).filter(Q(requester=user_value) | Q(manager=user_value))


@endpoint_value(['GET'], public_value=True)
def health_value(request_value):
    """Identifica o processo da API para testar disponibilidade e encaminhamento pelo proxy Angular."""
    return {'service': 'MANTIS Django API', 'status': 'ok'}


@endpoint_value(['POST'], public_value=True)
def login_value_value(request_value):
    """Valida matrícula e senha, limita tentativas por origem e devolve token e usuário à tela de entrada."""
    data_value = body_value(request_value)
    # A API mantém as chaves anteriores; as variáveis de leitura estão em português.
    registration_number, senha = data_value.get('registration'), data_value.get('password')
    if not isinstance(registration_number, str) or not registration_number.strip() or not isinstance(senha, str) or not senha:
        raise APIErrorCode('Informe matrícula e senha.')
    chave_tentativas = 'login:' + hashlib.sha256(request_value.META.get('REMOTE_ADDR', '').encode()).hexdigest()
    cache.add(chave_tentativas, 0, 900)
    if cache.incr(chave_tentativas) > 10:
        raise APIErrorCode('Muitas tentativas. Aguarde 15 minutos.', 429)
    user_value = authenticate(request_value, username=registration_number.strip(), password=senha)
    if user_value is None:
        raise APIErrorCode('Matrícula ou senha inválida.', 401)
    cache.delete(chave_tentativas)
    request_value.user = user_value
    return {'token': issue_token_value(user_value), 'user': user_data_value(user_value, login_value=True)}


@endpoint_value(['GET'])
def me_value(request_value):
    """Devolve a conta conferida pelo token, permitindo consultar a identidade atual no backend."""
    return user_data_value(request_value.user, login_value=True)


@endpoint_value(['GET', 'POST', 'DELETE'], roles_value=('OPERADOR',))
def operator_line_value(request_value):
    """Lista postos e inicia ou encerra o acesso a uma linha na sessão autenticada."""
    allowed_lines = sector_scope(LineCode.objects.filter(active=True), request_value.user)
    if request_value.method == 'GET':
        lines = allowed_lines.values('id', 'name', 'description', 'sector__name')
        return {'lineId': request_value.user.operator_line_id, 'lines': [
            {'id': line['id'], 'name': line['name'], 'description': line['description'],
             'sector_name': line['sector__name']} for line in lines
        ]}

    with transaction.atomic():
        session = OperatorSession.objects.select_for_update().get(
            pk=request_value.operator_session_id, expires_at__gt=timezone.now(),
        )
        if request_value.method == 'DELETE':
            session.line = None
        else:
            line_id = positive_id_value(body_value(request_value).get('lineId'), 'Linha')
            line = get_object_or_404(allowed_lines, pk=line_id)
            if session.line_id != line_id and allowed_lines.filter(pk=session.line_id).exists():
                raise APIErrorCode('Saia da linha atual antes de escolher outra.', 409)
            session.line = line
        session.save(update_fields=['line'])
        return {'lineId': session.line_id}


@endpoint_value(['GET'], roles_value=('ADMINISTRADOR',))
def activity_log(request_value):
    entries = ActivityLog.objects.all()
    actor = request_value.GET.get('actor', '').strip()[:160]
    if actor:
        entries = entries.filter(Q(actor_name__icontains=actor) | Q(actor_registration__icontains=actor))
    method = request_value.GET.get('method')
    if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        entries = entries.filter(method=method)
    try:
        page = int(request_value.GET.get('page', '1'))
    except ValueError:
        raise APIErrorCode('Página inválida.')
    if not 1 <= page <= 100000:
        raise APIErrorCode('Página inválida.')
    start = (page - 1) * 50
    rows = list(entries.values()[start:start + 51])
    return {'items': rows[:50], 'has_next': len(rows) > 50}


@endpoint_value(['GET', 'POST', 'PATCH', 'DELETE'], roles_value=STAFFCode)
def sectors_value(request_value, pk=None):
    """Lista/cria setores e permite edição ou desativação administrativa sem apagar vínculos históricos."""
    if request_value.method == 'GET':
        return [record_value(item_value) for item_value in SectorCode.objects.filter(active=True)
                if request_value.user.is_admin or item_value.pk == request_value.user.sector_id]
    if request_value.method != 'POST':
        require_role_value(request_value, 'ADMINISTRADOR')
    with transaction.atomic():
        item_value = get_object_or_404(SectorCode.objects.select_for_update(), pk=pk, active=True) if pk else SectorCode(code=maintenance_services.internal_code_value('SET'))
        if request_value.method == 'DELETE':
            if (item_value.lines.exists() or item_value.feeders.exists() or SectorStock.objects.filter(sector=item_value).exists()
                    or UserCode.objects.filter(sector=item_value, active=True).exists()
                    or EquipmentCode.objects.filter(sector=item_value, active=True).exists()):
                raise APIErrorCode('O setor possui linhas, equipamentos, usuários ou feeders vinculados.', 409)
            item_value.active = False
            item_value.save(update_fields=['active'])
            return {'ok': True}
        data_value = form_data_value(forms.SectorFormCode, body_value(request_value), instance_value=item_value if pk else None)
        item_value = validated_value(forms.SectorFormCode(data_value, instance=item_value)).save()
        return JsonResponse(record_value(item_value), status=200 if pk else 201)


@endpoint_value(['PATCH'], roles_value=STAFFCode)
def edit_line(request_value, pk):
    """Atualiza apenas nome e descrição, preservando código, setor, equipamentos e OS."""
    with transaction.atomic():
        item_value = get_object_or_404(sector_scope(LineCode.objects.select_for_update(), request_value.user), pk=pk, active=True)
        data_value = form_data_value(forms.LineEditForm, body_value(request_value), instance_value=item_value)
        form = validated_value(forms.LineEditForm(data_value, instance=item_value))
        form.save()
        return record_value(item_value)


@endpoint_value(['GET', 'POST'])
def lines_value(request_value):
    """Cadastra linhas por setor e calcula quantidade de equipamentos e comprimento para a interface."""
    if request_value.method == 'POST':
        require_role_value(request_value, *STAFFCode)
        data_value = form_data_value(forms.LineFormCode, body_value(request_value), aliases={'sectorId': 'sector'})
        item_value = validated_value(forms.LineFormCode(data_value)).save(commit=False)
        if not request_value.user.is_admin and item_value.sector_id != request_value.user.sector_id:
            raise PermissionDenied
        item_value.code = maintenance_services.internal_code_value('LIN')
        item_value.save()
        return JsonResponse(record_value(item_value), status=201)
    items_value = LineCode.objects.filter(active=True).select_related('sector').annotate(
        equipment_count=Count('equipment', filter=Q(equipment__active=True)),
        length_mm=Sum('equipment__length_mm', filter=Q(equipment__active=True)))
    items_value = sector_scope(items_value, request_value.user)
    if request_value.user.role == 'OPERADOR':
        items_value = items_value.filter(pk=request_value.user.operator_line_id)
    return [{**record_value(item_value), 'sector_name': item_value.sector.name if item_value.sector else None,
             'equipment_count': item_value.equipment_count, 'length_mm': item_value.length_mm or 0} for item_value in items_value]


@endpoint_value(['POST'], roles_value=STAFFCode)
def allocate_value(request_value, pk):
    """Valida os dados de montagem e delega alocação e histórico à transação de serviços."""
    data_value = body_value(request_value)
    equipment_id_value, position_value = positive_id_value(data_value.get('equipmentId')), positive_id_value(data_value.get('position'), 'Posição')
    get_object_or_404(sector_scope(LineCode.objects.all(), request_value.user), pk=pk)
    maintenance_services.allocate_value(pk, equipment_id_value, position_value, request_value.user)
    return JsonResponse(equipment_data_value(EquipmentCode.objects.get(pk=equipment_id_value)), status=201)


@endpoint_value(['DELETE'], roles_value=STAFFCode)
def remove_equipment_value(request_value, pk, equipment_pk):
    """Retira uma máquina da linha e registra sua devolução ao repositório do setor."""
    get_object_or_404(sector_scope(LineCode.objects.all(), request_value.user), pk=pk)
    maintenance_services.remove_equipment_value(pk, equipment_pk, request_value.user)
    return {'ok': True}


@endpoint_value(['POST'], roles_value=STAFFCode)
def dismantle_value(request_value, pk):
    """Libera os equipamentos da linha e informa a quantidade devolvida, preservando cadastros e OS."""
    get_object_or_404(sector_scope(LineCode.objects.all(), request_value.user), pk=pk)
    return {'ok': True, 'released': maintenance_services.dismantle_value(pk, request_value.user)}


@endpoint_value(['GET', 'POST'])
def equipment_types_value(request_value):
    """Lista o catálogo e permite que administradores adicionem tipos."""
    types = EquipmentTypeCode.objects
    if request_value.method == 'GET':
        return list(types.values('id', 'name'))

    require_role_value(request_value, 'ADMINISTRADOR')
    name = body_value(request_value).get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100 or '\x00' in name:
        raise APIErrorCode('Informe um nome de até 100 caracteres.')
    name = name.strip()

    with transaction.atomic():
        # A tabela legada usa chaves manuais. Serialize a escolha do próximo ID.
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                table = connection.ops.quote_name(EquipmentTypeCode._meta.db_table)
                cursor.execute(f'LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE')
        if types.filter(name__iexact=name).exists():
            raise APIErrorCode('Esse tipo de equipamento já está cadastrado.', 409)
        next_id = (types.aggregate(last_id=Max('id'))['last_id'] or 0) + 1
        if next_id > 32767:
            raise APIErrorCode('O catálogo atingiu o limite de tipos de equipamento.', 409)
        item = types.create(id=next_id, name=name)
    return JsonResponse({'id': item.id, 'name': item.name}, status=201)


EQUIPMENT_REFERENCE_FIELDS = (
    'model_number', 'model', 'manufacturer',
    'description', 'process_description', 'length_mm', 'width_mm', 'height_mm',
    'weight_kg', 'voltage_v', 'current_a', 'power_w', 'frequency_hz', 'pneumatic_pressure_bar',
)


def matching_equipment(equipment_type_id, name):
    if not isinstance(name, str) or not name.strip():
        return EquipmentCode.objects.none()
    if not re.fullmatch(r'[0-9]{1,5}', str(equipment_type_id)):
        return EquipmentCode.objects.none()
    type_id = int(equipment_type_id)
    if not 1 <= type_id <= 32767:
        return EquipmentCode.objects.none()
    return (EquipmentCode.objects.filter(equipment_type_id=type_id, active=True)
            .annotate(reference_name=Trim('name')).filter(reference_name__iexact=name.strip()))


def equipment_reference(name):
    """Busca o primeiro cadastro com esse nome, inclusive se tiver sido desativado."""
    if not isinstance(name, str) or not name.strip():
        return None
    return (EquipmentCode.objects.alias(reference_name=Trim('name'))
            .filter(reference_name__iexact=name.strip()).order_by('created_at', 'pk').first())


def reference_frequencies(reference):
    return list(reference.preventive_schedules.filter(active=True).values_list('frequency', flat=True))


def equipment_photo_references(equipment_type_id, name):
    """Procura a primeira máquina desse tipo e nome que já tem foto."""
    return (EquipmentAttachmentCode.objects.filter(
        equipment__in=matching_equipment(equipment_type_id, name), kind='PHOTO',
    ).order_by('equipment__created_at', 'equipment_id'))


@endpoint_value(['GET'], roles_value=STAFFCode)
def equipment_reference_value(request):
    type_id, name = request.GET.get('equipmentTypeId'), request.GET.get('name')
    reference = equipment_reference(name)
    photo_filename = equipment_photo_references(type_id, name).values_list('filename', flat=True).first()
    return {
        'fields': {camel_value(field): getattr(reference, field) for field in EQUIPMENT_REFERENCE_FIELDS} if reference else None,
        'frequencies': reference_frequencies(reference) if reference else [],
        'photoFilename': photo_filename,
    }


@endpoint_value(['GET', 'POST', 'PATCH', 'DELETE'])
def equipment_value_value(request_value, pk=None):
    """Consulta o repositório/linha e valida cadastros técnicos; editar ou desativar exige administrador."""
    if request_value.method == 'GET':
        # O Totem recebe indicadores completos, sem depender da lista paginada de OS.
        items_value = visible_equipment_value(request_value.user).prefetch_related('preventive_schedules').annotate(
            has_photo=Exists(EquipmentAttachmentCode.objects.filter(equipment_id=OuterRef('pk'), kind='PHOTO')),
            open_order_count=Count('orders', filter=Q(orders__status__in=('ABERTA', 'EM_ANDAMENTO')), distinct=True),
            in_progress_order_count=Count('orders', filter=Q(orders__status='EM_ANDAMENTO'), distinct=True))
        if request_value.user.role != 'OPERADOR':
            for query, field_value in [('lineId', 'line_id'), ('sectorId', 'sector_id')]:
                if request_value.GET.get(query):
                    items_value = items_value.filter(**{field_value: positive_id_value(request_value.GET[query])})
            if request_value.GET.get('available') == 'true':
                items_value = items_value.filter(line=None)
        return [equipment_data_value(item_value) for item_value in items_value]
    require_role_value(request_value, *(STAFFCode if request_value.method == 'POST' else ('ADMINISTRADOR',)))
    from .preventive_planning import planning_lock
    with transaction.atomic():
        planning_lock()
        item_value = get_object_or_404(EquipmentCode.objects.select_for_update(), pk=pk, active=True) if pk else EquipmentCode()
        if request_value.method == 'DELETE':
            if item_value.line_id or item_value.orders.exists():
                raise APIErrorCode('Somente equipamentos disponíveis e sem OS podem ser excluídos.', 409)
            item_value.active = False
            item_value.save(update_fields=['active'])
            return {'ok': True}
        payload_value = body_value(request_value)
        from .schedule_rules import validate_schedules_value, sync_schedules_value
        # Ausente no PATCH preserva a agenda; lista vazia significa desmarcar as periodicidades.
        selections_value = validate_schedules_value(payload_value['preventiveSchedules']) if 'preventiveSchedules' in payload_value else None
        data_value = form_data_value(forms.EquipmentFormCode, payload_value, instance_value=item_value if pk else None,
                         aliases={'equipmentTypeId': 'equipment_type', 'sectorId': 'sector'})
        if request_value.method == 'POST':
            reference = equipment_reference(data_value.get('name'))
            if reference is not None:
                data_value.update({field: getattr(reference, field) for field in EQUIPMENT_REFERENCE_FIELDS})
                due_dates = dict(selections_value or ())
                selections_value = [(frequency, due_dates.get(frequency)) for frequency in reference_frequencies(reference)]
        form = validated_value(forms.EquipmentFormCode(data_value, instance=item_value))
        if not request_value.user.is_admin and form.cleaned_data['sector'].pk != request_value.user.sector_id:
            raise PermissionDenied
        item_value = form.save()
        if selections_value is not None:
            sync_schedules_value(item_value, selections_value)
        if request_value.method == 'POST' and payload_value.get('useReferencePhoto') is not False:
            photo = equipment_photo_references(item_value.equipment_type_id, item_value.name).first()
            if photo is not None:
                # Cada máquina recebe sua cópia, para a foto poder ser trocada depois.
                EquipmentAttachmentCode.objects.create(
                    equipment=item_value, kind='PHOTO', filename=photo.filename,
                    mime_type=photo.mime_type, content=photo.content, size_bytes=photo.size_bytes,
                    uploaded_by_id=photo.uploaded_by_id,
                )
        return JsonResponse(equipment_data_value(item_value), status=200 if pk else 201)


@endpoint_value(['GET'], roles_value=STAFFCode)
def movements_value(request_value, pk):
    """Expõe o histórico de alocações e retiradas com nomes das linhas e do responsável."""
    item_value = get_object_or_404(visible_equipment_value(request_value.user), pk=pk)
    return [{**record_value(movement), 'from_line': movement.from_line.name if movement.from_line else None,
             'to_line': movement.to_line.name if movement.to_line else None,
             'performed_by_name': movement.performed_by.name,
             'from_sector_name': movement.from_sector.name if movement.from_sector else None,
             'to_sector_name': movement.to_sector.name if movement.to_sector else None}
            for movement in item_value.movements.select_related('from_line', 'to_line', 'from_sector', 'to_sector', 'performed_by')]


@endpoint_value(['GET'], roles_value=STAFFCode)
def equipment_history(request_value, pk):
    """Lista serviços concluídos usando o vínculo permanente com o equipamento."""
    machine = get_object_or_404(visible_equipment_value(request_value.user), pk=pk)
    rows = []
    orders = machine.orders.filter(status='CONCLUIDA').only(
        'finished_at', 'problem', 'occurrence_description', 'corrective_action',
    ).prefetch_related('part_requisitions__spare_part')
    for order in orders:
        rows.append({
            'key': f'corrective-{order.pk}', 'number': f'#{order.pk}', 'type': 'CORRETIVA',
            'finishedAt': order.finished_at, 'reason': order.problem or order.occurrence_description,
            'services': [order.corrective_action] if order.corrective_action else [],
            'requestedParts': [
                {'id': item.pk, 'partNumber': item.spare_part.part_number,
                 'description': item.spare_part.description, 'quantity': item.quantity}
                for item in order.part_requisitions.all()
            ],
        })
    for order in PreventiveOrder.objects.filter(schedule__equipment=machine, status='CONCLUIDA'):
        services = [item for item, result in zip(order.items, order.results) if result.get('status') == 'REALIZADO']
        if order.notes:
            services.append(order.notes)
        rows.append({
            'key': f'preventive-{order.pk}', 'number': order.number, 'type': 'PREVENTIVA',
            'finishedAt': order.finished_at, 'performedDate': order.performed_date,
            'reason': f'Manutenção programada · {order.get_frequency_display()}', 'services': services,
        })
    for execution in PreventiveExecution.objects.filter(
        schedule__equipment=machine, order__isnull=True,
    ).select_related('schedule'):
        rows.append({
            'key': f'execution-{execution.pk}', 'number': None, 'type': 'PREVENTIVA',
            'finishedAt': None, 'performedDate': execution.performed_date,
            'reason': f'Manutenção programada · {execution.schedule.get_frequency_display()}',
            'services': [execution.notes] if execution.notes else [],
        })
    rows.sort(key=lambda row: (row['finishedAt'] or row.get('performedDate')).isoformat()
              if row['finishedAt'] or row.get('performedDate') else '', reverse=True)
    return rows


@endpoint_value(['POST'], roles_value=('ADMINISTRADOR',))
def transfer_equipment(request_value, pk):
    """Somente administrador transfere máquinas livres; mantém ID, anexos, agendas e OS."""
    data_value = body_value(request_value)
    equipment_value = maintenance_services.transfer_equipment(pk, positive_id_value(data_value.get('originSectorId')),
        positive_id_value(data_value.get('destinationSectorId')), data_value.get('reason'), request_value.user)
    return equipment_data_value(equipment_value)


@endpoint_value(['GET', 'POST', 'PUT'])
def attachments_value(request_value, pk, kind=None, download=False, inline=False):
    """Lista, baixa ou substitui anexos. PUT mantém o contrato JSON anterior."""
    item_value = get_object_or_404(visible_equipment_value(request_value.user), pk=pk)
    if kind and kind not in ('PHOTO', 'MANUAL', 'ELECTRICAL'):
        raise APIErrorCode('Categoria de anexo inválida.')
    if request_value.method == 'GET':
        if download or inline:
            attachment = get_object_or_404(EquipmentAttachmentCode, equipment=item_value, kind=kind)
            if inline and attachment.mime_type not in ('image/png', 'image/jpeg', 'application/pdf'):
                raise Http404
            return FileResponse(io.BytesIO(bytes(attachment.content)), as_attachment=download,
                                filename=attachment.filename, content_type=attachment.mime_type)
        return [record_value(attachment) for attachment in item_value.attachments.defer('content')]
    require_role_value(request_value, *STAFFCode)
    if request_value.method == 'POST':
        file = request_value.FILES.get('file')
        if not file:
            raise APIErrorCode('Envie o arquivo no campo file.')
        filename_value, mime_type = file.name, file.content_type
    else:
        data_value = body_value(request_value)
        filename_value, mime_type = data_value.get('filename'), data_value.get('mimeType')
    if not isinstance(filename_value, str) or not 1 <= len(filename_value.strip()) <= 180:
        raise APIErrorCode('Nome de arquivo inválido.')
    if request_value.method == 'PUT':
        try:
            content_value = base64.b64decode(data_value.get('base64'), validate=True)
        except (binascii.Error, ValueError, TypeError):
            raise APIErrorCode('Arquivo base64 inválido.')
        file = SimpleUploadedFile(filename_value, content_value)
    form = validated_value(forms.AttachmentFormCode({'kind': kind}, {'file': file}))
    if mime_type != form.cleaned_data['mime_type']:
        raise APIErrorCode('Conteúdo do arquivo não corresponde ao tipo informado.')
    content_value = file.read()
    attachment, _ = EquipmentAttachmentCode.objects.update_or_create(equipment=item_value, kind=kind, defaults={
        'filename': filename_value, 'content': content_value, 'mime_type': form.cleaned_data['mime_type'],
        'size_bytes': len(content_value), 'uploaded_by': request_value.user, 'created_at': timezone.now()})
    return record_value(attachment)


@endpoint_value(['GET', 'POST', 'PATCH'], roles_value=('ADMINISTRADOR',))
def users_value(request_value, pk=None, action=None):
    """Centraliza cadastro, edição, situação e senha com proteção da própria conta."""
    if request_value.method == 'GET':
        return [user_data_value(user_value) for user_value in UserCode.objects.all()]
    data_value = body_value(request_value)
    with transaction.atomic():
        item_value = get_object_or_404(UserCode.objects.select_for_update(), pk=pk) if pk else UserCode()
        if action == 'status':
            active = data_value.get('active')
            if not isinstance(active, bool):
                raise APIErrorCode('Situação inválida.')
            if item_value.pk == request_value.user.pk and not active:
                raise PermissionDenied
            item_value.active = active
            item_value.save(update_fields=['active'])
            if not active:
                OperatorSession.objects.filter(user=item_value).delete()
            return {'message': 'Situação atualizada.', 'user': user_data_value(item_value)}
        if action == 'password':
            form = validated_value(forms.PasswordFormCode(data_value))
            item_value.set_password(form.cleaned_data['password'])
            item_value.save(update_fields=['password'])
            return {'message': 'Senha redefinida com sucesso.'}
        mapped = form_data_value(forms.UserFormCode, data_value, instance_value=item_value if pk else None,
                           aliases={'password': 'new_password', 'sectorId': 'sector'})
        old_role = item_value.role
        old_sector_id = item_value.sector_id
        item_value = validated_value(forms.UserFormCode(mapped, instance=item_value, actor=request_value.user)).save()
        if old_role == 'OPERADOR' and (item_value.role != old_role or item_value.sector_id != old_sector_id):
            OperatorSession.objects.filter(user=item_value).delete()
        return JsonResponse(user_data_value(item_value), status=200 if pk else 201)


@endpoint_value(['GET', 'POST', 'PATCH', 'DELETE'])
def problem_types_value(request_value, pk=None):
    """Permite consultar problemas ativos; manutenção do catálogo é exclusiva da equipe técnica."""
    if request_value.method == 'GET':
        items_value = ProblemTypeCode.objects.select_related('equipment_type')
        if request_value.GET.get('includeInactive') == 'true':
            require_role_value(request_value, *STAFFCode)
        else:
            items_value = items_value.filter(active=True)
        if request_value.GET.get('equipmentTypeId'):
            kind_id = positive_id_value(request_value.GET['equipmentTypeId'])
            items_value = items_value.filter(Q(equipment_type=None) | Q(equipment_type_id=kind_id))
        return [{**record_value(item_value), 'type_name': item_value.equipment_type.name if item_value.equipment_type else None}
                for item_value in items_value]
    require_role_value(request_value, *STAFFCode)
    with transaction.atomic():
        item_value = get_object_or_404(ProblemTypeCode.objects.select_for_update(), pk=pk) if pk else ProblemTypeCode()
        if request_value.method == 'DELETE':
            item_value.active = False
            item_value.save(update_fields=['active'])
            return {'ok': True}
        data_value = form_data_value(forms.ProblemTypeFormCode, body_value(request_value), instance_value=item_value if pk else None,
                         aliases={'equipmentTypeId': 'equipment_type'})
        if not pk:
            data_value.setdefault('active', True)
            data_value.setdefault('priority', 'MEDIA')
        item_value = validated_value(forms.ProblemTypeFormCode(data_value, instance=item_value)).save()
        return JsonResponse(record_value(item_value), status=200 if pk else 201)


@endpoint_value(['GET', 'POST', 'PATCH'])
def orders_value_value(request_value, pk=None):
    """Abre OS no equipamento autorizado e registra atendimento, responsável e horários de execução."""
    if request_value.method == 'GET':
        if pk:
            return order_data_value(get_object_or_404(visible_orders_value(request_value.user), pk=pk))
        if request_value.GET.get('lineId'):
            items_value = visible_orders_value(request_value.user).filter(equipment__line_id=positive_id_value(request_value.GET['lineId']))
            return [order_data_value(order_value) for order_value in items_value.exclude(status='CONCLUIDA')] + [
                order_data_value(order_value) for order_value in items_value.filter(status='CONCLUIDA')[:20]]
        return [order_data_value(order_value) for order_value in visible_orders_value(request_value.user)[:200]]
    if request_value.method == 'POST':
        # Fronteira de integração: transforma JSON camelCase em campos aceitos pelo ModelForm.
        if request_value.user.role == 'OPERADOR' and not request_value.user.operator_line_id:
            raise PermissionDenied
        submitted_data = body_value(request_value)
        occurrence_description = submitted_data.get('occurrenceDescription', submitted_data.get('occurrence_description', ''))
        if not isinstance(occurrence_description, str):
            raise APIErrorCode('A descrição do ocorrido deve ser um texto.')
        data_value = form_data_value(forms.OrderFormCode, submitted_data, aliases={'equipmentId': 'equipment', 'problemTypeId': 'problem_type'})
        form = validated_value(forms.OrderFormCode(data_value, user=request_value.user))
        if not visible_equipment_value(request_value.user).filter(pk=form.cleaned_data['equipment'].pk).exists():
            raise PermissionDenied
        item_value = form.save(commit=False)
        # Congela a descrição da opção escolhida, mesmo que o catálogo seja renomeado depois.
        item_value.problem = form.cleaned_data['problem_type'].name
        item_value.opened_by = request_value.user
        item_value.save()
        return JsonResponse(order_data_value(item_value), status=201)
    require_role_value(request_value, *STAFFCode)
    with transaction.atomic():
        item_value = get_object_or_404(sector_scope(WorkOrderCode.objects.select_for_update(of=('self',)),
                                                     request_value.user, 'equipment__sector'), pk=pk)
        if item_value.status == 'CONCLUIDA':
            raise APIErrorCode('Esta OS já foi concluída.', 409)
        if not item_value.started_at or item_value.assigned_to_id != request_value.user.pk:
            raise APIErrorCode('Inicie o atendimento com sua matrícula e senha antes de alterar esta OS.', 409)
        data_value = form_data_value(forms.OrderUpdateFormCode, body_value(request_value), instance_value=item_value)
        item_value = validated_value(forms.OrderUpdateFormCode(data_value, instance=item_value)).save(commit=False)
        if item_value.status not in ('EM_ANDAMENTO', 'CONCLUIDA'):
            raise APIErrorCode('O atendimento iniciado deve permanecer em andamento ou ser concluído.', 409)
        # O relógio do servidor fixa o fim e o total; atualizar a tela depois não aumenta uma parada concluída.
        if item_value.status == 'CONCLUIDA' and not item_value.finished_at:
            item_value.finished_at = timezone.now()
            item_value.downtime_seconds = max(0, int((item_value.finished_at - item_value.created_at).total_seconds()))
        item_value.save()
        return order_data_value(item_value)


@endpoint_value(['GET'])
def line_status_value(request_value):
    """GET /api/line-status: entrega linhas visíveis, todas as OS ativas e as últimas 100 concluídas para o painel Angular."""
    lines = LineCode.objects.filter(active=True).select_related('sector').order_by('name')
    lines = sector_scope(lines, request_value.user)
    if request_value.user.role == 'OPERADOR':
        lines = lines.filter(pk=request_value.user.operator_line_id)
    lines = list(lines)
    items_value = visible_orders_value(request_value.user).filter(equipment__line_id__in=[row_value.pk for row_value in lines])
    # Diferente da listagem genérica, não limita OS ativas a 200: nenhuma ocorrência deve sumir do painel.
    active = list(items_value.exclude(status='CONCLUIDA').order_by('created_at'))
    history = list(items_value.filter(status='CONCLUIDA').order_by('-finished_at', '-created_at')[:100])
    return {'lines': [{**record_value(row_value), 'sector_name': row_value.sector.name if row_value.sector else None} for row_value in lines],
            'orders': [order_data_value(item_value) for item_value in active + history], 'server_now': timezone.now().isoformat()}


def order_data_value(order_value):
    """Monta o JSON de uma OS com máquina, operador, técnico e minutos; duração concluída usa o total registrado."""
    end = order_value.finished_at or timezone.now()
    seconds = order_value.downtime_seconds if order_value.downtime_seconds is not None else max(0, int((end - order_value.created_at).total_seconds()))
    return {**record_value(order_value), 'model': order_value.equipment.model, 'serial': order_value.equipment.serial,
            'asset_number': order_value.equipment.asset_number, 'type_name': order_value.equipment.equipment_type.name,
            'line_id': order_value.equipment.line_id, 'line_name': order_value.equipment.line.name if order_value.equipment.line else None,
            'opened_by': order_value.opened_by_id, 'assigned_to': order_value.assigned_to_id,
            'opened_by_name': order_value.opened_by.name,
            'assigned_to_name': order_value.assigned_to.name if order_value.assigned_to else None,
            'downtime_minutes': round(seconds / 60, 2), 'server_now': timezone.now().isoformat()}


@endpoint_value(['POST'], roles_value=STAFFCode)
# Registra o técnico e o horário de início da OS.
def start_order_value(request_value, pk):
    """POST /api/orders/:id/start: reconfirma a conta conectada e grava técnico/início uma única vez sob bloqueio transacional."""
    payload_value = body_value(request_value)
    registration, password = payload_value.get('registration'), payload_value.get('password')
    if not isinstance(registration, str) or not isinstance(password, str):
        raise APIErrorCode('Informe matrícula e senha.')
    key_value = f'order-start:{request_value.user.pk}'
    cache.add(key_value, 0, 900)
    if cache.incr(key_value) > 10:
        raise APIErrorCode('Muitas tentativas. Aguarde 15 minutos.', 429)
    user_value = authenticate(request_value, username=registration.strip(), password=password)
    if not user_value or user_value.pk != request_value.user.pk:
        raise APIErrorCode('Confirme a matrícula e senha do técnico conectado.', 403)
    cache.delete(key_value)
    with transaction.atomic():
        item_value = get_object_or_404(sector_scope(WorkOrderCode.objects.select_for_update(of=('self',)),
                                                     request_value.user, 'equipment__sector'), pk=pk)
        if item_value.status == 'CONCLUIDA':
            raise APIErrorCode('Esta OS já foi concluída.', 409)
        if item_value.started_at:
            if item_value.assigned_to_id != user_value.pk:
                raise APIErrorCode('Esta OS já está em atendimento por outro técnico.', 409)
        else:
            item_value.started_at = timezone.now()
            item_value.assigned_to = user_value
            item_value.status = 'EM_ANDAMENTO'
            item_value.save(update_fields=['started_at', 'assigned_to', 'status'])
    return order_data_value(item_value)


@endpoint_value(['GET'], roles_value=STAFFCode)
def order_parts_value(request_value, pk):
    """Consulta peças ativas e destaca os vínculos cadastrados com a máquina desta OS."""
    order_value = get_object_or_404(visible_orders_value(request_value.user), pk=pk)
    parts_value = SparePartCode.objects.filter(active=True).defer('photo_data', 'datasheet_data').annotate(
        compatible=Exists(SparePartCompatibilityCode.objects.filter(spare_part_id=OuterRef('pk'), equipment_id=order_value.equipment_id)))
    if request_value.GET.get('compatibleOnly') == 'true':
        parts_value = parts_value.filter(compatible=True)
    query = request_value.GET.get('q', '').strip()
    if query:
        parts_value = parts_value.filter(Q(description__icontains=query) | Q(part_number__icontains=query) | Q(manufacturer__icontains=query) | Q(code__icontains=query))
    return [{**record_value(part_value), 'compatible': part_value.compatible} for part_value in parts_value.order_by('-compatible', 'description')[:1000]]


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def order_purchases_value(request_value, pk):
    """Vincula a solicitação à OS do endereço, impedindo a troca silenciosa de máquina."""
    order_value = get_object_or_404(visible_orders_value(request_value.user), pk=pk)
    if request_value.method == 'GET':
        items_value = PurchaseRequestCode.objects.filter(work_order=order_value).select_related('requester', 'manager', 'equipment')
        return [purchase_data_value(item_value) for item_value in items_value]
    payload_value = body_value(request_value)
    for key_value, expected_value in [('workOrderId', order_value.pk), ('equipmentId', order_value.equipment_id)]:
        if key_value in payload_value and positive_id_value(payload_value[key_value]) != expected_value:
            raise APIErrorCode('A solicitação deve pertencer à OS e à máquina selecionadas.')
        payload_value[key_value] = expected_value
    return save_purchase_value(request_value, payload_value)


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def order_requisitions_value(request_value, pk):
    """Lista ou registra solicitação DIRETA de peça para a OS; deriva máquina/serial no servidor, sem criar compra."""
    order_value = get_object_or_404(visible_orders_value(request_value.user), pk=pk)
    def data_value(item_value):
        """Monta o JSON da solicitação direta incluindo descrição da peça, solicitante e situação solicitada."""
        return {**record_value(item_value), 'description': item_value.spare_part.description,
                'part_number': item_value.spare_part.part_number, 'requester_name': item_value.requester.name,
                'status': 'SOLICITADA'}
    if request_value.method == 'GET':
        return [data_value(item_value) for item_value in order_value.part_requisitions.select_related('spare_part', 'requester')]
    payload_value = body_value(request_value)
    part_value = get_object_or_404(SparePartCode, pk=positive_id_value(payload_value.get('sparePartId')), active=True)
    try:
        quantity = Decimal(str(payload_value.get('quantity', '')))
        if not quantity.is_finite() or quantity <= 0 or quantity >= Decimal('100000000000') or quantity.as_tuple().exponent < -3:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise APIErrorCode('Informe uma quantidade positiva com até três casas decimais.')
    note = payload_value.get('note', '')
    if not isinstance(note, str) or len(note) > 5000:
        raise APIErrorCode('Observação inválida (máximo de 5000 caracteres).')
    item_value = PartRequisitionCode.objects.create(work_order=order_value, equipment=order_value.equipment,
        equipment_serial=order_value.equipment.serial, spare_part=part_value, quantity=quantity,
        requester=request_value.user, note=note.strip())
    return JsonResponse(data_value(item_value), status=201)


def pendency_data_value(item_value):
    """Serializa a pendência acrescentando os nomes da linha e dos autores para a listagem Angular."""
    return {**record_value(item_value), 'line_name': item_value.line.name, 'equipment_model': item_value.equipment.model,
            'created_by_name': item_value.created_by.name,
            'resolved_by_name': item_value.resolved_by.name if item_value.resolved_by else None}


def pending_items_value():
    """Prepara a consulta de pendências com relacionamentos carregados para evitar uma consulta extra por nome exibido."""
    return LinePendencyCode.objects.select_related('line', 'equipment', 'created_by', 'resolved_by')


@endpoint_value(['GET', 'POST'], roles_value=STAFFCode)
def order_pendencies_value(request_value, pk):
    """Consulta ou cria pendência da OS, preservando linha e serial de origem independentemente do fechamento da OS."""
    order_value = get_object_or_404(visible_orders_value(request_value.user), pk=pk)
    if request_value.method == 'GET':
        return [pendency_data_value(item_value) for item_value in pending_items_value().filter(work_order=order_value)]
    payload_value = body_value(request_value)
    description = payload_value.get('description', '')
    priority = payload_value.get('priority', 'MEDIA')
    if not isinstance(description, str) or not 5 <= len(description.strip()) <= 5000:
        raise APIErrorCode('Descreva a pendência com 5 a 5000 caracteres.')
    if not isinstance(priority, str) or priority not in dict(PRIORITIES):
        raise APIErrorCode('Prioridade inválida.')
    with transaction.atomic():
        equipment_value = get_object_or_404(EquipmentCode.objects.select_for_update(), pk=order_value.equipment_id)
        if not equipment_value.line_id:
            raise APIErrorCode('A máquina desta OS precisa estar vinculada a uma linha.', 409)
        item_value = LinePendencyCode.objects.create(work_order=order_value, line_id=equipment_value.line_id,
            equipment=equipment_value, equipment_serial=equipment_value.serial, description=description.strip(),
            priority=priority, created_by=request_value.user)
    return JsonResponse(pendency_data_value(item_value), status=201)


@endpoint_value(['GET', 'PATCH'], roles_value=STAFFCode)
def line_pendencies_value(request_value, pk=None):
    """Filtra pendências para a Central; no PATCH registra solução, responsável e horário sem sobrescrever uma resolução anterior."""
    if request_value.method == 'GET':
        items_value = sector_scope(pending_items_value(), request_value.user, 'line__sector')
        if request_value.GET.get('lineId'):
            items_value = items_value.filter(line_id=positive_id_value(request_value.GET['lineId']))
        status_value = request_value.GET.get('status')
        if status_value:
            if status_value not in ('PENDENTE', 'RESOLVIDA'):
                raise APIErrorCode('Situação inválida.')
            items_value = items_value.filter(status=status_value)
        return [pendency_data_value(item_value) for item_value in items_value]
    payload_value = body_value(request_value)
    resolution = payload_value.get('resolution', '')
    if payload_value.get('status') != 'RESOLVIDA' or not isinstance(resolution, str) or not 5 <= len(resolution.strip()) <= 5000:
        raise APIErrorCode('Informe a solução com 5 a 5000 caracteres para resolver a pendência.')
    with transaction.atomic():
        item_value = get_object_or_404(sector_scope(LinePendencyCode.objects.select_for_update(of=('self',)),
                                                     request_value.user, 'line__sector'), pk=pk)
        if item_value.status == 'RESOLVIDA':
            raise APIErrorCode('Esta pendência já foi resolvida.', 409)
        item_value.status = 'RESOLVIDA'
        item_value.resolution = resolution.strip()
        item_value.resolved_by = request_value.user
        item_value.resolved_at = timezone.now()
        item_value.save(update_fields=['status', 'resolution', 'resolved_by', 'resolved_at'])
    return pendency_data_value(item_value)


def part_data_value(part_value):
    """Acrescenta os IDs de equipamentos compatíveis ao cadastro público da peça."""
    categories = list(part_value.categorias.all())
    return {**record_value(part_value), 'category':categories[0].name if categories else part_value.category, 'category_ids':[c.pk for c in categories], 'categories':[{'id':c.pk,'name':c.name,'active':c.active} for c in categories], 'stock_status': stock.stock_status(part_value), 'equipment_ids': list(part_value.compatibility.values_list('equipment_id', flat=True))}


@endpoint_value(['GET'], roles_value=STAFFCode)
def operational_dashboard(request_value):
    """Filtra os indicadores por linha e por janela de 7, 30 ou 90 dias."""
    from .dashboard import dashboard_summary
    days_value=request_value.GET.get('days','30')
    if days_value not in ('7','30','90'):
        raise APIErrorCode('Selecione um período de 7, 30 ou 90 dias.')
    equipment_value_value=visible_equipment_value(request_value.user)
    row_value=request_value.GET.get('lineId','')
    if row_value:
        line_id_value=positive_id_value(row_value)
        get_object_or_404(sector_scope(LineCode.objects.all(), request_value.user), pk=line_id_value, active=True)
        equipment_value_value=equipment_value_value.filter(line_id=line_id_value)
    return dashboard_summary(equipment_value_value,visible_orders_value(request_value.user),int(days_value))


@endpoint_value(['POST'], roles_value=STAFFCode)
def part_image_search(request_value):
    from .part_image_search import search_photo

    return search_photo(request_value.FILES.get('image'), request_value.POST.get('reference', '')[:200])


def stock_sector(user, sector_id):
    if sector_id in (None, ''):
        return user.sector if not user.is_admin else None
    sector = get_object_or_404(SectorCode, pk=positive_id_value(sector_id, 'Setor'), active=True)
    if not user.is_admin and sector.pk != user.sector_id:
        raise PermissionDenied
    return sector


def apply_sector_stock(parts, sector):
    if sector:
        balances = {row.spare_part_id: row for row in SectorStock.objects.filter(
            sector=sector, spare_part_id__in=[part.pk for part in parts],
        )}
        for part in parts:
            balance = balances.get(part.pk)
            part.stock_quantity = balance.quantity if balance else None
            part.storage_location = balance.location if balance else ''


@endpoint_value(['GET'], roles_value=STAFFCode)
def part_details(request_value, pk):
    """Busca os dados da peça para exibir a ficha."""
    part_value = get_object_or_404(SparePartCode.objects.defer('photo_data','datasheet_data').select_related('technical'), pk=pk, active=True)
    sector = stock_sector(request_value.user, request_value.GET.get('sectorId'))
    apply_sector_stock([part_value], sector)
    return {**part_data_value(part_value), 'technical': record_value(part_value.technical) if hasattr(part_value, 'technical') else None}


@endpoint_value(['GET'], roles_value=STAFFCode)
def part_photo(request_value, pk):
    """Envia a foto da peça para o usuário que tem acesso."""
    part_value = get_object_or_404(SparePartCode, pk=pk, active=True)
    if not part_value.photo_data:
        raise Http404
    return FileResponse(io.BytesIO(bytes(part_value.photo_data)), content_type=part_value.photo_mime,
                        filename=part_value.photo_filename or 'foto-peca.png')


@endpoint_value(['GET', 'POST', 'PATCH', 'DELETE'], roles_value=STAFFCode)
def material_categories(request_value, pk=None):
    """Lista as categorias e permite que administradores as atualizem."""
    if request_value.method == 'GET':
        items_value = MaterialCategory.objects.annotate(part_count=Count('pecas', filter=Q(pecas__active=True)))
        if request_value.GET.get('includeInactive') != 'true':
            items_value = items_value.filter(active=True)
        return [{'id':c.pk,'name':c.name,'description':c.description,'active':c.active,'part_count':c.part_count} for c in items_value]
    require_role_value(request_value, 'ADMINISTRADOR')
    with transaction.atomic():
        category = get_object_or_404(MaterialCategory.objects.select_for_update(), pk=pk) if pk else MaterialCategory()
        if request_value.method == 'DELETE':
            category.active=False
        else:
            data_value=body_value(request_value)
            for field_value, limit in [('name',100),('description',250)]:
                if field_value in data_value:
                    if not isinstance(data_value[field_value],str) or len(data_value[field_value]) > limit:
                        raise APIErrorCode('Nome ou descrição de categoria inválido.')
                    setattr(category,field_value,' '.join(data_value[field_value].split()))
            if not category.name:
                raise APIErrorCode('Informe o nome da categoria.')
            if 'active' in data_value:
                if not isinstance(data_value['active'],bool):
                    raise APIErrorCode('Situação da categoria inválida.')
                category.active=data_value['active']
            if MaterialCategory.objects.filter(name_key=MaterialCategory.key_value(category.name)).exclude(pk=category.pk).exists():
                raise APIErrorCode('Já existe uma categoria com esse nome.')
        category.save()
        return JsonResponse({'id':category.pk,'name':category.name,'description':category.description,'active':category.active},status=200 if pk else 201)


def filter_by_category(items_value, request_value):
    """O mesmo filtro é usado na tela e no relatório completo de inventário."""
    category=request_value.GET.get('categoryId','')
    if category:
        category_id=positive_id_value(category)
        get_object_or_404(MaterialCategory,pk=category_id)
        items_value=items_value.filter(categorias__pk=category_id)
    return items_value.prefetch_related('categorias').distinct()


@endpoint_value(['GET', 'POST', 'PATCH', 'DELETE'], roles_value=STAFFCode)
def parts_value(request_value, pk=None):
    """Mantém o cadastro mestre e suas compatibilidades; limites de estoque não representam movimentações."""
    if request_value.method == 'GET':
        items_value = SparePartCode.objects.filter(active=True).defer('photo_data', 'datasheet_data').prefetch_related('compatibility')
        items_value = filter_by_category(items_value, request_value)
        exact_part_number = request_value.GET.get('partNumber', '').strip()
        if exact_part_number:
            items_value = items_value.filter(part_number__iexact=exact_part_number)
        search_term = request_value.GET.get('q','').strip()
        if search_term:
            items_value = items_value.filter(Q(part_number__icontains=search_term) | Q(description__icontains=search_term) | Q(manufacturer__icontains=search_term))
        parts = list(items_value.order_by('part_number','description')[:500])
        sector = stock_sector(request_value.user, request_value.GET.get('sectorId'))
        apply_sector_stock(parts, sector)
        return [part_data_value(part) for part in parts]
    require_role_value(request_value, 'ADMINISTRADOR')
    with transaction.atomic():
        item_value = get_object_or_404(SparePartCode.objects.select_for_update(), pk=pk, active=True) if pk else SparePartCode(code=maintenance_services.internal_code_value('SP'))
        if request_value.method == 'DELETE':
            if item_value.stock_quantity is not None and item_value.stock_quantity > 0:
                raise APIErrorCode('Registre a saída ou ajuste do saldo antes de desativar a peça.', 409)
            item_value.active, item_value.updated_at = False, timezone.now()
            item_value.save(update_fields=['active', 'updated_at'])
            return {'ok': True}
        payload_value = body_value(request_value)
        if any(key_value in payload_value for key_value in ('stockQuantity','stock_quantity')):
            raise APIErrorCode('Altere o saldo pela opção Movimentar estoque, com histórico.')
        # Usa os IDs para buscar as categorias escolhidas no formulário.
        categories = None
        if 'categoryIds' in payload_value:
            ids = payload_value['categoryIds']
            if not isinstance(ids,list) or len(ids)>50 or any(type(i) is not int or i<=0 for i in ids):
                raise APIErrorCode('Selecione categorias válidas na lista.')
            ids=set(ids)
            categories=list(MaterialCategory.objects.filter(pk__in=ids))
            existing_ids=set(item_value.categorias.values_list('pk',flat=True)) if pk else set()
            if len(categories)!=len(ids) or any(not c.active and c.pk not in existing_ids for c in categories):
                raise APIErrorCode('Uma categoria não existe ou está inativa. Atualize a lista.')
        elif 'category' in payload_value and payload_value['category']:
            name_value=payload_value['category']
            if not isinstance(name_value,str):
                raise APIErrorCode('Selecione uma categoria da lista.')
            category=MaterialCategory.objects.filter(name_key=MaterialCategory.key_value(name_value),active=True).first()
            if not category:
                raise APIErrorCode('Cadastre a categoria antes de selecionar na peça.')
            categories=[category]
        photo = payload_value.get('photo')
        if 'photo' in payload_value:
            if not isinstance(photo, dict) or not isinstance(photo.get('filename'), str) or not 1 <= len(photo['filename'].strip()) <= 255:
                raise APIErrorCode('Informe um nome válido para a foto da peça.')
            try:
                photo_bytes = base64.b64decode(photo.get('base64'), validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise APIErrorCode('Foto em base64 inválida.')
            uploaded_file = validated_value(forms.AttachmentFormCode({'kind':'PHOTO'}, {'file':SimpleUploadedFile(photo['filename'], photo_bytes)}))
            if photo.get('mimeType') != uploaded_file.cleaned_data['mime_type']:
                raise APIErrorCode('O conteúdo da foto não corresponde ao tipo informado.')
            # Confere a foto antes de salvar a peça.
            item_value.photo_filename = photo['filename'].strip()
            item_value.photo_mime = uploaded_file.cleaned_data['mime_type']
            item_value.photo_data = photo_bytes
        data_value = form_data_value(forms.SparePartFormCode, payload_value, instance_value=item_value if pk else None, aliases={'equipmentIds': 'equipment'})
        if not pk:
            data_value = {'unit': 'UN', 'minimum_stock': 0, 'reorder_point': 0, **data_value}
        elif 'equipment' not in data_value:
            data_value['equipment'] = list(item_value.compatibility.values_list('equipment_id', flat=True))
        form = validated_value(forms.SparePartFormCode(data_value, instance=item_value))
        item_value = form.save(commit=False)
        item_value.updated_at = timezone.now()
        item_value.save()
        if categories is not None:
            item_value.categorias.set(categories)
            item_value.category=categories[0].name if categories else None
            item_value.save(update_fields=['category'])
        item_value.compatibility.all().delete()
        SparePartCompatibilityCode.objects.bulk_create([SparePartCompatibilityCode(spare_part=item_value, equipment=e) for e in form.cleaned_data['equipment']])
        return JsonResponse(part_data_value(item_value), status=200 if pk else 201)




def purchase_receipts(purchase):
    events = list(purchase.events.filter(action='RECEBIMENTO').exclude(receipt=None))
    totals = {}
    for event in events:
        for item in event.receipt['items']:
            part_id = item['partId']
            totals[part_id] = totals.get(part_id, Decimal(0)) + Decimal(item['quantity'])
    return events, totals


@endpoint_value(['POST'], roles_value=('ADMINISTRADOR',))
def stock_receipt(request_value):
    """Registra todas as entradas da nota na mesma transação."""
    payload = body_value(request_value)
    supplier = payload.get('supplier')
    reference = payload.get('documentReference')
    received = payload.get('movementDate')
    items = payload.get('items')
    if not isinstance(supplier, str) or not supplier.strip() or not isinstance(reference, str) or not reference.strip():
        raise APIErrorCode('Informe o fornecedor e o número da nota fiscal.')
    if not isinstance(received, str) or not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise APIErrorCode('Informe a data de recebimento e de 1 a 100 itens.')
    try:
        receipt_key = UUID(str(payload.get('requestKey', '')))
    except ValueError:
        raise APIErrorCode('Chave de requisição inválida.')
    purchase_id = payload.get('purchaseRequestId')
    common = {'supplier': supplier, 'documentReference': reference, 'movementDate': received}
    user = request_value.user
    movements = []
    seen = set()
    sector = stock_sector(user, payload.get('sectorId'))
    with transaction.atomic():
        # Bloqueia as peças existentes em ordem fixa, inclusive durante reenvios.
        if any(not isinstance(item, dict) for item in items):
            raise APIErrorCode('Item da nota inválido.')
        purchase = None
        if purchase_id is not None:
            purchase = get_object_or_404(
                PurchaseRequestCode.objects.select_for_update(),
                pk=positive_id_value(purchase_id, 'Solicitação'),
            )
            if sector and sector.pk != purchase.sector_id:
                raise APIErrorCode('A nota precisa entrar no setor da solicitação.')
            sector = purchase.sector
            events, totals = purchase_receipts(purchase)
            receipt_key = uuid5(receipt_key, f'purchase:{purchase.pk}')
            replay = next((event for event in events if event.receipt['key'] == str(receipt_key)), None)
            if not replay and purchase.status not in ('APROVADA', 'RECEBIDA_PARCIALMENTE'):
                raise APIErrorCode('A solicitação não está disponível para recebimento.', 409)
            approved = {}
            for part_id, quantity in purchase.items.values_list('spare_part_id', 'quantity'):
                approved[part_id] = approved.get(part_id, Decimal(0)) + quantity
            try:
                delivered = {positive_id_value(item.get('partId'), 'Peça'): Decimal(str(item.get('quantity')))
                             for item in items}
                if len(delivered) != len(items) or any(
                    not quantity.is_finite() or quantity <= 0 or part_id not in approved
                    for part_id, quantity in delivered.items()
                ):
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise APIErrorCode('Informe quantidades positivas para os itens da solicitação.')
            if replay:
                if replay.actor_id != user.pk or replay.receipt['payload'] != payload:
                    raise APIErrorCode('Esta chave já foi utilizada para outra entrada.', 409)
                return {'items': replay.receipt['items'], 'status': purchase.status}
            if any(event.receipt['supplier'].casefold() == supplier.strip().casefold()
                   and event.receipt['reference'].casefold() == reference.strip().casefold()
                   for event in events):
                raise APIErrorCode('Esta nota já foi registrada para a solicitação.', 409)
            for part_id, quantity in delivered.items():
                totals[part_id] = totals.get(part_id, Decimal(0)) + quantity
                if totals[part_id] > approved[part_id]:
                    raise APIErrorCode('A quantidade recebida ultrapassa o saldo pendente.')
        ids = {positive_id_value(item['partId'], 'Peça') for item in items if item.get('partId') is not None}
        locked = SparePartCode.objects.select_for_update().filter(pk__in=ids, active=True).order_by('pk')
        parts = {part.pk: part for part in locked}
        for index, item in enumerate(items):
            key = uuid5(receipt_key, f'entry:{index}')
            prior = StockMovement.objects.filter(request_key=key).select_related('spare_part').first()
            if purchase and prior:
                raise APIErrorCode('Esta solicitação já foi recebida ou a chave da nota já foi usada.', 409)
            if item.get('partId') is not None:
                part = parts.get(positive_id_value(item['partId'], 'Peça'))
                if part is None:
                    raise APIErrorCode(f'Item {index + 1}: peça indisponível.')
            else:
                number = item.get('partNumber')
                if not isinstance(number, str) or not number.strip():
                    raise APIErrorCode(f'Item {index + 1}: informe o Part Number.')
                if prior:
                    part = prior.spare_part
                    if (part.part_number or '').casefold() != number.strip().casefold():
                        raise APIErrorCode('Esta chave já foi utilizada para outra entrada.')
                else:
                    if SparePartCode.objects.filter(part_number__iexact=number.strip(), active=True).exists():
                        raise APIErrorCode(f'Item {index + 1}: selecione a peça que já está cadastrada.')
                    fields = {
                        'part_number': number.strip(), 'description': item.get('description'),
                        'manufacturer': item.get('manufacturer', ''), 'unit': item.get('unit', 'UN'),
                        'minimum_stock': 0, 'reorder_point': 0, 'preferred_supplier': supplier.strip(),
                    }
                    part = validated_value(forms.SparePartFormCode(fields, instance=SparePartCode(
                        code=maintenance_services.internal_code_value('SP')))).save()
            if part.pk in seen:
                raise APIErrorCode('Some as quantidades de uma mesma peça em uma única linha.')
            seen.add(part.pk)
            initialized = (SectorStock.objects.filter(spare_part=part, sector=sector).exists()
                           if sector else part.stock_quantity is not None)
            if not initialized:
                initial = item.get('previousQuantity') if item.get('partId') is not None else 0
                if initial is None:
                    raise APIErrorCode(f'Item {index + 1}: informe o saldo anterior ao recebimento.')
                stock.record_movement(part.pk, {
                    'kind': 'INICIAL', 'quantity': initial, 'movementDate': received,
                    'requestKey': str(uuid5(receipt_key, f'initial:{index}')),
                }, user, sector=sector)
            movement, _ = stock.record_movement(part.pk, {
                **common, 'kind': 'ENTRADA', 'quantity': item.get('quantity'), 'requestKey': str(key),
            }, user, sector=sector)
            movements.append({'partId': part.pk, 'partNumber': part.part_number,
                              'quantity': format(movement.quantity, '.3f'),
                              'resultingQuantity': format(movement.resulting_quantity, '.3f')})
        if purchase:
            complete = all(totals.get(part_id, 0) == quantity for part_id, quantity in approved.items())
            purchase.status = 'RECEBIDA' if complete else 'RECEBIDA_PARCIALMENTE'
            purchase.updated_at = timezone.now()
            purchase.save(update_fields=['status', 'updated_at'])
            PurchaseEventCode.objects.create(
                request=purchase, actor=user, action='RECEBIMENTO',
                details=f'NF {reference.strip()} · {supplier.strip()} · Recebimento em {received}',
                receipt={'key': str(receipt_key), 'supplier': supplier.strip(), 'reference': reference.strip(),
                         'payload': payload, 'items': movements},
            )
            return {'items': movements, 'status': purchase.status}
    return {'items': movements}


@endpoint_value(['GET','POST'], roles_value=STAFFCode)
def stock_movements(request_value, pk):
    """Técnicos consultam; administradores lançam saldo inicial, entrada, saída e ajuste."""
    if request_value.method == 'POST':
        require_role_value(request_value, 'ADMINISTRADOR')
        payload = body_value(request_value)
        sector = stock_sector(request_value.user, payload.get('sectorId'))
        movement, created_value = stock.record_movement(pk, payload, request_value.user, sector=sector)
        return JsonResponse({'movement': record_value(movement), 'replayed':not created_value}, status=201 if created_value else 200)
    get_object_or_404(SparePartCode,pk=pk)
    sector = stock_sector(request_value.user, request_value.GET.get('sectorId'))
    movements = StockMovement.objects.filter(spare_part_id=pk).select_related('performed_by', 'sector')
    if sector:
        movements = movements.filter(sector=sector)
    return [{**record_value(m), 'performed_by_name': m.performed_by.name,
             'sector_name': m.sector.name if m.sector else None} for m in movements[:100]]


@endpoint_value(['GET'], roles_value=STAFFCode)
def parts_inventory(request_value, output_format='json'):
    """Lista todas as peças ativas e pode gerar um arquivo CSV."""
    items_value = SparePartCode.objects.filter(active=True).defer('photo_data','datasheet_data').order_by('part_number','description','pk')
    items_value = filter_by_category(items_value, request_value)
    search_term = request_value.GET.get('q','').strip()
    if search_term:
        items_value = items_value.filter(Q(part_number__icontains=search_term)|Q(description__icontains=search_term)|Q(manufacturer__icontains=search_term))
    sector = stock_sector(request_value.user, request_value.GET.get('sectorId'))
    items_value = list(items_value.prefetch_related('categorias'))
    apply_sector_stock(items_value, sector)
    generated_at = timezone.now()
    lines_value = [{'id':p.pk,'part_number':p.part_number,'description':p.description,'manufacturer':p.manufacturer,'storage_location':p.storage_location,'unit':p.unit,'stock_quantity':p.stock_quantity,'minimum_stock':p.minimum_stock,'maximum_stock':p.maximum_stock,'reorder_point':p.reorder_point,'stock_status':stock.stock_status(p),'categories':[c.name for c in p.categorias.all()]} for p in items_value]
    if output_format == 'csv':
        response_value = HttpResponse(content_type='text/csv; charset=utf-8')
        response_value['Content-Disposition']='attachment; filename="INVENTARIO_PECAS.csv"'
        response_value.write('\ufeff')
        writer=csv.writer(response_value,delimiter=';')
        writer.writerow(['Gerado em','Part Number','Descrição','Fabricante','Localização','Unidade','Saldo disponível','Situação','Mínimo','Máximo','Ponto de reposição','Categorias'])
        def cell(value_value):
            cell_text='' if value_value is None else str(value_value)
            return "'"+cell_text if cell_text.lstrip().startswith(('=','+','-','@')) else cell_text
        for p in lines_value:
            row_values=[timezone.localtime(generated_at).isoformat(),p['part_number'],p['description'],p['manufacturer'],p['storage_location'],p['unit'],p['stock_quantity'],p['stock_status'],p['minimum_stock'],p['maximum_stock'],p['reorder_point'],', '.join(p['categories'])]
            writer.writerow([cell(v) for v in row_values])
        return response_value
    return {'sector_id': sector.pk if sector else None, 'category_id':request_value.GET.get('categoryId',''),'category_name':MaterialCategory.objects.get(pk=request_value.GET['categoryId']).name if request_value.GET.get('categoryId') else '', 'generated_at':generated_at,'query':search_term,'items':lines_value,'total_items':len(lines_value),'uninitialized_items':sum(p['stock_quantity'] is None for p in lines_value)}


@endpoint_value(['GET'])
def managers_value(request_value):
    """Lista administradores ativos para o seletor de gestor responsável na solicitação de compra."""
    return list(UserCode.objects.filter(role='ADMINISTRADOR', active=True).values('id', 'name'))


@endpoint_value(['GET'])
def purchase_parts_value(request_value):
    """Fornece peças ativas e situação da ficha para os seletores da tela de compras."""
    return [{**record_value(part_value), 'fiscal_status': part_value.technical.fiscal_status if hasattr(part_value, 'technical') else 'PENDENTE'}
            for part_value in SparePartCode.objects.filter(active=True).defer('photo_data', 'datasheet_data').select_related('technical')[:1000]]


@endpoint_value(['GET', 'PUT', 'POST'], roles_value=STAFFCode)
def technical_value(request_value, pk, validate=False):
    """Consulta/salva a ficha ou registra validação administrativa; alterações revogam a validação anterior."""
    part_value = get_object_or_404(SparePartCode, pk=pk, active=True)
    if validate:
        require_role_value(request_value, 'ADMINISTRADOR')
    with transaction.atomic():
        profile_value = SparePartTechnicalCode.objects.select_for_update().filter(spare_part=part_value).first()
        if request_value.method == 'GET':
            return record_value(profile_value) if profile_value else {'spare_part_id': pk, 'fiscal_status': 'PENDENTE'}
        if validate:
            if profile_value is None or not (profile_value.ncm or '').strip() or not (profile_value.pli_description or '').strip():
                raise APIErrorCode('Preencha NCM e descrição para PLI antes da validação interna.', 409)
            profile_value.fiscal_status, profile_value.fiscal_validated_by = 'VALIDADA', request_value.user
            profile_value.fiscal_validated_at = timezone.now()
        else:
            payload_value = body_value(request_value)
            if not payload_value or set(payload_value) - set(TECHNICAL_FIELDS):
                raise APIErrorCode('Campos da ficha técnica inválidos.')
            data_value = {key_value: getattr(profile_value, key_value) for key_value in TECHNICAL_FIELDS} if profile_value else {}
            data_value.update(payload_value)
            profile_value = validated_value(forms.TechnicalFormCode(data_value, instance=profile_value or SparePartTechnicalCode(spare_part=part_value))).save(commit=False)
            profile_value.fiscal_status, profile_value.fiscal_validated_by, profile_value.fiscal_validated_at = 'PENDENTE', None, None
        profile_value.updated_at = timezone.now()
        profile_value.save()
        return record_value(profile_value)


def purchase_data_value(purchase_value):
    """Inclui os nomes do solicitante e do gestor para a tabela de acompanhamento Angular."""
    return {**record_value(purchase_value), 'requester_name': purchase_value.requester.name, 'manager_name': purchase_value.manager.name,
            'sector_name': purchase_value.sector.name if purchase_value.sector else None,
            'cost_center': purchase_value.sector.cost_center if purchase_value.sector else '',
            'equipment_model': purchase_value.equipment.model if purchase_value.equipment else None}


@endpoint_value(['GET', 'POST', 'PATCH'])
def purchases_value(request_value, pk=None):
    """Lista/detalha compras ou grava rascunho e itens na mesma transação, preservando autoria e estado."""
    if request_value.method == 'GET':
        if not pk:
            return [purchase_data_value(item_value) for item_value in visible_purchases_value(request_value.user)[:200]]
        item_value = get_object_or_404(visible_purchases_value(request_value.user), pk=pk)
        items_value = []
        balances = dict(SectorStock.objects.filter(
            sector_id=item_value.sector_id, spare_part_id__in=item_value.items.values('spare_part_id'),
        ).values_list('spare_part_id', 'quantity')) if item_value.sector_id else None
        for row_value in item_value.items.select_related('spare_part', 'spare_part__technical').order_by('pk'):
            profile_value = row_value.spare_part.technical if hasattr(row_value.spare_part, 'technical') else None
            items_value.append({**(record_value(profile_value) if profile_value else {}), **record_value(row_value),
                          'code': row_value.spare_part.code, 'part_number': row_value.spare_part.part_number,
                          'description': row_value.spare_part.description, 'manufacturer': row_value.spare_part.manufacturer,
                          'unit': row_value.spare_part.unit, 'stock_quantity': balances.get(row_value.spare_part_id) if balances is not None else row_value.spare_part.stock_quantity})
        _, totals = purchase_receipts(item_value)
        for item in items_value:
            part_id = item['spare_part_id']
            quantity = Decimal(item['quantity'])
            received = quantity if item_value.status == 'RECEBIDA' else min(quantity, totals.get(part_id, Decimal(0)))
            item['received_quantity'] = received
            item['pending_quantity'] = quantity - received
            totals[part_id] = totals.get(part_id, Decimal(0)) - received
        return {**purchase_data_value(item_value), 'items': items_value, 'events': [{**record_value(event, ('receipt',)), 'actor_name': event.actor.name,
                     'receipt_items': event.receipt['items'] if event.receipt else []}
                    for event in item_value.events.select_related('actor')]}
    return save_purchase_value(request_value, body_value(request_value), pk)


def save_purchase_value(request_value, payload_value, pk=None):
    """Valida e grava o rascunho e os itens; o serial é obtido no servidor, nunca do navegador."""
    with transaction.atomic():
        item_value = get_object_or_404(PurchaseRequestCode.objects.select_for_update(), pk=pk) if pk else PurchaseRequestCode(requester=request_value.user)
        original_equipment_id = item_value.equipment_id
        if item_value.requester_id != request_value.user.pk or item_value.status not in ('RASCUNHO', 'DEVOLVIDA'):
            raise PermissionDenied
        data_value = form_data_value(forms.PurchaseFormCode, payload_value, instance_value=item_value if pk else None,
                         aliases={'managerId': 'manager', 'workOrderId': 'work_order', 'equipmentId': 'equipment'})
        item_value = validated_value(forms.PurchaseFormCode(data_value, instance=item_value, user=request_value.user)).save(commit=False)
        if item_value.equipment_id and not sector_scope(EquipmentCode.objects.all(), request_value.user).filter(pk=item_value.equipment_id).exists():
            raise PermissionDenied
        if item_value.work_order_id and not visible_orders_value(request_value.user).filter(pk=item_value.work_order_id).exists():
            raise PermissionDenied
        if payload_value.get('sectorId'):
            item_value.sector = stock_sector(request_value.user, payload_value['sectorId'])
        elif item_value.work_order_id:
            item_value.sector_id = item_value.work_order.equipment.sector_id
        elif item_value.equipment_id:
            item_value.sector_id = item_value.equipment.sector_id
        elif not item_value.sector_id:
            item_value.sector = request_value.user.sector
        if item_value.equipment_id and item_value.sector_id != item_value.equipment.sector_id:
            raise APIErrorCode('Use o setor do equipamento vinculado.')
        if item_value.work_order_id and item_value.sector_id != item_value.work_order.equipment.sector_id:
            raise APIErrorCode('Use o setor do equipamento da ordem de serviço.')
        if not pk or item_value.equipment_id != original_equipment_id:
            item_value.equipment_serial = item_value.equipment.serial if item_value.equipment else None
        entries = payload_value.get('items')
        if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
            raise APIErrorCode('Informe de 1 a 100 peças.')
        # Valida todos os itens antes de gravar. atomic desfaz o conjunto caso alguma etapa falhe.
        validated_items = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise APIErrorCode('Item de compra inválido.')
            mapped = form_data_value(forms.PurchaseItemFormCode, entry, aliases={'sparePartId': 'spare_part'})
            validated_items.append(validated_value(forms.PurchaseItemFormCode(mapped)).save(commit=False))
        item_value.updated_at = timezone.now()
        item_value.save()
        item_value.items.all().delete()
        for row_value in validated_items:
            row_value.request = item_value
            row_value.save()
        PurchaseEventCode.objects.create(request=item_value, actor=request_value.user, action='EDICAO' if pk else 'CRIACAO')
        return JsonResponse(purchase_data_value(item_value), status=200 if pk else 201)


@endpoint_value(['POST'])
def submit_purchase_value(request_value, pk):
    """Solicita conferência e congelamento dos dados técnicos; a aprovação será acompanhada no sistema."""
    get_object_or_404(visible_purchases_value(request_value.user), pk=pk)
    try:
        maintenance_services.submit_purchase_value(pk, request_value.user)
    except ValidationError as exc:
        # TODO integração: a tela Angular também lê missing para listar os campos pendentes por peça.
        # Este retorno fornece a mensagem geral; a lista estruturada ainda precisa ser alinhada.
        raise APIErrorCode(' '.join(exc.messages), 409)
    # O encaminhamento altera o estado da compra; não há integração de envio de e-mail neste backend.
    return {'ok': True, 'status': 'EM_APROVACAO', 'notification': 'SEM_DESTINATARIO_CONFIGURADO'}


@endpoint_value(['POST'], roles_value=('ADMINISTRADOR',))
def decide_purchase_value(request_value, pk):
    """Valida a decisão recebida e delega a autorização do gestor e o registro do evento ao serviço."""
    form = validated_value(forms.DecisionFormCode(body_value(request_value)))
    get_object_or_404(visible_purchases_value(request_value.user), pk=pk)
    try:
        maintenance_services.decide_purchase_value(pk, request_value.user, form.cleaned_data['decision'], form.cleaned_data['comment'])
    except ValidationError as exc:
        raise APIErrorCode(' '.join(exc.messages), 409)
    return {'id': pk, 'status': form.cleaned_data['decision']}


@endpoint_value(['GET'])
def export_purchase_value(request_value, pk):
    """Exporta os dados congelados no envio, neutralizando células que poderiam virar fórmulas."""
    item_value = get_object_or_404(visible_purchases_value(request_value.user), pk=pk)
    if item_value.status not in ('EM_APROVACAO', 'APROVADA', 'RECEBIDA_PARCIALMENTE', 'RECEBIDA'):
        raise APIErrorCode('Encaminhe a solicitação antes de exportar.', 409)
    response_value = HttpResponse(content_type='text/csv; charset=utf-8')
    response_value['Content-Disposition'] = f'attachment; filename="SC-{pk}-DADOS-TECNICOS.csv"'
    response_value.write('\ufeff')
    writer = csv.writer(response_value, delimiter=';')
    columns = {'part_number': 'Part Number', 'description':'Descrição da peça', 'manufacturer':'Fabricante', 'picture_reference': 'Picture', **TECHNICAL_FIELDS}
    writer.writerow(['OS', 'Equipamento', 'Serial da máquina', *columns.values()])
    for row_value in item_value.items.select_related('spare_part').order_by('pk'):
        values = [str(item_value.work_order_id or ''), (item_value.equipment.model or '') if item_value.equipment else '', item_value.equipment_serial or '']
        retrato = row_value.technical_snapshot or {}
        values += [str(retrato.get(key_value, getattr(row_value.spare_part,key_value,'') if key_value in ('part_number','description','manufacturer') else '') or '') for key_value in columns]
        writer.writerow(["'" + value_value if value_value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value_value for value_value in values])
    return response_value

# Compatibilidade para importações anteriores; as URLs usam os nomes em português.
login = adapt_call(login_value_value, {'request': 'request_value'})
me = adapt_call(me_value, {'request': 'request_value'})
sectors = adapt_call(sectors_value, {'request': 'request_value'})
lines = adapt_call(lines_value, {'request': 'request_value'})
allocate = adapt_call(allocate_value, {'request': 'request_value'})
remove_equipment = adapt_call(remove_equipment_value, {'request': 'request_value'})
dismantle = adapt_call(dismantle_value, {'request': 'request_value'})
equipment_types = adapt_call(equipment_types_value, {'request': 'request_value'})
equipment = adapt_call(equipment_value_value, {'request': 'request_value'})
movements = adapt_call(movements_value, {'request': 'request_value'})
attachments = adapt_call(attachments_value, {'request': 'request_value'})
users = adapt_call(users_value, {'request': 'request_value'})
problem_types = adapt_call(problem_types_value, {'request': 'request_value'})
line_pendencies = adapt_call(line_pendencies_value, {'request': 'request_value'})
parts = adapt_call(parts_value, {'request': 'request_value'})
managers = adapt_call(managers_value, {'request': 'request_value'})
purchase_parts = adapt_call(purchase_parts_value, {'request': 'request_value'})
technical = adapt_call(technical_value, {'request': 'request_value'})
purchases = adapt_call(purchases_value, {'request': 'request_value'})
save_purchase = adapt_call(save_purchase_value, {'request': 'request_value', 'payload': 'payload_value'})
submit_purchase = adapt_call(submit_purchase_value, {'request': 'request_value'})
decide_purchase = adapt_call(decide_purchase_value, {'request': 'request_value'})
export_purchase = adapt_call(export_purchase_value, {'request': 'request_value'})

# Compatibilidade com integrações que ainda importam os identificadores anteriores.
error = adapt_call(error_value, {'message': 'message_value', 'details': 'detail_value_value', 'status': 'status_value'})
bad_request = adapt_call(bad_request_value, {'request': 'request_value'})
forbidden = adapt_call(forbidden_value, {'request': 'request_value'})
not_found = adapt_call(not_found_value, {'request': 'request_value'})
server_error = adapt_call(server_error_value, {'request': 'request_value'})
issue_token = adapt_call(issue_token_value, {'user': 'user_value'})
bearer_user = adapt_call(bearer_user_value, {'request': 'request_value'})
endpoint = adapt_call(endpoint_value, {'methods': 'methods', 'roles': 'roles_value', 'public': 'public_value'})
require_role = adapt_call(require_role_value, {'request': 'request_value'})
body = adapt_call(body_value, {'request': 'request_value'})
positive_id = adapt_call(positive_id_value, {'value': 'value_value', 'label': 'label_value'})
record = adapt_call(record_value, {'item': 'item_value', 'exclude': 'exclude_value'})
user_data = adapt_call(user_data_value, {'user': 'user_value', 'login': 'login_value'})
camel = adapt_call(camel_value, {'name': 'name_value'})
form_data = adapt_call(form_data_value, {'payload': 'payload_value', 'aliases': 'aliases', 'instance': 'instance_value', 'form_class': 'form_class'})
validated = adapt_call(validated_value, {'form': 'form'})
visible_equipment = adapt_call(visible_equipment_value, {'user': 'user_value'})
equipment_data = adapt_call(equipment_data_value, {'item': 'item_value'})
visible_orders = adapt_call(visible_orders_value, {'user': 'user_value'})
visible_purchases = adapt_call(visible_purchases_value, {'user': 'user_value'})
health = adapt_call(health_value, {'request': 'request_value'})
orders = adapt_call(orders_value_value, {'request': 'request_value'})
line_status = adapt_call(line_status_value, {'request': 'request_value'})
order_data = adapt_call(order_data_value, {'order': 'order_value'})
start_order = adapt_call(start_order_value, {'request': 'request_value'})
order_parts = adapt_call(order_parts_value, {'request': 'request_value'})
order_purchases = adapt_call(order_purchases_value, {'request': 'request_value'})
order_requisitions = adapt_call(order_requisitions_value, {'request': 'request_value'})
pendency_data = adapt_call(pendency_data_value, {'item': 'item_value'})
pending_items = pending_items_value
order_pendencies = adapt_call(order_pendencies_value, {'request': 'request_value'})
part_data = adapt_call(part_data_value, {'part': 'part_value'})
purchase_data = adapt_call(purchase_data_value, {'purchase': 'purchase_value'})
APIError = APIErrorCode
STAFF = STAFFCode
TOKEN_SALT = TOKEN_SALTCode
