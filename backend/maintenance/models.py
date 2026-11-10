"""Persistência PostgreSQL e restrições de integridade; tabelas e colunas físicas em português, com compatibilidade da API e ORM."""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from .portuguese_names import COLUMN_NAMES

# Para aprendizagem: o atributo à esquerda continua sendo usado pelo ORM/API.
# db_column maps the real column: registration -> usuarios.matricula.
# Meta.db_table traduz a tabela. A migração 0012 renomeia sem apagar registros.
# Essa ponte permite traduzir os módulos gradualmente e manter os contratos HTTP.

ROLES = [('ADMINISTRADOR', 'Administrador'), ('TECNICO', 'Técnico'), ('OPERADOR', 'Operador')]
PRIORITIES = [('BAIXA', 'Baixa'), ('MEDIA', 'Média'), ('ALTA', 'Alta'), ('CRITICA', 'Crítica')]
ORDER_STATUSES = [('ABERTA', 'Aberta'), ('EM_ANDAMENTO', 'Em andamento'), ('CONCLUIDA', 'Concluída')]

class Sector(models.Model):
    """Agrupa linhas e equipamentos, preservando o cadastro por desativação lógica."""
    code = models.CharField(max_length=40, unique=True, db_column='codigo')
    name = models.CharField('Nome', max_length=120, db_column='nome')
    description = models.TextField('Descrição', blank=True, null=True, db_column='descricao')
    active = models.BooleanField(default=True, db_column='ativo')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia Sector para a tabela setores; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'setores'
        ordering = ['name']
    def __str__(self):
        """Representação legível de Sector para mensagens e diagnósticos; não grava dados."""
        return self.name

class Line(models.Model):
    """Representa a linha SMT vinculada a um setor; sua composição vem dos equipamentos alocados."""
    code = models.CharField(max_length=40, unique=True, db_column='codigo')
    name = models.CharField('Nome', max_length=120, db_column='nome')
    description = models.TextField('Descrição', blank=True, null=True, db_column='descricao')
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, null=True, related_name='lines', verbose_name='Setor', db_column='setor_id')
    active = models.BooleanField(default=True, db_column='ativo')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia Line para a tabela linhas; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'linhas'
        ordering = ['name']
    def __str__(self):
        """Representação legível de Line para mensagens e diagnósticos; não grava dados."""
        return self.name

class UserManager(BaseUserManager):
    """Cria contas com senha tratada pelos hashers do Django e valida as restrições do modelo."""
    def create_user(self, registration, password=None, **extra):
        """Cria a conta, transforma a senha em hash, valida o modelo e grava pelo gerenciador de usuários."""
        user = self.model(registration=registration, **extra)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user
    def create_superuser(self, registration, password=None, **extra):
        """Define o perfil administrador deste sistema e delega à criação de usuário; não instala o painel admin do Django."""
        extra['role'] = 'ADMINISTRADOR'
        return self.create_user(registration, password, **extra)

