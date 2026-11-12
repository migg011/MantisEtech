"""Painel administrativo: contas editáveis e consulta dos registros operacionais."""
from django.apps import apps
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db import models

from .models import Line, User


class AccountRulesMixin:
    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields['line'].queryset = Line.objects.filter(active=True)

    def clean(self):
        data = super().clean()
        if data.get('role') == 'OPERADOR' and not data.get('line'):
            self.add_error('line', 'Operador precisa de uma linha SMT ativa.')
        if data.get('role') != 'OPERADOR':
            data['line'] = None
        if self.actor and self.instance.pk == self.actor.pk:
            if data.get('role') != 'ADMINISTRADOR':
                self.add_error('role', 'Você não pode remover seu próprio perfil de administrador.')
            if not data.get('active'):
                self.add_error('active', 'Você não pode desativar sua própria conta.')
        return data


class AccountCreationForm(AccountRulesMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('registration', 'name', 'role', 'line', 'active')


class AccountChangeForm(AccountRulesMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('registration', 'name', 'password', 'role', 'line', 'active')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    list_display = ('registration', 'name', 'role', 'active', 'line')
    list_filter = ('role', 'active')
    search_fields = ('registration', 'name')
    ordering = ('name',)
    filter_horizontal = ()
    readonly_fields = ('last_login', 'created_at')
    fieldsets = (
        (None, {'fields': ('registration', 'password')}),
        ('Conta', {'fields': ('name', 'role', 'line', 'active')}),
        ('Datas', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = ((None, {'fields': (
        'registration', 'name', 'role', 'line', 'active', 'password1', 'password2',
    )}),)

    def has_delete_permission(self, request, obj=None):
        return False  # Contas são desativadas para preservar o histórico.

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class RequestAccountForm(base_form):
            def __init__(self, *args, **form_kwargs):
                form_kwargs['actor'] = request.user
                super().__init__(*args, **form_kwargs)

        return RequestAccountForm


class OperationalAdmin(admin.ModelAdmin):
    """Evita alterações diretas que ignorariam os serviços de negócio."""
    actions = None
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in apps.get_app_config('maintenance').get_models():
    # O Admin não suporta modelos com chave primária composta.
    if model is not User and not isinstance(model._meta.pk, models.CompositePrimaryKey):
        admin.site.register(model, OperationalAdmin)

admin.site.site_header = 'Administração Mantis'
admin.site.site_title = 'Mantis'
admin.site.index_title = 'Cadastros e registros'
