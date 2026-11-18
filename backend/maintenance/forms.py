"""Validação de dados no servidor. ModelForms são usados sem renderização de HTML ou templates."""

import re
from datetime import datetime
from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import (SectorCode, LineCode, EquipmentCode, UserCode, WorkOrderCode, ProblemTypeCode, SparePartCode,
                     SparePartTechnicalCode, SparePartCompatibilityCode, PurchaseRequestCode, PurchaseItemCode, TECHNICAL_FIELDS)

MANUFACTURING_MONTHS = {
    'JAN': '01', 'FEB': '02', 'FEV': '02', 'MAR': '03',
    'APR': '04', 'ABR': '04', 'MAY': '05', 'MAI': '05',
    'JUN': '06', 'JUL': '07', 'AUG': '08', 'AGO': '08',
    'SEP': '09', 'SEPT': '09', 'SET': '09', 'OCT': '10', 'OUT': '10',
    'NOV': '11', 'DEC': '12', 'DEZ': '12',
}


class SectorFormCode(forms.ModelForm):
    """Valida os dados JSON do setor, incluindo o tamanho mínimo do nome."""
    class Meta:
        """Define o modelo de SectorForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = SectorCode
        fields = ['name', 'description', 'cost_center']
    def clean_name(self):
        """Remove espaços e exige nome de setor com pelo menos dois caracteres."""
        value_value = self.cleaned_data['name'].strip()
        if len(value_value) < 2:
            raise ValidationError('Informe pelo menos dois caracteres.')
        return value_value

class LineFormCode(forms.ModelForm):
    """Exige uma linha identificada por nome e vinculada a um setor ativo."""
    class Meta:
        """Define o modelo de LineForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = LineCode
        fields = ['name', 'sector', 'description']
    def __init__(self, *args, **kwargs):
        """Limita a seleção a setores ativos e exige que a linha tenha setor."""
        super().__init__(*args, **kwargs)
        self.fields['sector'].queryset = SectorCode.objects.filter(active=True)
        self.fields['sector'].required = True
    def clean_name(self):
        """Remove espaços e exige identificação mínima para a linha."""
        value_value = self.cleaned_data['name'].strip()
        if len(value_value) < 2:
            raise ValidationError('Informe pelo menos dois caracteres.')
        return value_value

class LineEditForm(LineFormCode):
    """Permite renomear e descrever a linha sem mudar seu setor ou sua montagem."""
    class Meta:
        model = LineCode
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        # Não usa o inicializador de cadastro, pois o setor não é editável aqui.
        forms.ModelForm.__init__(self, *args, **kwargs)


