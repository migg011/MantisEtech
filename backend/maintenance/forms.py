"""Server-side data validation. ModelForms are used without rendering HTML or templates."""

import re
from datetime import datetime

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import (Sector, Line, Equipment, User, WorkOrder, ProblemType, SparePart,
                     SparePartTechnical, SparePartCompatibility, PurchaseRequest, PurchaseItem, TECHNICAL_FIELDS)


class SectorForm(forms.ModelForm):
    """Validate JSON sector data, including the minimum name length."""
    class Meta:
        """Define the SectorForm model and the fields included in validation and saving."""
        model = Sector
        fields = ['name', 'description']

    def clean_name(self):
        """Strip spaces and require a sector name with at least two characters."""
        value = self.cleaned_data['name'].strip()
        if len(value) < 2:
            raise ValidationError('Informe pelo menos dois caracteres.')
        return value


class LineForm(forms.ModelForm):
    """Require a line identified by name and linked to an active sector."""
    class Meta:
        """Define the LineForm model and the fields included in validation and saving."""
        model = Line
        fields = ['name', 'sector', 'description']

    def __init__(self, *args, **kwargs):
        """Restrict selection to active sectors and require a sector for the line."""
        super().__init__(*args, **kwargs)
        self.fields['sector'].queryset = Sector.objects.filter(active=True)
        self.fields['sector'].required = True

    def clean_name(self):
        """Strip spaces and require a minimum line name."""
        value = self.cleaned_data['name'].strip()
        if len(value) < 2:
            raise ValidationError('Informe pelo menos dois caracteres.')
        return value


class LineEditForm(LineForm):
    """Allow renaming and describing the line without changing its sector or assembly."""
    class Meta:
        model = Line
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        # Do not use the registration initializer: the sector is not editable here.
        forms.ModelForm.__init__(self, *args, **kwargs)


class EquipmentForm(forms.ModelForm):
    """Validate technical data, non-negative measurements, and partial dates; keep the sector on edits."""
    class Meta:
        """Define the EquipmentForm model and the fields included in validation and saving."""
        model = Equipment
        exclude = ['line', 'position', 'active', 'created_at', 'manufacturing_date']

    def __init__(self, *args, **kwargs):
        """Restrict the sector to active records, prevent sector changes on edit, and add non-negative validation."""
        super().__init__(*args, **kwargs)
        self.fields['sector'].queryset = Sector.objects.filter(active=True)
        self.fields['sector'].required = True
        if self.instance.pk:
            self.fields['sector'].disabled = True
        for name, field in self.fields.items():
            if isinstance(field, forms.DecimalField):
                field.min_value = 0
                field.validators.append(lambda value: self.nonnegative(value))
                field.widget.attrs['min'] = 0

    @staticmethod
    def nonnegative(value):
        """Reject negative measurements or costs while validating numeric fields."""
        if value < 0:
            raise ValidationError('O valor não pode ser negativo.')

    def clean_manufacturing_date_text(self):
        """Validate the partial manufacturing date as year, month/year, or day/month/year."""
        value = self.cleaned_data.get('manufacturing_date_text')
        if not value:
            return None
        if not re.fullmatch(r'\d{4}|\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{4}', value):
            raise ValidationError('Use AAAA, MM/AAAA ou DD/MM/AAAA.')
        try:
            datetime.strptime(value, {0: '%Y', 1: '%m/%Y', 2: '%d/%m/%Y'}[value.count('/')])
        except ValueError:
            raise ValidationError('Data de fabricação inválida.')
        return value


class UserForm(forms.ModelForm):
    """Require an active line for operators, protect the current administrator, and apply password rules."""
    new_password = forms.CharField(label='Senha inicial', widget=forms.PasswordInput, required=False,
                                   help_text='Mínimo de 12 caracteres. Deixe em branco ao editar para manter a senha.')

    class Meta:
        """Define the UserForm model and the fields included in validation and saving."""
        model = User
        fields = ['name', 'registration', 'role', 'line']

    def __init__(self, *args, actor=None, **kwargs):
        """Receive the actor to protect the current account; require a password only for new accounts."""
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields['line'].queryset = Line.objects.filter(active=True)
        self.fields['new_password'].required = not bool(self.instance.pk)

    def clean(self):
        """Validate the operator line, protect the current administrator profile, and check the initial password."""
        data = super().clean()
        if data.get('role') == 'OPERADOR' and not data.get('line'):
            self.add_error('line', 'Operador precisa de uma linha SMT ativa.')
        if data.get('role') != 'OPERADOR':
            data['line'] = None
        if self.actor and self.instance.pk == self.actor.pk and data.get('role') != 'ADMINISTRADOR':
            self.add_error('role', 'Você não pode remover seu próprio perfil de administrador.')
        if data.get('new_password'):
            try:
                validate_password(data['new_password'], self.instance)
            except ValidationError as error:
                self.add_error('new_password', error)
        return data

    def save(self, commit=True):
        """Apply set_password when there is a new password and save the account only when commit is enabled."""
        user = super().save(commit=False)
        if self.cleaned_data.get('new_password'):
            user.set_password(self.cleaned_data['new_password'])
        if commit:
            user.save()
        return user