class User(AbstractBaseUser):
    """Conta por matrícula, com perfil e linha do operador; usa a tabela usuarios e sua coluna senha_hash."""
    # last_login é o nome esperado pelo Django; db_column traduz somente a coluna.
    last_login = models.DateTimeField('Último acesso', blank=True, null=True, db_column='ultimo_acesso')
    name = models.CharField('Nome', max_length=160, db_column='nome')
    registration = models.CharField('Matrícula', max_length=50, unique=True, db_column='matricula')
    password = models.TextField(db_column='senha_hash')
    role = models.CharField('Perfil', max_length=20, choices=ROLES, db_column='perfil')
    line = models.ForeignKey(Line, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Linha SMT', db_column='linha_id')
    active = models.BooleanField(default=True, db_column='ativo')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    objects = UserManager()
    USERNAME_FIELD = 'registration'
    REQUIRED_FIELDS = ['name']
    class Meta:
        """Mapeia User para a tabela usuarios; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'usuarios'
        ordering = ['name']
        constraints = [models.CheckConstraint(condition=~Q(role='OPERADOR') | Q(line__isnull=False), name='operator_requires_line')]
    @property
    def is_active(self):
        """Expõe o campo active no formato esperado pela autenticação Django."""
        return self.active
    @property
    def is_admin(self):
        """Indicate whether the account has the administrator profile for internal rules."""
        return self.role == 'ADMINISTRADOR'
    @property
    def is_staff_member(self):
        """Identifica os perfis administrador e técnico usados nas operações de manutenção."""
        return self.role in ('ADMINISTRADOR', 'TECNICO')
    def __str__(self):
        """Representação legível de User para mensagens e diagnósticos; não grava dados."""
        return f'{self.name} ({self.registration})'

class EquipmentType(models.Model):
    """Catálogo de tipos de equipamento utilizado pelo cadastro Angular."""
    id = models.SmallIntegerField(primary_key=True, db_column='id')
    name = models.CharField(max_length=100, unique=True, db_column='nome')
    class Meta:
        """Mapeia EquipmentType para a tabela tipos_equipamento; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'tipos_equipamento'
        ordering = ['id']
    def __str__(self):
        """Representação legível de EquipmentType para mensagens e diagnósticos; não grava dados."""
        return self.name

PREVENTIVE_FREQUENCIES = [('QUINZENAL', 'Quinzenal'), ('MENSAL', 'Mensal'), ('BIMESTRAL', 'Bimestral'), ('TRIMESTRAL', 'Trimestral'), ('SEMESTRAL', 'Semestral'), ('ANUAL', 'Anual')]


class PreventiveChecklist(models.Model):
    """Itens aprovados pela equipe para cada tipo de máquina e periodicidade."""
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, db_column='tipo_equipamento_id')
    frequency = models.CharField(max_length=20, choices=PREVENTIVE_FREQUENCIES, db_column='periodicidade')
    items = models.JSONField(default=list, db_column='itens')

    class Meta:
        """Define o nome da tabela e impede cadastrar dois roteiros padrão para a mesma combinação de tipo e frequência."""
        db_table = 'roteiros_preventiva'
        constraints = [models.UniqueConstraint(fields=['equipment_type', 'frequency'], name='unique_preventive_type_frequency')]