class EquipmentFormCode(forms.ModelForm):
    """Valida dados técnicos, medidas não negativas e data parcial; mantém o setor em edições."""
    class Meta:
        """Define o modelo de EquipmentForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = EquipmentCode
        exclude = ['line', 'position', 'active', 'created_at', 'manufacturing_date']
    def __init__(self, *args, **kwargs):
        """Restringe setor a ativos, impede troca de setor na edição e adiciona validação de medidas não negativas."""
        super().__init__(*args, **kwargs)
        self.fields['sector'].queryset = SectorCode.objects.filter(active=True)
        self.fields['sector'].required = True
        if self.instance.pk:
            self.fields['sector'].disabled = True
        for name_value, field_value in self.fields.items():
            if isinstance(field_value, forms.DecimalField):
                field_value.min_value = 0
                field_value.validators.append(lambda value_value: self.nonnegative(value_value))
                field_value.widget.attrs['min'] = 0
    @staticmethod
    def nonnegative(value_value):
        """Rejeita medidas ou custos negativos durante a validação de campos numéricos."""
        if value_value < 0:
            raise ValidationError('O valor não pode ser negativo.')
    def clean_pneumatic_pressure_bar(self):
        return self.clean_measurement('pneumatic_pressure_bar', 'bar', '6 ou 4 - 8')

    def clean_frequency_hz(self):
        return self.clean_measurement('frequency_hz', 'Hz', '60, 50/60 ou 50 - 60', allow_alternatives=True)

    def clean_voltage_v(self):
        return self.clean_measurement(
            'voltage_v', 'V', '220, 127/220 ou 220 - 230 Trifásico',
            allow_alternatives=True, phase_pattern=r'(?:mono|bi|tri)f[aá]sic[oa]',
        )

    def clean_measurement(self, field, unit, examples, *, allow_alternatives=False, phase_pattern=None):
        """Valida o valor da placa e inclui a indicação de fase quando aplicável."""
        value = self.cleaned_data[field]
        if not value:
            return None
        number = r'[0-9]+(?:[.,][0-9]+)?'
        separator = '[-–—/]|a' if allow_alternatives else '[-–—]|a'
        phase = rf'(?:\s*({phase_pattern}))?' if phase_pattern else ''
        match = re.fullmatch(
            rf'({number})(?:\s*({separator})\s*({number}))?(?:\s*{unit})?{phase}',
            value, re.IGNORECASE,
        )
        if not match:
            raise ValidationError(f'Informe um valor válido em {unit}. Exemplos: {examples}.')
        first, separator, second = match.group(1, 2, 3)
        normalized = first.replace(',', '.')
        if second is not None:
            second = second.replace(',', '.')
            if separator != '/' and Decimal(normalized) > Decimal(second):
                raise ValidationError('O valor inicial da faixa deve ser menor ou igual ao valor final.')
            normalized += ('/' if separator == '/' else ' - ') + second
        if phase_pattern and match.group(4):
            normalized += ' ' + match.group(4)
        if len(normalized) > self.fields[field].max_length:
            raise ValidationError('A especificação deve ter até 40 caracteres.')
        return normalized

    def clean_manufacturing_date_text(self):
        """Valida a data de fabricação parcial como ano, mês/ano ou dia/mês/ano, sem inventar a precisão ausente."""
        value_value = self.cleaned_data.get('manufacturing_date_text')
        if not value_value:
            return None
        abbreviated = re.fullmatch(r'([A-Za-z]{3,4})\.?(?:\s+|\s*[/\-]\s*)(\d{4})', value_value)
        if abbreviated:
            abbreviation, year = abbreviated.groups()
            month = MANUFACTURING_MONTHS.get(abbreviation.upper())
            if month:
                value_value = f'{month}/{year}'
        if not re.fullmatch(r'\d{4}|\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{4}', value_value):
            raise ValidationError('Data de fabricação: use 2014, 07/2014, JUL 2014 ou 15/07/2014.')
        try:
            datetime.strptime(value_value, {0: '%Y', 1: '%m/%Y', 2: '%d/%m/%Y'}[value_value.count('/')])
        except ValueError:
            raise ValidationError('Data de fabricação inválida.')
        return value_value

class UserFormCode(forms.ModelForm):
    """Protege o perfil do próprio administrador e aplica as regras de senha."""
    new_password = forms.CharField(label='Senha inicial', widget=forms.PasswordInput, required=False, help_text='Mínimo de 12 caracteres. Deixe em branco ao editar para manter a senha.')
    class Meta:
        """Define o modelo de UserForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = UserCode
        fields = ['name', 'registration', 'role', 'sector']
    def __init__(self, *args, actor=None, **kwargs):
        """Recebe o autor para proteger a própria conta; exige senha somente no cadastro de uma conta nova."""
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields['sector'].queryset = SectorCode.objects.filter(active=True)
        self.fields['new_password'].required = not bool(self.instance.pk)
    def clean(self):
        """Protege o perfil do próprio administrador e verifica a senha inicial."""
        data = super().clean()
        if self.actor and self.instance.pk == self.actor.pk and data.get('role') != 'ADMINISTRADOR':
            self.add_error('role', 'Você não pode remover seu próprio perfil de administrador.')
        if data.get('role') in ('OPERADOR', 'TECNICO') and not data.get('sector'):
            self.add_error('sector', 'Selecione o setor do operador ou técnico.')
        if data.get('role') == 'ADMINISTRADOR':
            data['sector'] = None
        if data.get('new_password'):
            try:
                validate_password(data['new_password'], self.instance)
            except ValidationError as error:
                self.add_error('new_password', error)
        return data
    def save(self, commit=True):
        """Aplica set_password quando há nova senha e grava a conta somente se commit estiver habilitado."""
        user_value = super().save(commit=False)
        if self.cleaned_data.get('new_password'):
            user_value.set_password(self.cleaned_data['new_password'])
        if commit:
            user_value.save()
        return user_value

