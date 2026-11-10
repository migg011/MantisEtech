/** Tela de preventivas: liga os campos HTML aos roteiros, alertas e OS da API. O servidor decide permissões, validações e gravações definitivas. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    OnInit,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { forkJoin, finalize, interval } from 'rxjs';
import { Api, Authentication } from '../../services';
import { Equipment } from '../../core/models/equipment.model';
import {
    PREVENTIVE_PERIODICITIES,
    EquipmentPreventive,
    PreventiveExecution,
    PreventiveOrder,
    PreventiveOrderDetails,
} from '../../core/models/preventive.model';
import { FormModal } from '../../shared/form-modal.component';
import { EquipmentSheet } from './equipment-sheet.component';
import { PreventiveCalendar } from './preventive-calendar.component';

@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        RouterLink,
        MatButtonModule,
        MatIconModule,
        FormModal,
        EquipmentSheet,
        PreventiveCalendar,
    ],
    templateUrl: './preventive.component.html',
    styleUrl: './preventive.component.scss',
})
export class Preventive implements OnInit {
    private api = inject(Api);
    private routeSheet = inject(ActivatedRoute);
    private authentication = inject(Authentication);
    private httpClient = inject(HttpClient);
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    // Só uma área ocupa a tela por vez. Usamos [hidden] para preservar os formulários ainda não salvos.
    view = 'EQUIPAMENTOS';
    limitSchedules = 8;
    limitOrders = 8;
    searchOrders = '';
    /** Indicadores são atalhos para a agenda, mantendo o filtro escolhido visível no seletor. */
    showStatusSchedule(status: string) {
        this.filterStatus = status;
        this.limitSchedules = 8;
        this.view = 'AGENDA';
    }
    /** Pesquisa somente as OS já carregadas; mostrar mais não faz uma nova consulta ao banco. */
    get ordersVisible() {
        const term = this.searchOrders.trim().toLocaleLowerCase('pt-BR');
        return this.orders.filter((order) =>
            `${order.number} ${order.equipment_name} ${order.assigned_name}`
                .toLocaleLowerCase('pt-BR')
                .includes(term)
        );
    }
    // Catálogos recebidos da API; os seletores usam essas listas, sem consultar o banco diretamente.
    types: { id: number; name: string }[] = [];
    equipment: Equipment[] = [];
    idType: number | null = null;
    // Estes valores representam a escolha do formulário, ainda sem uma nova OS gravada.
    idMachine: number | null = null;
    private lastMachineSheet: Equipment | undefined;
    // Mantém a ficha montada durante a troca de tipo/frequência para preservar a lista geral de compra.
    get machineSheet() {
        return this.machine || this.lastMachineSheet;
    }
    // As abas apenas alternam a consulta; o roteiro continua no componente que já controla a emissão da OS.
    tabSheet = 'GERAIS';
    tabsSheet = [
        { id: 'GERAIS', label: 'Equipamento' },
        { id: 'TIPOS_OS', label: 'Tipos de OS' },
        { id: 'ROTEIRO', label: 'Checklist / Emitir OS' },
        { id: 'PECAS', label: 'Spare Parts' },
        { id: 'DOCUMENTOS', label: 'Documentação' },
        { id: 'HISTORICO', label: 'Histórico' },
    ];
    // A configuração pertence à máquina e reutiliza as agendas do cadastro, sem um catálogo paralelo.
    selectionTypesWorkOrder: Record<string, boolean> = {};
    datesTypesWorkOrder: Record<string, string> = {};
    typesWorkOrderChanged = false;
    errorTypesWorkOrder = '';
    messageTypesWorkOrder = '';
    private machineConfigurationTypes: number | null = null;
    private alertsTypesWorkOrderLoaded = false;
    administratorPreventive() {
        return this.authentication.user()?.role === 'ADMINISTRADOR';
    }
    selectTabSheet(tab: string) {
        if (this.processing) return;
        if (
            tab === 'ROTEIRO' &&
            this.typesWorkOrderChanged &&
            this.machineConfigurationTypes === this.idMachine
        ) {
            this.tabSheet = 'TIPOS_OS';
            this.errorTypesWorkOrder =
                'Salve ou descarte a configuração antes de preparar a preventiva.';
            return;
        }
        this.tabSheet = tab;
        if (
            tab === 'TIPOS_OS' &&
            (this.machineConfigurationTypes !== this.idMachine ||
                !this.typesWorkOrderChanged)
        )
            this.resetTypesWorkOrder();
    }
    resetTypesWorkOrder(useRegistration = false) {
        this.machineConfigurationTypes = this.idMachine;
        this.selectionTypesWorkOrder = {};
        this.datesTypesWorkOrder = {};
        this.typesWorkOrderChanged = false;
        this.errorTypesWorkOrder = this.messageTypesWorkOrder = '';
        for (const schedule of !useRegistration &&
        this.alertsTypesWorkOrderLoaded
            ? this.schedules.filter((a) => a.equipment_id === this.idMachine)
            : this.machine?.preventive_schedules || []) {
            this.selectionTypesWorkOrder[schedule.frequency] = true;
            this.datesTypesWorkOrder[schedule.frequency] = schedule.next_due;
        }
    }
    changeTypesWorkOrder() {
        this.typesWorkOrderChanged = true;
        this.errorTypesWorkOrder = this.messageTypesWorkOrder = '';
    }
    scheduleTypeWorkOrder(frequency: string) {
        return this.schedules.find(
            (a) =>
                a.equipment_id === this.idMachine && a.frequency === frequency
        );
    }
    typeWorkOrderLocked(frequency: string) {
        const schedule = this.scheduleTypeWorkOrder(frequency);
        return !!schedule && !!this.orderOpen(schedule);
    }
    saveTypesWorkOrder() {
        const machine = this.machine;
        if (
            !machine ||
            !this.administratorPreventive() ||
            this.processing ||
            this.loadingAlerts ||
            this.errorAlerts ||
            !this.typesWorkOrderChanged
        )
            return;
        this.processing = true;
        this.errorTypesWorkOrder = this.messageTypesWorkOrder = '';
        const preventiveSchedules = this.periodicities
            .filter((p) => this.selectionTypesWorkOrder[p.value])
            .map((p) => ({
                frequency: p.value,
                nextDue: this.datesTypesWorkOrder[p.value] || null,
            }));
        // PATCH envia somente as periodicidades; fotos, identificação e históricos permanecem no cadastro.
        this.httpClient
            .patch<Equipment>(`/api/equipment/${machine.id}`, {
                preventiveSchedules,
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (updated) => {
                    this.equipment = this.equipment.map((e) =>
                        e.id === updated.id ? updated : e
                    );
                    this.lastMachineSheet = updated;
                    this.resetTypesWorkOrder(true);
                    this.messageTypesWorkOrder =
                        'Configuração de manutenção salva para este equipamento.';
                    this.loadAlerts();
                },
                error: (failure) => {
                    this.errorTypesWorkOrder =
                        failure.error?.error ||
                        'Não foi possível salvar a configuração de manutenção.';
                },
            });
    }
    prepareTypeWorkOrder(frequency: string) {
        if (
            this.typesWorkOrderChanged ||
            this.processing ||
            this.loading ||
            this.loadingAlerts
        )
            return;
        const schedule = this.scheduleTypeWorkOrder(frequency);
        if (!schedule) {
            this.errorTypesWorkOrder =
                'Atualize o cronograma antes de preparar esta preventiva.';
            return;
        }
        // Se a periodicidade já tem OS aberta, consulta a ordem em vez de gerar outra.
        this.openCompletion(schedule);
    }
    periodicity = 'MENSAL';
    periodicities = PREVENTIVE_PERIODICITIES;
    schedules: EquipmentPreventive[] = [];
    executions: PreventiveExecution[] = [];
    quantityWithoutConfiguration = 0;
    today = '';
    loadingAlerts = false;
    private updateAlertsPending = false;
    errorAlerts = '';
    filterStatus = 'TODAS';
    search = '';
    orders: PreventiveOrder[] = [];
    // A lista contém resumos. O modal busca o detalhe com resultados e revisão atual.
    technicians: { id: number; name: string }[] = [];
    idAssignee: number | null = null;
    datePlanned = '';
    timePlanned = '';
    baseRecurrence = 'PLANEJADA';
    sourceChecklist = 'TIPO';
    orderInEditing: PreventiveOrderDetails | null = null;
    errorOrder = '';
    orderCancel: PreventiveOrder | null = null;
    reasonCancellation = '';
    text = '';
    // savedText identifica um roteiro alterado localmente sem confirmação de gravação na API.
    textSaved = '';
    loading = true;
    processing = false;
    error = '';
    message = '';
    /** A consulta da ficha depende apenas do tipo. Ter uma preventiva configurada é exigido somente para editar o roteiro e emitir a OS. */
    get machinesFiltered() {
        return this.equipment.filter(
            (machine) => machine.equipment_type_id === this.idType
        );
    }
    /** Busca o cadastro independentemente da agenda, permitindo consultar máquinas ainda sem programação. */
    get machine() {
        return this.equipment.find((machine) => machine.id === this.idMachine);
    }
    /** Indica se o recorte de OS carregado contém registros da máquina cuja ficha está aberta. */
    get hasOrdersMachine() {
        return this.orders.some(
            (order) => order.equipment_id === this.idMachine
        );
    }
    /** Converte o texto do roteiro em uma lista: uma atividade por linha, sem linhas vazias nem espaços nas extremidades. */
    get items() {
        return this.text
            .split('\n')
            .map((item) => item.trim())
            .filter(Boolean);
    }
    /** Habilita a emissão somente com máquina, agenda, técnico, data e roteiro salvo, sem outra OS aberta nem operação em andamento. A API repete as validações. */
    get canGenerate() {
        return (
            !!this.machine &&
            !!this.scheduleSelected &&
            !this.orderOpen(this.scheduleSelected) &&
            !!this.idAssignee &&
            !!this.datePlanned &&
            !!this.items.length &&
            this.text === this.textSaved &&
            !this.loading &&
            !this.processing &&
            !(
                this.typesWorkOrderChanged &&
                this.machineConfigurationTypes === this.idMachine
            )
        );
    }
    /** Recebe uma linha da agenda e procura sua OS aberta na lista carregada. Retorna o registro ou undefined, sem alterar a agenda. */
    orderOpen(row: EquipmentPreventive) {
        return this.orders.find(
            (order) => order.schedule_id === row.id && order.status === 'ABERTA'
        );
    }
    /** Indica se o preenchimento local pode ser concluído: data válida, ao menos um realizado e demais itens realizados ou não aplicáveis justificados. O Django valida novamente. */
    get canCompleteOrder() {
        const order = this.orderInEditing;
        return (
            !!order &&
            order.status === 'ABERTA' &&
            !!order.performed_date &&
            order.performed_date <= this.today &&
            order.results.every(
                (result) =>
                    result.status === 'REALIZADO' ||
                    (result.status === 'NA' && !!result.notes.trim())
            ) &&
            order.results.some((result) => result.status === 'REALIZADO')
        );
    }
    /** Relaciona a máquina e a frequência selecionadas à agenda devolvida pelo servidor, incluindo seu vencimento e ID. */
    get scheduleSelected() {
        return this.schedules.find(
            (row) =>
                row.equipment_id === this.idMachine &&
                row.frequency === this.periodicity
        );
    }
    /** Conta as agendas que o servidor classificou como vencidas. O total se refere a periodicidades, não a máquinas distintas. */
    get quantityOverdue() {
        return this.schedules.filter((row) => row.status === 'VENCIDA').length;
    }
    /** Conta as agendas cujo vencimento é hoje, segundo a data local calculada pelo backend. */
    get quantityToday() {
        return this.schedules.filter((row) => row.status === 'HOJE').length;
    }
    /** Conta as agendas com vencimento futuro; não modifica datas nem calcula o prazo de uma execução. */
    get quantityInDay() {
        return this.schedules.filter((row) => row.status === 'EM_DIA').length;
    }
    /** Aplica situação e pesquisa à lista local de agendas. Busca nome, tipo, patrimônio, série, setor e linha sem consultar a API a cada tecla. */
    get schedulesVisible() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.schedules.filter(
            (row) =>
                (this.filterStatus === 'TODAS' ||
                    row.status === this.filterStatus) &&
                `${row.equipment_name} ${row.type_name} ${row.asset_number || ''} ${row.serial || ''} ${row.sector_name || ''} ${row.line_name || ''}`
                    .toLocaleLowerCase('pt-BR')
                    .includes(term)
        );
    }
    /** Traduz um código como BIMESTRAL para o rótulo da tela; mantém o código se não houver uma opção correspondente. */
    labelPeriodicity(value: string) {
        return (
            this.periodicities.find((option) => option.value === value)
                ?.label || value
        );
    }
    /** Transforma o status e os dias restantes enviados pela API em uma mensagem legível de atraso, vencimento hoje ou prazo futuro. */
    labelStatus(row: EquipmentPreventive) {
        return row.status === 'VENCIDA'
            ? `Vencida há ${-row.days_remaining} dia(s)`
            : row.status === 'HOJE'
              ? 'Vence hoje'
              : `Em dia · ${row.days_remaining} dia(s)`;
    }

    /** Ao abrir a tela, carrega agendas, OS, históricos, máquinas, tipos e técnicos. Inicia atualização a cada minuto, encerrada automaticamente quando o componente é destruído. */
    ngOnInit() {
        this.loadAlerts();
        interval(60000)
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => this.loadAlerts());
        forkJoin({
            types: this.api.types(),
            machines: this.api.equipment(),
            technicians: this.httpClient.get<{ id: number; name: string }[]>(
                '/api/preventive-orders/technicians'
            ),
        })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (result) => {
                    this.types = result.types;
                    this.equipment = result.machines;
                    this.technicians = result.technicians;
                    this.idAssignee =
                        result.technicians.find(
                            (user) => user.id === this.authentication.user()?.id
                        )?.id || null;
                    const id = Number(
                        this.routeSheet.snapshot.queryParamMap.get(
                            'equipmentId'
                        )
                    );
                    if (id && this.equipment.some((e) => e.id === id)) {
                        this.idMachine = id;
                        this.selectSheetEquipment();
                        if (
                            this.routeSheet.snapshot.queryParamMap.get(
                                'tab'
                            ) === 'TIPOS_OS'
                        )
                            this.selectTabSheet('TIPOS_OS');
                    }
                },
                error: () =>
                    (this.error =
                        'Não foi possível carregar as máquinas. Recarregue a página para tentar novamente.'),
            });
    }
    /** Consulta agenda, histórico e OS em paralelo. Evita consultas sobrepostas, agenda uma atualização pendente e avisa quando a leitura falha, sem ocultar o possível desatualizado. */
    loadAlerts() {
        if (this.loadingAlerts) {
            this.updateAlertsPending = true;
            return;
        }
        this.loadingAlerts = true;
        forkJoin({
            // Se uma consulta falhar, o aviso identifica que os dados visíveis podem estar antigos.
            schedule: this.httpClient.get<{
                today: string;
                schedules: EquipmentPreventive[];
                unconfigured_count: number;
            }>('/api/preventive-schedules'),
            history: this.httpClient.get<PreventiveExecution[]>(
                '/api/preventive-executions'
            ),
            orders: this.httpClient.get<PreventiveOrder[]>(
                '/api/preventive-orders'
            ),
        })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loadingAlerts = false;
                    this.changeDetector.markForCheck();
                    if (
                        this.updateAlertsPending &&
                        !this.destructionRef.destroyed
                    ) {
                        this.updateAlertsPending = false;
                        this.loadAlerts();
                    }
                })
            )
            .subscribe({
                next: (result) => {
                    this.alertsTypesWorkOrderLoaded = true;
                    this.schedules = result.schedule.schedules;
                    this.today = result.schedule.today;
                    this.quantityWithoutConfiguration =
                        result.schedule.unconfigured_count;
                    this.executions = result.history;
                    this.orders = result.orders;
                    this.errorAlerts = '';
                    if (
                        this.tabSheet === 'TIPOS_OS' &&
                        !this.typesWorkOrderChanged
                    ) {
                        const message = this.messageTypesWorkOrder;
                        this.resetTypesWorkOrder();
                        this.messageTypesWorkOrder = message;
                    }
                },
                error: () =>
                    (this.errorAlerts =
                        'Não foi possível atualizar os alertas. Os dados exibidos podem estar desatualizados.'),
            });
    }
    /** Copia a máquina, o tipo e a frequência de uma linha da agenda para o formulário; carrega seu roteiro e rola até o gerador. */
    useSchedule(row: EquipmentPreventive) {
        if (this.loading || this.processing) return;
        this.view = 'EQUIPAMENTOS';
        this.idType = row.equipment_type_id;
        this.periodicity = row.frequency;
        this.idMachine = row.equipment_id;
        this.tabSheet = 'ROTEIRO';
        this.load();
        this.scrollForSheet();
    }
    /** Abre a identificação da máquina a partir do cronograma, reutilizando a mesma seleção do checklist. */
    showEquipment(row: EquipmentPreventive) {
        this.useSchedule(row);
        this.tabSheet = 'GERAIS';
    }
    /** O seletor no topo abre qualquer equipamento. Quando há agenda, sugere uma frequência já configurada. */
    selectSheetEquipment() {
        this.view = 'EQUIPAMENTOS';
        const machine = this.machine;
        this.tabSheet = 'GERAIS';
        if (!machine) return;
        this.idType = machine.equipment_type_id;
        const schedules = machine.preventive_schedules || [];
        if (
            !schedules.some(
                (schedule) => schedule.frequency === this.periodicity
            ) &&
            schedules.length
        )
            this.periodicity = schedules[0].frequency;
        this.load();
    }
    /** Aguarda o Angular mostrar a seção antes de rolar até a ficha escolhida. */
    scrollForSheet() {
        requestAnimationFrame(() =>
            document
                .getElementById('equipment-sheet')
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        );
    }
    /** Se já existir OS aberta para a agenda, abre seu preenchimento. Caso contrário, seleciona a agenda no formulário para emitir a OS primeiro. */
    openCompletion(row: EquipmentPreventive) {
        const order = this.orderOpen(row);
        if (order) this.openDetailsOrder(order);
        else this.useSchedule(row);
    }
    /** Limpa a máquina escolhida ao trocar o tipo e recarrega o roteiro correspondente, evitando combinar máquina e tipo incompatíveis. */
    changeType() {
        this.idMachine = null;
        this.load();
    }
    /** GET /api/preventive-checklists lê o roteiro do tipo ou da máquina selecionada. Reinicia mensagens e usa o vencimento da agenda como sugestão de data prevista. */
    load() {
        if (
            !this.machinesFiltered.some(
                (machine) => machine.id === this.idMachine
            )
        )
            this.idMachine = null;
        if (this.machine) this.lastMachineSheet = this.machine;
        this.text = this.textSaved = this.error = this.message = '';
        if (!this.idType) return;
        this.datePlanned = this.scheduleSelected?.next_due || this.today;
        // Sem agenda não consultamos o roteiro específico: a API exige uma preventiva ativa para esse endpoint.
        if (
            this.machine &&
            !this.machine.preventive_schedules?.some(
                (schedule) => schedule.frequency === this.periodicity
            )
        )
            return;
        this.loading = true;
        const parameters: Record<string, string | number> = {
            equipmentTypeId: this.idType,
            frequency: this.periodicity,
        };
        // equipmentId escolhe o roteiro específico; sem ele consultamos o padrão do tipo.
        if (this.idMachine) parameters['equipmentId'] = this.idMachine;
        this.httpClient
            .get<{ items: string[]; source: string }>(
                '/api/preventive-checklists',
                { params: parameters }
            )
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => {
                    this.text = this.textSaved = data.items.join('\n');
                    this.sourceChecklist = data.source;
                },
                error: () =>
                    (this.error =
                        'Não foi possível carregar o checklist. Selecione novamente a periodicidade para tentar novamente.'),
            });
    }
    /** PUT /api/preventive-checklists salva o roteiro padrão sem máquina ou um específico com equipmentId. Só atualiza o texto considerado salvo após a confirmação do servidor. */
    save() {
        if (
            !this.idType ||
            this.loading ||
            this.processing ||
            !this.items.length ||
            (this.idMachine && !this.scheduleSelected)
        )
            return;
        this.processing = true;
        this.error = this.message = '';
        this.httpClient
            .put<{ items: string[]; source: string }>(
                '/api/preventive-checklists',
                {
                    equipmentTypeId: this.idType,
                    equipmentId: this.idMachine,
                    frequency: this.periodicity,
                    items: this.items,
                }
            )
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => {
                    this.text = this.textSaved = data.items.join('\n');
                    this.sourceChecklist = data.source;
                    this.message = this.idMachine
                        ? 'Roteiro salvo para este equipamento e periodicidade.'
                        : 'Roteiro padrão salvo para este tipo e periodicidade.';
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível salvar o checklist.'),
            });
    }
    /** POST /api/preventive-orders emite a OS com referência de vencimento, previsão, técnico e regra de renovação. Depois atualiza as listas e inicia o download da ficha salva. */
    generate() {
        if (!this.canGenerate || !this.idType || !this.idMachine) return;
        this.processing = true;
        this.error = this.message = '';
        this.httpClient
            .post<PreventiveOrderDetails>('/api/preventive-orders', {
                scheduleId: this.scheduleSelected!.id,
                expectedDueDate: this.scheduleSelected!.next_due,
                plannedDate: this.datePlanned,
                plannedTime: this.timePlanned || null,
                assignedToId: this.idAssignee,
                recurrenceBasis: this.baseRecurrence,
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (order) => {
                    this.message = `${order.number} emitida. Após realizar a manutenção, abra “Preencher OS” para registrar cada atividade.`;
                    this.loadAlerts();
                    this.downloadOrder(order);
                },
                error: (failure) => {
                    this.error =
                        failure.error?.error || 'Não foi possível emitir a OS.';
                    this.loadAlerts();
                },
            });
    }
    /** Remove a personalização da máquina com useTypeDefault=true e passa a exibir o roteiro padrão do tipo. As OS já emitidas continuam com seus próprios itens. */
    useChecklistDefault() {
        if (!this.idMachine || this.processing) return;
        this.processing = true;
        this.error = '';
        this.httpClient
            .put<{ items: string[]; source: string }>(
                '/api/preventive-checklists',
                {
                    equipmentTypeId: this.idType,
                    equipmentId: this.idMachine,
                    frequency: this.periodicity,
                    useTypeDefault: true,
                }
            )
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => {
                    this.text = this.textSaved = data.items.join('\n');
                    this.sourceChecklist = data.source;
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível usar o roteiro padrão.'),
            });
    }
    /** GET do documento da OS recebe um Blob autenticado, cria um link temporário de download e libera a URL depois. Falha no download não desfaz a OS já salva. */
    downloadOrder(order: PreventiveOrder) {
        this.httpClient
            .get(`/api/preventive-orders/${order.id}/document`, {
                responseType: 'blob',
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => this.changeDetector.markForCheck())
            )
            .subscribe({
                next: (contentFile) => {
                    const address = URL.createObjectURL(contentFile);
                    const link = document.createElement('a');
                    link.href = address;
                    link.download = `${order.number}.html`;
                    link.click();
                    setTimeout(() => URL.revokeObjectURL(address), 60000);
                },
                error: () =>
                    (this.error = `A OS ${order.number} está salva, mas o download falhou. Use “Imprimir” na lista para tentar novamente.`),
            });
    }
    /** GET /api/preventive-orders/:id busca a versão atual da OS para preencher ou consultar. A resposta alimenta o modal e inclui a revisão usada para gravar com segurança. */
    openDetailsOrder(order: PreventiveOrder) {
        if (this.processing) return;
        this.processing = true;
        this.error = this.errorOrder = '';
        this.httpClient
            .get<PreventiveOrderDetails>(`/api/preventive-orders/${order.id}`)
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => (this.orderInEditing = data),
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível carregar a OS.'),
            });
    }
    /** Fecha o modal quando não há gravação em andamento. Valores locais ainda não salvos não são enviados ao servidor. */
    closeOrder() {
        if (!this.processing) this.orderInEditing = null;
    }
    /** Com conclude=false, PATCH salva parcialmente; com true, POST /complete conclui e renova a agenda. Envia revisão, resultados, peças e data/horário, tratando conflitos ou validações. */
    saveOrder(conclude = false) {
        const order = this.orderInEditing;
        if (
            !order ||
            this.processing ||
            order.status !== 'ABERTA' ||
            (conclude && !this.canCompleteOrder)
        )
            return;
        this.processing = true;
        this.errorOrder = '';
        const dataSubmission = {
            revision: order.revision,
            results: order.results,
            performedDate: order.performed_date,
            performedTime: order.performed_time,
            parts: order.parts,
            notes: order.notes,
        };
        // O mesmo formulário pode salvar parcialmente ou concluir com validações adicionais.
        const requestHttp = conclude
            ? this.httpClient.post<PreventiveOrderDetails>(
                  `/api/preventive-orders/${order.id}/complete`,
                  dataSubmission
              )
            : this.httpClient.patch<PreventiveOrderDetails>(
                  `/api/preventive-orders/${order.id}`,
                  dataSubmission
              );
        requestHttp
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => {
                    this.orderInEditing = data;
                    this.message = conclude
                        ? `${data.number} concluída. Agenda atualizada.`
                        : `${data.number}: preenchimento salvo.`;
                    this.loadAlerts();
                },
                error: (failure) =>
                    (this.errorOrder =
                        failure.error?.error ||
                        'Não foi possível salvar a OS.'),
            });
    }
    /** Abre a confirmação de cancelamento para a OS escolhida e limpa a justificativa anterior. Ainda não envia nenhuma alteração. */
    openCancellation(order: PreventiveOrder) {
        if (!this.processing) {
            this.orderCancel = order;
            this.reasonCancellation = this.errorOrder = '';
        }
    }
    /** POST /api/preventive-orders/:id/cancel envia revisão e justificativa. No sucesso fecha o modal e recarrega as listas; a API preserva o vencimento. */
    cancelOrder() {
        if (!this.orderCancel || this.processing) return;
        this.processing = true;
        this.errorOrder = '';
        this.httpClient
            .post(`/api/preventive-orders/${this.orderCancel.id}/cancel`, {
                revision: this.orderCancel.revision,
                reason: this.reasonCancellation,
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: () => {
                    this.orderCancel = null;
                    this.message =
                        'OS cancelada. O vencimento da agenda foi preservado.';
                    this.loadAlerts();
                },
                error: (failure) =>
                    (this.errorOrder =
                        failure.error?.error ||
                        'Não foi possível cancelar a OS.'),
            });
    }
}