class PasswordForm(forms.Form):
    """Apply the password policy when a reset arrives through a direct API call."""
    password = forms.CharField(label='Nova senha', widget=forms.PasswordInput)

    def clean_password(self):
        """Apply the project password validators to the new password received by the API."""
        value = self.cleaned_data['password']
        validate_password(value)
        return value


class ProblemTypeForm(forms.ModelForm):
    """Validate the problem selectable by the operator; optionally link it to an equipment type and priority."""
    class Meta:
        """Define the ProblemTypeForm model and the fields included in validation and saving."""
        model = ProblemType
        fields = ['name', 'equipment_type', 'priority', 'active']

    def clean_name(self):
        """Require a clear problem description with at least five characters."""
        value = self.cleaned_data['name'].strip()
        if len(value) < 5:
            raise ValidationError('Informe um problema com pelo menos cinco caracteres.')
        return value


class WorkOrderForm(forms.ModelForm):
    """Accept order creation only for equipment visible to the informed profile."""
    class Meta:
        """Define the WorkOrderForm model and the fields included in validation and saving."""
        model = WorkOrder
        fields = ['equipment', 'priority', 'problem_type', 'occurrence_description']

    def __init__(self, *args, user=None, **kwargs):
        """Restrict machines by the operator line and problems to active options before validating JSON."""
        super().__init__(*args, **kwargs)
        self.user = user
        items = Equipment.objects.filter(active=True)
        if user.role == 'OPERADOR':
            items = items.filter(line_id=user.line_id)
        self.fields['equipment'].queryset = items
        self.fields['problem_type'].queryset = ProblemType.objects.filter(active=True)
        self.fields['problem_type'].required = True
        self.fields['problem_type'].error_messages['required'] = 'Selecione um problema cadastrado.'
        self.fields['priority'].required = False

    def clean(self):
        """Check that the problem applies to the equipment and fix the catalog priority for operators."""
        data = super().clean()
        equipment, problem_type = data.get('equipment'), data.get('problem_type')
        if equipment and problem_type:
            if problem_type.equipment_type_id and problem_type.equipment_type_id != equipment.equipment_type_id:
                self.add_error('problem_type', 'O problema selecionado não se aplica a este tipo de equipamento.')
            if self.user.role == 'OPERADOR' or not data.get('priority'):
                data['priority'] = problem_type.priority
        return data


class WorkOrderUpdateForm(forms.ModelForm):
    """Limit editable service fields to status and technical actions."""
    class Meta:
        """Define the WorkOrderUpdateForm model and the fields included in validation and saving."""
        model = WorkOrder
        fields = ['status', 'root_cause', 'corrective_action', 'preventive_action']


class PlacementForm(forms.Form):
    """Validator for assembly: select free machines from the same sector and a positive position."""
    equipment = forms.ModelChoiceField(label='Equipamento disponível', queryset=Equipment.objects.none())
    position = forms.IntegerField(label='Posição na linha', min_value=1)

    def __init__(self, *args, line, **kwargs):
        """Offer only free, active machines from the same sector as the line."""
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = Equipment.objects.filter(active=True, line=None, sector_id=line.sector_id)


class AttachmentForm(forms.Form):
    """Validate photo/manual size and binary signature without trusting the file extension."""
    kind = forms.ChoiceField(label='Categoria', choices=[('PHOTO', 'Foto PNG/JPG (até 3 MB)'),
                                                        ('MANUAL', 'Manual PDF (até 5 MB)')])
    file = forms.FileField(label='Arquivo')

    def clean(self):
        """Check the real file size and signature; the browser MIME type is not enough."""
        data = super().clean()
        file, kind = data.get('file'), data.get('kind')
        if not file or not kind:
            return data
        limit = (3 if kind == 'PHOTO' else 5) * 1024 * 1024
        if not 0 < file.size <= limit:
            self.add_error('file', 'O arquivo está vazio ou excede o tamanho permitido.')
            return data
        prefix = file.read(8)
        file.seek(0)
        mime = 'image/png' if prefix.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if prefix.startswith(
            b'\xff\xd8\xff') else 'application/pdf' if prefix.startswith(b'%PDF-') else None
        if mime not in (['image/png', 'image/jpeg'] if kind == 'PHOTO' else ['application/pdf']):
            self.add_error('file', 'Conteúdo inválido para a categoria escolhida.')
        data['mime_type'] = mime
        return data