class PasswordFormCode(forms.Form):
    """Aplica a política de senha também quando a redefinição vem de uma chamada direta à API."""
    password = forms.CharField(label='Nova senha', widget=forms.PasswordInput)
    def clean_password(self):
        """Aplica os validadores de senha do projeto à nova senha recebida pela API."""
        value_value = self.cleaned_data['password']
        validate_password(value_value)
        return value_value

class ProblemTypeFormCode(forms.ModelForm):
    """Valida o problema selecionável pelo operador; vincula opcionalmente ao tipo de equipamento e à prioridade."""
    class Meta:
        """Define o modelo de ProblemTypeForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = ProblemTypeCode
        fields = ['name', 'equipment_type', 'priority', 'active']
    def clean_name(self):
        """Exige uma descrição de problema clara, com pelo menos cinco caracteres."""
        value_value = self.cleaned_data['name'].strip()
        if len(value_value) < 5:
            raise ValidationError('Informe um problema com pelo menos cinco caracteres.')
        return value_value


class OrderFormCode(forms.ModelForm):
    """Aceita abertura de OS apenas para equipamentos visíveis ao perfil informado."""
    class Meta:
        """Define o modelo de OrderForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = WorkOrderCode
        fields = ['equipment', 'priority', 'problem_type', 'occurrence_description']
    def __init__(self, *args, user=None, user_value=None, **kwargs):
        """Restringe máquinas pela linha do operador e problemas a opções ativas antes de validar o JSON."""
        super().__init__(*args, **kwargs)
        user_value = user_value or user  # Aceita o argumento anterior durante a tradução dos chamadores.
        self.user = user_value
        items = EquipmentCode.objects.filter(active=True)
        if user_value.role == 'OPERADOR':
            items = items.filter(line_id=user_value.operator_line_id, line__active=True)
        self.fields['equipment'].queryset = items
        self.fields['problem_type'].queryset = ProblemTypeCode.objects.filter(active=True)
        self.fields['problem_type'].required = True
        self.fields['problem_type'].error_messages['required'] = 'Selecione um problema cadastrado.'
        self.fields['priority'].required = False
    def clean(self):
        """Confere se o problema se aplica ao equipamento e fixa a prioridade do catálogo quando o solicitante é operador."""
        data = super().clean()
        equipment_value, problem_type = data.get('equipment'), data.get('problem_type')
        if equipment_value and problem_type:
            if problem_type.equipment_type_id and problem_type.equipment_type_id != equipment_value.equipment_type_id:
                self.add_error('problem_type', 'O problema selecionado não se aplica a este tipo de equipamento.')
            if self.user.role == 'OPERADOR' or not data.get('priority'):
                data['priority'] = problem_type.priority
        return data