class Equipment(models.Model):
    """Cadastro técnico da máquina; o banco impede posição duplicada ou alocação sem posição válida."""
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, verbose_name='Tipo', db_column='tipo_equipamento_id')
    name = models.CharField('Nome do equipamento', max_length=160, blank=True, default='', db_column='nome')
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, null=True, verbose_name='Setor proprietário', db_column='setor_id')
    model_number = models.CharField('Número do modelo', max_length=100, blank=True, null=True, db_column='numero_modelo')
    model = models.CharField('Modelo', max_length=160, blank=True, null=True, db_column='modelo')
    serial = models.CharField('Número de série', max_length=160, unique=True, blank=True, null=True, db_column='numero_serie')
    manufacturer = models.CharField('Fabricante', max_length=160, blank=True, null=True, db_column='fabricante')
    manufacturing_date = models.DateField(blank=True, null=True, db_column='data_fabricacao')
    manufacturing_date_text = models.CharField('Data de fabricação (ano, mês/ano ou dia/mês/ano)', max_length=10, blank=True, null=True, db_column='data_fabricacao_texto')
    length_mm = models.DecimalField('Comprimento (mm)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='comprimento_mm')
    width_mm = models.DecimalField('Largura (mm)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='largura_mm')
    height_mm = models.DecimalField('Altura (mm)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='altura_mm')
    weight_kg = models.DecimalField('Peso (kg)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='peso_kg')
    voltage_v = models.DecimalField('Tensão (V)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='tensao_v')
    frequency_hz = models.DecimalField('Frequência (Hz)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='frequencia_hz')
    current_a = models.DecimalField('Corrente (A)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='corrente_a')
    power_w = models.DecimalField('Potência (W)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='potencia_w')
    pneumatic_pressure_bar = models.DecimalField('Pressão pneumática (bar)', max_digits=12, decimal_places=2, blank=True, null=True, db_column='pressao_pneumatica_bar')
    asset_number = models.CharField('Patrimônio', max_length=100, unique=True, blank=True, null=True, db_column='numero_patrimonio')
    description = models.TextField('Descrição', blank=True, null=True, db_column='descricao')
    process_description = models.TextField('Descrição do processo', blank=True, null=True, db_column='descricao_processo')
    line = models.ForeignKey(Line, on_delete=models.PROTECT, null=True, blank=True, related_name='equipment', db_column='linha_id')
    position = models.IntegerField(null=True, blank=True, db_column='posicao')
    active = models.BooleanField(default=True, db_column='ativo')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia Equipment para a tabela equipamentos; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'equipamentos'
        ordering = ['line_id', 'position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['line', 'position'], name='line_position_unique'),
            models.CheckConstraint(condition=Q(line__isnull=True, position__isnull=True) | Q(line__isnull=False, position__isnull=False, position__gt=0), name='equipment_valid_placement'),
        ]
    def __str__(self):
        """Representação legível de Equipment para mensagens e diagnósticos; não grava dados."""
        return f'{self.asset_number or self.serial or self.pk} — {self.model or self.equipment_type}'

class EquipmentPreventive(models.Model):
    """Agenda independente por equipamento e periodicidade, preservada quando desmarcada."""
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='preventive_schedules', db_column='equipamento_id')
    frequency = models.CharField(max_length=20, choices=PREVENTIVE_FREQUENCIES, db_column='periodicidade')
    next_due = models.DateField(db_index=True, db_column='proximo_vencimento')
    last_performed = models.DateField(null=True, blank=True, db_column='ultima_execucao')
    active = models.BooleanField(default=True, db_column='ativo')
    checklist_items = models.JSONField(null=True, blank=True, db_column='itens_roteiro')
    # None significa herdar o roteiro do tipo; uma lista representa a personalização desta máquina.

    class Meta:
        """Define a tabela da agenda e garante uma única configuração por equipamento e periodicidade, mesmo se estiver desativada."""
        db_table = 'agendas_preventiva'
        constraints = [models.UniqueConstraint(fields=['equipment', 'frequency'], name='unique_equipment_preventive')]


class PreventiveExecution(models.Model):
    """Histórico da execução e do vencimento substituído; imprimir não registra execução."""
    schedule = models.ForeignKey(EquipmentPreventive, on_delete=models.PROTECT, related_name='executions', db_column='agenda_id')
    performed_date = models.DateField(db_column='data_execucao')
    previous_due = models.DateField(db_column='vencimento_anterior')
    next_due = models.DateField(db_column='proximo_vencimento')
    technician = models.ForeignKey(User, on_delete=models.PROTECT, db_column='tecnico_id')
    notes = models.TextField(blank=True, db_column='observacoes')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    order = models.OneToOneField('PreventiveOrder', on_delete=models.PROTECT, null=True, blank=True, related_name='execution', db_column='ordem_preventiva_id')

    class Meta:
        """Define a tabela do histórico e ordena as execuções da mais recente para a mais antiga."""
        db_table = 'execucoes_preventiva'
        ordering = ['-created_at', '-id']


class PreventiveOrder(models.Model):
    """OS preventiva independente da corretiva, com roteiro e identificação congelados na emissão."""
    schedule = models.ForeignKey(EquipmentPreventive, on_delete=models.PROTECT, related_name='orders', db_column='agenda_id')
    status = models.CharField(max_length=20, default='ABERTA', choices=[('ABERTA', 'Aberta'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], db_column='situacao')
    expected_due = models.DateField(db_column='vencimento_previsto')
    planned_date = models.DateField(db_column='data_planejada')
    planned_time = models.TimeField(null=True, blank=True, db_column='hora_planejada')
    recurrence_basis = models.CharField(max_length=20, default='PLANEJADA', choices=[('PLANEJADA', 'Calendário planejado'), ('EXECUCAO', 'Data executada')], db_column='base_recorrencia')
    frequency = models.CharField(max_length=20, choices=PREVENTIVE_FREQUENCIES, db_column='periodicidade')
    equipment_snapshot = models.JSONField(default=dict, db_column='retrato_equipamento')
    # items preserva o texto emitido; results recebe situação e observação de cada posição.
    items = models.JSONField(default=list, db_column='itens')
    results = models.JSONField(default=list, db_column='resultados')
    safety_instructions = models.TextField(db_column='instrucoes_seguranca')
    parts = models.JSONField(default=list, db_column='pecas')
    notes = models.TextField(blank=True, db_column='observacoes')
    performed_date = models.DateField(null=True, blank=True, db_column='data_execucao')
    performed_time = models.TimeField(null=True, blank=True, db_column='hora_execucao')
    assigned_to = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='assigned_preventive_orders', db_column='responsavel_id')
    assigned_name = models.CharField(max_length=160, blank=True, db_column='nome_responsavel')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='issued_preventive_orders', db_column='criado_por_id')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    finished_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='finished_preventive_orders', db_column='concluido_por_id')
    executor_name = models.CharField(max_length=160, blank=True, db_column='nome_executor')
    finished_at = models.DateTimeField(null=True, blank=True, db_column='concluido_em')
    cancellation_reason = models.TextField(blank=True, db_column='motivo_cancelamento')
    revision = models.PositiveIntegerField(default=1, db_column='revisao')
    # A revisão aumenta a cada gravação, para recusar uma tela que abriu dados antigos.

    class Meta:
        """Define a tabela e a ordenação das OS. A restrição no banco impede duas OS abertas para a mesma agenda, inclusive em requisições simultâneas."""
        db_table = 'ordens_preventiva'
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['schedule'], condition=Q(status='ABERTA'), name='one_open_preventive_order')]

    @property
    def number(self):
        """Converte o ID já salvo em uma identificação legível, como PREV-000001. A propriedade não cria uma coluna nem grava outro registro."""
        return f'PREV-{self.pk:06d}'


class ProblemType(models.Model):
    """Catálogo de problemas selecionáveis; a desativação preserva o histórico das OS."""
    name = models.CharField('Problema', max_length=180, db_column='nome')
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='problem_types', verbose_name='Tipo de equipamento', db_column='tipo_equipamento_id')
    priority = models.CharField('Prioridade padrão', max_length=20, choices=PRIORITIES, default='MEDIA', db_column='prioridade')
    active = models.BooleanField(default=True, db_column='ativo')
    class Meta:
        """Mapeia ProblemType para a tabela tipos_problema; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'tipos_problema'
        ordering = ['name']
        constraints = [models.UniqueConstraint(Lower('name'), name='problem_type_name_ci_unique')]
    def __str__(self):
        """Representação legível de ProblemType para mensagens e diagnósticos; não grava dados."""
        return self.name


class WorkOrder(models.Model):
    """Preserva o problema, responsáveis, ações e horários do atendimento de manutenção."""
    # ForeignKey guarda o vínculo no banco; PROTECT impede apagar a máquina e deixar a OS sem origem.
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='orders', verbose_name='Equipamento', db_column='equipamento_id')
    opened_by = models.ForeignKey(User, db_column='aberto_por_id', on_delete=models.PROTECT, related_name='opened_orders')
    assigned_to = models.ForeignKey(User, db_column='responsavel_id', on_delete=models.PROTECT, null=True, related_name='assigned_orders')
    priority = models.CharField('Prioridade', max_length=20, choices=PRIORITIES, default='MEDIA', db_column='prioridade')
    status = models.CharField('Situação', max_length=20, choices=ORDER_STATUSES, default='ABERTA', db_column='situacao')
    problem = models.TextField('Problema relatado', db_column='problema')
    # O problema padronizado e o relato livre são preservados separadamente na OS.
    occurrence_description = models.TextField('Descrição do ocorrido', blank=True, default='', max_length=3000, db_column='descricao_ocorrencia')
    problem_type = models.ForeignKey(ProblemType, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='orders', verbose_name='Problema cadastrado', db_column='tipo_problema_id')
    root_cause = models.TextField('Causa raiz', blank=True, null=True, db_column='causa_raiz')
    corrective_action = models.TextField('Ação corretiva', blank=True, null=True, db_column='acao_corretiva')
    preventive_action = models.TextField('Ação preventiva', blank=True, null=True, db_column='acao_preventiva')
    # created_at é a abertura/parada; started_at é o começo do técnico; finished_at é o encerramento.
    started_at = models.DateTimeField(null=True, db_column='iniciado_em')
    finished_at = models.DateTimeField(null=True, db_column='concluido_em')
    downtime_seconds = models.PositiveIntegerField(null=True, db_column='tempo_parado_segundos')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia WorkOrder para a tabela ordens_servico; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'ordens_servico'
        ordering = ['-created_at']
    def __str__(self):
        """Representação legível de WorkOrder para mensagens e diagnósticos; não grava dados."""
        return f'OS-{self.pk} — {self.equipment}'

class LinePendency(models.Model):
    """Ação pendente originada em uma OS, preservando sua linha e máquina de origem."""
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='pendencies', db_column='ordem_servico_id')
    line = models.ForeignKey(Line, on_delete=models.PROTECT, db_column='linha_id')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipamento_id')
    # Cópia do serial na criação: a manutenção futura do cadastro da máquina não reescreve este histórico.
    equipment_serial = models.CharField(max_length=160, null=True, blank=True, db_column='serie_equipamento')
    description = models.TextField(db_column='descricao')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='MEDIA', db_column='prioridade')
    status = models.CharField(max_length=20, default='PENDENTE', choices=[('PENDENTE', 'Pendente'), ('RESOLVIDA', 'Resolvida')], db_column='situacao')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+', db_column='criado_por_id')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    resolved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='+', db_column='resolvido_por_id')
    resolved_at = models.DateTimeField(null=True, db_column='resolvido_em')
    resolution = models.TextField(blank=True, db_column='resolucao')

    class Meta:
        """Mapeia LinePendency para a tabela pendencias_linha; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'pendencias_linha'
        ordering = ['-created_at']


class EquipmentAttachment(models.Model):
    """Armazena o conteúdo de foto/manual no PostgreSQL, com um arquivo por categoria e máquina."""
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='attachments', db_column='equipamento_id')
    kind = models.CharField(max_length=10, choices=[('PHOTO', 'Foto'), ('MANUAL', 'Manual')], db_column='categoria')
    filename = models.CharField(max_length=180, db_column='nome_arquivo')
    mime_type = models.CharField(max_length=60, db_column='tipo_mime')
    content = models.BinaryField(db_column='conteudo')
    size_bytes = models.IntegerField(db_column='tamanho_bytes')
    uploaded_by = models.ForeignKey(User, db_column='enviado_por_id', on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia EquipmentAttachment para a tabela anexos_equipamento; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'anexos_equipamento'
        constraints = [models.UniqueConstraint(fields=['equipment', 'kind'], name='attachment_equipment_kind')]

class EquipmentMovement(models.Model):
    """Registra a origem, destino, posição e autoria das mudanças de montagem."""
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='movements', db_column='equipamento_id')
    from_line = models.ForeignKey(Line, on_delete=models.PROTECT, null=True, related_name='+', db_column='linha_origem_id')
    from_position = models.IntegerField(null=True, db_column='posicao_origem')
    to_line = models.ForeignKey(Line, on_delete=models.PROTECT, null=True, related_name='+', db_column='linha_destino_id')
    to_position = models.IntegerField(null=True, db_column='posicao_destino')
    action = models.CharField(max_length=20, db_column='acao')
    from_sector = models.ForeignKey(Sector, verbose_name='Setor de origem', on_delete=models.PROTECT, null=True, blank=True, related_name='+', db_column='setor_origem_id')
    to_sector = models.ForeignKey(Sector, verbose_name='Setor de destino', on_delete=models.PROTECT, null=True, blank=True, related_name='+', db_column='setor_destino_id')
    reason = models.CharField('Motivo', max_length=500, blank=True, default='', db_column='motivo')
    performed_by = models.ForeignKey(User, db_column='executado_por_id', on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia EquipmentMovement para a tabela movimentacoes_equipamento; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'movimentacoes_equipamento'
        ordering = ['-created_at']

class MaterialCategory(models.Model):
    """Single catalog: normalize names to avoid duplicate categories."""
    name = models.CharField('Nome', max_length=100, db_column='nome')
    name_key = models.CharField(max_length=64, unique=True, editable=False, db_column='chave_nome')
    description = models.CharField('Descrição', max_length=250, blank=True, default='', db_column='descricao')
    active = models.BooleanField(default=True, db_column='ativo')

    @staticmethod
    def make_key(name):
        import hashlib, unicodedata
        text = unicodedata.normalize('NFKD', ' '.join(name.split()).casefold())
        text = ''.join(character for character in text if not unicodedata.combining(character))
        return hashlib.sha256(text.encode()).hexdigest()

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        self.name_key = self.make_key(self.name)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'categorias_materiais'
        ordering = ['name']

class SparePart(models.Model):
    """Cadastro de peças com saldo controlado por movimentações e referências de custo."""
    code = models.CharField(max_length=40, unique=True, db_column='codigo')
    description = models.CharField('Descrição', max_length=250, db_column='descricao')
    part_number = models.CharField('Part number', max_length=120, blank=True, null=True, db_column='numero_peca')
    manufacturer = models.CharField('Fabricante', max_length=160, blank=True, null=True, db_column='fabricante')
    categories = models.ManyToManyField(MaterialCategory, blank=True, related_name='parts', through='SparePartCategory')
    category = models.CharField('Categoria', max_length=100, blank=True, null=True, db_column='categoria')
    unit = models.CharField('Unidade', max_length=20, default='UN', db_column='unidade')
    # Nulo significa que a contagem inicial ainda não foi informada.
    stock_quantity = models.DecimalField('Saldo disponível', max_digits=14, decimal_places=3, null=True, blank=True, editable=False, db_column='saldo_disponivel')
    minimum_stock = models.DecimalField('Estoque mínimo', max_digits=14, decimal_places=3, default=0, db_column='estoque_minimo')
    maximum_stock = models.DecimalField('Estoque máximo', max_digits=14, decimal_places=3, blank=True, null=True, db_column='estoque_maximo')
    reorder_point = models.DecimalField('Ponto de reposição', max_digits=14, decimal_places=3, default=0, db_column='ponto_reposicao')
    storage_location = models.CharField('Localização', max_length=160, blank=True, null=True, db_column='local_armazenamento')
    preferred_supplier = models.CharField('Fornecedor preferencial', max_length=160, blank=True, null=True, db_column='fornecedor_preferencial')
    average_cost = models.DecimalField('Custo médio', max_digits=14, decimal_places=2, blank=True, null=True, db_column='custo_medio')
    last_cost = models.DecimalField('Último custo', max_digits=14, decimal_places=2, blank=True, null=True, db_column='ultimo_custo')
    # Empty preserves the unknown currency of values registered before this feature.
    average_cost_currency = models.CharField('Moeda do custo médio', max_length=3, choices=[('BRL', 'R$'), ('USD', 'US$'), ('EUR', '€')], blank=True, default='', db_column='moeda_custo_medio')
    last_cost_currency = models.CharField('Moeda do último custo', max_length=3, choices=[('BRL', 'R$'), ('USD', 'US$'), ('EUR', '€')], blank=True, default='', db_column='moeda_ultimo_custo')
    photo_filename = models.CharField(max_length=255, null=True, db_column='nome_arquivo_foto')
    photo_mime = models.CharField(max_length=100, null=True, db_column='tipo_mime_foto')
    photo_data = models.BinaryField(null=True, db_column='conteudo_foto')
    datasheet_filename = models.CharField(max_length=255, null=True, db_column='nome_arquivo_ficha')
    datasheet_data = models.BinaryField(null=True, db_column='conteudo_ficha')
    active = models.BooleanField(default=True, db_column='ativo')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    updated_at = models.DateTimeField(default=timezone.now, db_column='atualizado_em')
    class Meta:
        """Mapeia SparePart para a tabela pecas_reposicao; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'pecas_reposicao'
        ordering = ['description']
        constraints = [models.CheckConstraint(condition=models.Q(stock_quantity__gte=0) | models.Q(stock_quantity__isnull=True), name='peca_saldo_nao_negativo')]
    def __str__(self):
        """Representação legível de SparePart para mensagens e diagnósticos; não grava dados."""
        return f'{self.part_number or self.code} — {self.description}'

class StockMovement(models.Model):
    """Movement history. The balance changes only together with this record in the same transaction."""
    spare_part = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='stock_movements', db_column='peca_id')
    kind = models.CharField(max_length=12, choices=[('INICIAL','Saldo inicial'),('ENTRADA','Entrada'),('SAIDA','Saída'),('AJUSTE','Contagem de ajuste')], db_column='tipo')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, db_column='quantidade_informada')
    previous_quantity = models.DecimalField(max_digits=14, decimal_places=3, null=True, db_column='saldo_anterior')
    delta = models.DecimalField(max_digits=14, decimal_places=3, db_column='variacao')
    resulting_quantity = models.DecimalField(max_digits=14, decimal_places=3, db_column='saldo_resultante')
    performed_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column='responsavel_id')
    note = models.CharField(max_length=500, db_column='justificativa')
    # Datas antigas ficam nulas: não inventamos uma data de recebimento para lançamentos anteriores.
    movement_date = models.DateField(null=True, blank=True, db_column='data_movimentacao')
    supplier = models.CharField(max_length=160, blank=True, default='', db_column='fornecedor_entrada')
    document_reference = models.CharField(max_length=100, blank=True, default='', db_column='documento_entrada')
    request_key = models.UUIDField(unique=True, db_column='chave_requisicao')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')

    class Meta:
        db_table = 'movimentacoes_estoque_pecas'
        ordering = ['-created_at','-pk']
        constraints = [models.CheckConstraint(condition=models.Q(resulting_quantity__gte=0), name='movimento_saldo_nao_negativo')]


class SparePartCompatibility(models.Model):
    """Relaciona peças aos equipamentos compatíveis, impedindo pares duplicados pela chave composta."""
    pk = models.CompositePrimaryKey('spare_part_id', 'equipment_id')
    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE, related_name='compatibility', db_column='peca_id')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipamento_id')
    class Meta:
        """Mapeia SparePartCompatibility para a tabela compatibilidade_pecas_equipamentos; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'compatibilidade_pecas_equipamentos'

TECHNICAL_FIELDS = {
    'description_en': 'Descrição em inglês', 'ncm': 'NCM', 'pli_description': 'Descrição para PLI',
    'description_pt': 'Descrição detalhada em português', 'classification': 'Classificação do material',
    'independent_function': 'Tem função própria? Funciona sozinho?', 'connection_details': 'Dispositivos e conexões',
    'useful_life': 'Vida útil', 'asset_classification': 'Ativo fixo ou uso e consumo',
    'main_function': 'Função principal', 'secondary_function': 'Função secundária', 'raw_material': 'Matéria-prima',
    'intended_use': 'Utilização / linha de produção', 'application_machine': 'Máquina de aplicação e série',
    'mechanical_electrical': 'Mecânico ou elétrico', 'current_type': 'Tipo de corrente', 'power': 'Potência',
    'voltage': 'Tensão', 'amperage': 'Amperagem', 'picture_reference': 'Referência da imagem',
}

class SparePartTechnical(models.Model):
    """Ficha reutilizável da peça e registro de sua validação fiscal interna."""
    spare_part = models.OneToOneField(SparePart, primary_key=True, on_delete=models.PROTECT, related_name='technical', db_column='peca_id')
    fiscal_status = models.CharField(max_length=20, default='PENDENTE', db_column='situacao_fiscal')
    fiscal_validated_by = models.ForeignKey(User, db_column='validado_por_id', on_delete=models.PROTECT, null=True)
    fiscal_validated_at = models.DateTimeField(null=True, db_column='validado_em')
    updated_at = models.DateTimeField(default=timezone.now, db_column='atualizado_em')
    class Meta:
        """Mapeia SparePartTechnical para a tabela fichas_tecnicas_pecas; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'fichas_tecnicas_pecas'

# Gera os campos repetidos da ficha a partir de um único catálogo de nomes e rótulos.
for _name, _label in TECHNICAL_FIELDS.items():
    SparePartTechnical.add_to_class(_name, models.CharField(_label, max_length=10, blank=True, null=True, db_column=COLUMN_NAMES[_name]) if _name == 'ncm' else models.TextField(_label, blank=True, null=True, db_column=COLUMN_NAMES[_name]))

class PartRequisition(models.Model):
    """Solicitação direta de peça para manutenção, independente do processo de compra."""
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, related_name='part_requisitions', db_column='ordem_servico_id')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipamento_id')
    equipment_serial = models.CharField(max_length=160, blank=True, null=True, db_column='serie_equipamento')
    spare_part = models.ForeignKey(SparePart, on_delete=models.PROTECT, db_column='peca_id')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, db_column='quantidade')
    requester = models.ForeignKey(User, on_delete=models.PROTECT, db_column='solicitante_id')
    note = models.TextField(blank=True, db_column='observacao')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')

    class Meta:
        """Mapeia PartRequisition para a tabela solicitacoes_pecas_manutencao; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'solicitacoes_pecas_manutencao'
        ordering = ['-created_at']


class PurchaseRequest(models.Model):
    """Cabeçalho da compra com solicitante, gestor designado, justificativa e estado de aprovação."""
    purchase_type = models.CharField('Tipo de compra', max_length=16, choices=[('NACIONAL', 'Nacional'), ('IMPORTACAO', 'Importação')], db_column='tipo_compra')
    status = models.CharField(max_length=24, default='RASCUNHO', db_column='situacao')
    requester = models.ForeignKey(User, on_delete=models.PROTECT, related_name='purchases', db_column='solicitante_id')
    manager = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approvals', verbose_name='Gestor responsável', db_column='gestor_id')
    work_order = models.ForeignKey(WorkOrder, on_delete=models.PROTECT, blank=True, null=True, verbose_name='Ordem de serviço', db_column='ordem_servico_id')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, blank=True, null=True, verbose_name='Equipamento', db_column='equipamento_id')
    equipment_serial = models.CharField('Serial da máquina na solicitação', max_length=160, blank=True, null=True, db_column='serie_equipamento')
    justification = models.TextField('Justificativa', db_column='justificativa')
    priority = models.CharField('Prioridade', max_length=12, choices=PRIORITIES, db_column='prioridade')
    manager_comment = models.TextField(null=True, db_column='parecer_gestor')
    submitted_at = models.DateTimeField(null=True, db_column='enviado_em')
    decided_at = models.DateTimeField(null=True, db_column='decidido_em')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    updated_at = models.DateTimeField(default=timezone.now, db_column='atualizado_em')
    class Meta:
        """Mapeia PurchaseRequest para a tabela solicitacoes_compra; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'solicitacoes_compra'
        ordering = ['-created_at']

class PurchaseItem(models.Model):
    """Relaciona a peça e a quantidade à compra e mantém os dados técnicos congelados no envio."""
    request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name='items', db_column='solicitacao_id')
    spare_part = models.ForeignKey(SparePart, on_delete=models.PROTECT, verbose_name='Peça', db_column='peca_id')
    quantity = models.DecimalField('Quantidade', max_digits=14, decimal_places=3, db_column='quantidade')
    item_note = models.TextField('Observação', blank=True, null=True, db_column='observacao_item')
    technical_snapshot = models.JSONField(null=True, db_column='retrato_ficha_tecnica')
    class Meta:
        """Mapeia PurchaseItem para a tabela itens_solicitacao_compra; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'itens_solicitacao_compra'

class PurchaseEvent(models.Model):
    """Histórico de autoria e ações da solicitação, separado do seu estado atual."""
    request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name='events', db_column='solicitacao_id')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, db_column='autor_id')
    action = models.CharField(max_length=32, db_column='acao')
    details = models.TextField(null=True, db_column='detalhes')
    created_at = models.DateTimeField(default=timezone.now, db_column='criado_em')
    class Meta:
        """Mapeia PurchaseEvent para a tabela eventos_solicitacao_compra; as configurações abaixo definem ordenação e/ou integridade quando declaradas."""
        db_table = 'eventos_solicitacao_compra'
        ordering = ['created_at']

# Domain catalog names are already exported directly by the class definitions above.


class SparePartCategory(models.Model):
    """Vínculo explícito para preservar as colunas da tabela de categorias existente."""

    spare_part = models.ForeignKey(SparePart, on_delete=models.CASCADE, db_column='sparepart_id')
    category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, db_column='categoriamaterial_id')

    class Meta:
        db_table = 'categorias_pecas'
        unique_together = [('spare_part', 'category')]
