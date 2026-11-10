"""Casos de uso de usuarios do Mantis, separados do transporte HTTP."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from .base import Result, operation, request_body
from ..exceptions import ApiError
from .. import forms
from ..filters import UserFilter, apply_filters
from ..models import Line, User
from .common import form_data, user_data, validate_form


@operation(['GET', 'POST', 'PATCH'], roles=('ADMINISTRADOR',))
def users(context, pk=None, action=None):
    """Centraliza cadastro, edição, situação e senha com validação de perfil, linha e proteção da própria conta."""
    if context.method == 'GET':
        return [user_data(user) for user in
                apply_filters(UserFilter, context.filters, User.objects.all())]
    data = request_body(context)
    with transaction.atomic():
        record = get_object_or_404(User.objects.select_for_update(), pk=pk) if pk else User()
        if action == 'status':
            active = data.get('active')
            if not isinstance(active, bool):
                raise ApiError('Situação inválida.')
            if record.pk == context.user.pk and not active:
                raise PermissionDenied
            if active and record.role == 'OPERADOR' and not Line.objects.filter(pk=record.line_id,
                                                                                active=True).exists():
                raise ApiError('Vincule uma linha ativa ao operador antes de reativá-lo.')
            record.active = active
            record.save(update_fields=['active'])
            return {'message': 'Situação atualizada.', 'user': user_data(record)}
        if action == 'password':
            form = validate_form(forms.PasswordForm(data))
            record.set_password(form.cleaned_data['password'])
            record.save(update_fields=['password'])
            return {'message': 'Senha redefinida com sucesso.'}
        mapped = form_data(forms.UserForm, data, instance=record if pk else None,
                           aliases={'lineId': 'line', 'password': 'new_password'})
        record = validate_form(forms.UserForm(mapped, instance=record, actor=context.user)).save()
        return Result(user_data(record), status=200 if pk else 201)


@operation(['GET'])
def managers(context):
    """Lista administradores ativos para o seletor de gestor responsável na solicitação de compra."""
    return list(User.objects.filter(role='ADMINISTRADOR', active=True).values('id', 'name'))