class OrderUpdateFormCode(forms.ModelForm):
    """Limita os campos editáveis do atendimento ao estado e às ações técnicas."""
    class Meta:
        """Define o modelo de OrderUpdateForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = WorkOrderCode
        fields = ['status', 'root_cause', 'corrective_action', 'preventive_action']

    def clean(self):
        data = super().clean()
        if data.get('status') == 'CONCLUIDA':
            for field, label in (
                ('root_cause', 'a causa raiz'),
                ('corrective_action', 'a solução corretiva'),
                ('preventive_action', 'a solução preventiva'),
            ):
                if field in data and not (data[field] or '').strip():
                    self.add_error(field, f'Informe {label} para concluir a OS.')
        return data

class PlacementFormCode(forms.Form):
    """Validador disponível para montagem: seleciona máquinas livres do mesmo setor e posição positiva."""
    equipment = forms.ModelChoiceField(label='Equipamento disponível', queryset=EquipmentCode.objects.none())
    position = forms.IntegerField(label='Posição na linha', min_value=1)
    def __init__(self, *args, line, **kwargs):
        """Oferece somente máquinas livres e ativas do mesmo setor da linha."""
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = EquipmentCode.objects.filter(active=True, line=None, sector_id=line.sector_id)

class AttachmentFormCode(forms.Form):
    """Valida tamanho e assinatura binária de foto/manual, sem confiar na extensão do arquivo."""
    kind = forms.ChoiceField(label='Categoria', choices=[('PHOTO', 'Foto PNG/JPG (até 3 MB)'), ('MANUAL', 'Manual PDF (até 25 MB)'), ('ELECTRICAL', 'Esquema elétrico PDF (até 25 MB)')])
    file = forms.FileField(label='Arquivo')
    def clean(self):
        """Confere tamanho e assinatura real do arquivo; o MIME informado pelo navegador não é suficiente."""
        data = super().clean()
        file, kind = data.get('file'), data.get('kind')
        if not file or not kind:
            return data
        limit_mb = 3 if kind == 'PHOTO' else 25
        limit = limit_mb * 1024 * 1024
        if not 0 < file.size <= limit:
            self.add_error('file', f'O arquivo está vazio ou excede o limite de {limit_mb} MB.')
            return data
        prefix = file.read(8)
        file.seek(0)
        mime = 'image/png' if prefix.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if prefix.startswith(b'\xff\xd8\xff') else 'application/pdf' if prefix.startswith(b'%PDF-') else None
        if mime not in (['image/png', 'image/jpeg'] if kind == 'PHOTO' else ['application/pdf']):
            self.add_error('file', 'Conteúdo inválido para a categoria escolhida.')
        data['mime_type'] = mime
        return data

class SparePartFormCode(forms.ModelForm):
    """Valida limites de estoque, custos e equipamentos compatíveis da peça."""
    equipment = forms.ModelMultipleChoiceField(label='Equipamentos compatíveis', queryset=EquipmentCode.objects.none(), required=False)
    class Meta:
        """Define o modelo de SparePartForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = SparePartCode
        fields = ['description', 'part_number', 'manufacturer', 'unit', 'minimum_stock', 'maximum_stock', 'reorder_point', 'storage_location', 'preferred_supplier', 'average_cost', 'last_cost', 'average_cost_currency', 'last_cost_currency']
    def __init__(self, *args, **kwargs):
        """Prepara máquinas ativas para compatibilidade e carrega os vínculos existentes na edição."""
        super().__init__(*args, **kwargs)
        self.fields['equipment'].queryset = EquipmentCode.objects.filter(active=True)
        if self.instance.pk:
            self.fields['equipment'].initial = self.instance.compatibility.values_list('equipment_id', flat=True)
    def clean(self):
        """Valida custos e referências de estoque e impede máximo inferior ao mínimo; não movimenta saldo."""
        data = super().clean()
        for key in ('minimum_stock', 'maximum_stock', 'reorder_point', 'average_cost', 'last_cost'):
            if data.get(key) is not None and data[key] < 0:
                self.add_error(key, 'O valor não pode ser negativo.')
        for custo in ('average_cost', 'last_cost'):
            moeda = custo + '_currency'
            # Valores antigos sem moeda podem continuar intocados; um novo valor exige identificação.
            alterado = not self.instance.pk or data.get(custo) != getattr(self.instance, custo)
            if data.get(custo) is not None and not data.get(moeda) and alterado:
                self.add_error(moeda, 'Selecione R$ ou US$ para o custo informado.')
        if data.get('maximum_stock') is not None and data.get('minimum_stock') is not None and data['maximum_stock'] < data['minimum_stock']:
            self.add_error('maximum_stock', 'O estoque máximo não pode ser inferior ao mínimo.')
        return data