class SparePartForm(forms.ModelForm):
    """Validate stock limits, costs, and compatible equipment for the part."""
    equipment = forms.ModelMultipleChoiceField(label='Equipamentos compatíveis', queryset=Equipment.objects.none(),
                                               required=False)

    class Meta:
        """Define the SparePartForm model and the fields included in validation and saving."""
        model = SparePart
        fields = ['description', 'part_number', 'manufacturer', 'unit', 'minimum_stock', 'maximum_stock',
                  'reorder_point', 'storage_location', 'preferred_supplier', 'average_cost', 'last_cost',
                  'average_cost_currency', 'last_cost_currency']

    def __init__(self, *args, **kwargs):
        """Prepare active machines for compatibility and load existing links on edit."""
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = Equipment.objects.filter(active=True)
        if self.instance.pk:
            self.fields['equipment'].initial = self.instance.compatibility.values_list('equipment_id', flat=True)

    def clean(self):
        """Validate costs and stock references and prevent a maximum below the minimum; do not move balances."""
        data = super().clean()
        for key in ('minimum_stock', 'maximum_stock', 'reorder_point', 'average_cost', 'last_cost'):
            if data.get(key) is not None and data[key] < 0:
                self.add_error(key, 'O valor não pode ser negativo.')
        for cost in ('average_cost', 'last_cost'):
            currency = cost + '_currency'
            # Old values without a currency may stay untouched; a new value requires identification.
            changed = not self.instance.pk or data.get(cost) != getattr(self.instance, cost)
            if data.get(cost) is not None and not data.get(currency) and changed:
                self.add_error(currency, 'Selecione R$ ou US$ para o custo informado.')
        if data.get('maximum_stock') is not None and data.get('minimum_stock') is not None and \
                data['maximum_stock'] < data['minimum_stock']:
            self.add_error('maximum_stock', 'O estoque máximo não pode ser inferior ao mínimo.')
        return data


class TechnicalForm(forms.ModelForm):
    """Accept only sheet fields, without allowing its fiscal approval to be forged."""
    class Meta:
        """Define the TechnicalForm model and the fields included in validation and saving."""
        model = SparePartTechnical
        fields = list(TECHNICAL_FIELDS)


class PurchaseForm(forms.ModelForm):
    """Check the active manager, justification, and order/equipment consistency within the operator line."""
    class Meta:
        """Define the PurchaseForm model and the fields included in validation and saving."""
        model = PurchaseRequest
        fields = ['purchase_type', 'manager', 'work_order', 'equipment', 'justification', 'priority']

    def __init__(self, *args, user=None, **kwargs):
        """Limit managers to active administrators and restrict orders/machines for operator accounts."""
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['manager'].queryset = User.objects.filter(role='ADMINISTRADOR', active=True)
        self.fields['equipment'].queryset = Equipment.objects.filter(active=True)
        if user.role == 'OPERADOR':
            self.fields['equipment'].queryset = self.fields['equipment'].queryset.filter(line_id=user.line_id)
            self.fields['work_order'].queryset = WorkOrder.objects.filter(equipment__line_id=user.line_id)
            self.fields['work_order'].required = True

    def clean(self):
        """Check order/equipment consistency and justification size; derive the machine from the order."""
        data = super().clean()
        order, equipment = data.get('work_order'), data.get('equipment')
        if order and equipment and order.equipment_id != equipment.pk:
            self.add_error('equipment', 'O equipamento não corresponde à OS.')
        elif order:
            data['equipment'] = order.equipment
        if len(data.get('justification', '').strip()) < 10:
            self.add_error('justification', 'Informe pelo menos dez caracteres.')
        return data


class PurchaseItemForm(forms.ModelForm):
    """Validate the active part and quantity of each item before saving the whole request."""
    class Meta:
        """Define the PurchaseItemForm model and the fields included in validation and saving."""
        model = PurchaseItem
        fields = ['spare_part', 'quantity', 'item_note']

    def __init__(self, *args, **kwargs):
        """Restrict each item's part to active records before saving."""
        super().__init__(*args, **kwargs)
        self.fields['spare_part'].queryset = SparePart.objects.filter(active=True)

    def clean_quantity(self):
        """Accept only a positive quantity within the allowed purchase item limit."""
        value = self.cleaned_data['quantity']
        if not 0 < value <= 100000:
            raise ValidationError('A quantidade deve ser maior que zero e até 100.000.')
        return value


class DecisionForm(forms.Form):
    """Restrict the allowed decisions and the manager comment length."""
    decision = forms.ChoiceField(label='Decisão', choices=[('APROVADA', 'Aprovar'), ('REJEITADA', 'Rejeitar'),
                                                            ('DEVOLVIDA', 'Devolver para revisão')])
    comment = forms.CharField(label='Comentário', widget=forms.Textarea, max_length=1500, required=False)