class TechnicalFormCode(forms.ModelForm):
    """Aceita somente os campos de preenchimento da ficha, sem permitir forjar sua aprovação fiscal."""
    class Meta:
        """Define o modelo de TechnicalForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = SparePartTechnicalCode
        fields = list(TECHNICAL_FIELDS)

class PurchaseFormCode(forms.ModelForm):
    """Confere gestor ativo, justificativa e coerência entre OS e equipamento, respeitando a linha do operador."""
    class Meta:
        """Define o modelo de PurchaseForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = PurchaseRequestCode
        fields = ['purchase_type', 'manager', 'work_order', 'equipment', 'justification', 'priority']
    def __init__(self, *args, user=None, user_value=None, **kwargs):
        """Limita gestores a administradores ativos e restringe OS/máquinas quando a conta é operadora."""
        super().__init__(*args, **kwargs)
        user_value = user_value or user
        self.user = user_value
        self.fields['manager'].queryset = UserCode.objects.filter(role='ADMINISTRADOR', active=True)
        self.fields['equipment'].queryset = EquipmentCode.objects.filter(active=True)
        if user_value.role == 'OPERADOR':
            self.fields['equipment'].queryset = self.fields['equipment'].queryset.filter(line_id=user_value.operator_line_id, line__active=True)
            self.fields['work_order'].queryset = WorkOrderCode.objects.filter(equipment__line_id=user_value.operator_line_id, equipment__line__active=True)
            self.fields['work_order'].required = True
    def clean(self):
        """Confere coerência de OS e máquina e tamanho da justificativa; deriva a máquina quando há OS informada."""
        data = super().clean()
        order, equipment_value = data.get('work_order'), data.get('equipment')
        if order and equipment_value and order.equipment_id != equipment_value.pk:
            self.add_error('equipment', 'O equipamento não corresponde à OS.')
        elif order:
            data['equipment'] = order.equipment
        if len(data.get('justification', '').strip()) < 10:
            self.add_error('justification', 'Informe pelo menos dez caracteres.')
        return data

class PurchaseItemFormCode(forms.ModelForm):
    """Valida peça ativa e quantidade de cada item antes de gravar a solicitação inteira."""
    class Meta:
        """Define o modelo de PurchaseItemForm e a lista de campos incluídos ou excluídos da validação e gravação."""
        model = PurchaseItemCode
        fields = ['spare_part', 'quantity', 'item_note']
    def __init__(self, *args, **kwargs):
        """Restringe a peça de cada item a cadastros ativos antes da gravação."""
        super().__init__(*args, **kwargs)
        self.fields['spare_part'].queryset = SparePartCode.objects.filter(active=True)
    def clean_quantity(self):
        """Aceita somente quantidade positiva dentro do limite permitido por item de compra."""
        value_value = self.cleaned_data['quantity']
        if not 0 < value_value <= 100000:
            raise ValidationError('A quantidade deve ser maior que zero e até 100.000.')
        return value_value

class DecisionFormCode(forms.Form):
    """Restringe as decisões permitidas e o tamanho da observação do gestor."""
    decision = forms.ChoiceField(label='Decisão', choices=[('APROVADA', 'Aprovar'), ('REJEITADA', 'Rejeitar'), ('DEVOLVIDA', 'Devolver para revisão')])
    comment = forms.CharField(label='Comentário', widget=forms.Textarea, max_length=1500, required=False)

# Compatibilidade com integrações que ainda importam os nomes anteriores.
SectorForm = SectorFormCode
LineForm = LineFormCode
EquipmentForm = EquipmentFormCode
UserForm = UserFormCode
PasswordForm = PasswordFormCode
ProblemTypeForm = ProblemTypeFormCode
OrderForm = OrderFormCode
OrderUpdateForm = OrderUpdateFormCode
PlacementForm = PlacementFormCode
AttachmentForm = AttachmentFormCode
SparePartForm = SparePartFormCode
TechnicalForm = TechnicalFormCode
PurchaseForm = PurchaseFormCode
PurchaseItemForm = PurchaseItemFormCode
DecisionForm = DecisionFormCode
