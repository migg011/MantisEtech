/** Tela de preventivas: liga os campos HTML aos roteiros, alertas e OS da API. O servidor decide permissões, validações e gravações definitivas. */
import { EquipmentDocuments } from '../../shared/equipment-documents.component';
import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { forkJoin, finalize, interval } from 'rxjs';
import { Api, Auth } from '../../services';
import { Equipment } from '../../core/models/equipment.model';
import { PREVENTIVE_FREQUENCIES, PreventiveSchedule, PreventiveExecution, PreventiveOrder, PreventiveOrderDetail } from '../../core/models/preventive.model';
import { FormModal } from '../../shared/form-modal.component';
import { EquipmentSheet } from './equipment-sheet.component';
import { PreventiveCalendar } from './preventive-calendar.component';

@Component({
    standalone: true,
    imports: [EquipmentDocuments, CommonModule, FormsModule, RouterLink, MatButtonModule, MatIconModule, FormModal, EquipmentSheet, PreventiveCalendar],
    templateUrl: './preventive-checklists.component.html',
    styleUrl: './preventive-checklists.component.scss'
})
export class PreventiveChecklists implements OnInit {
    private api = inject(Api);
    private sheetRoute = inject(ActivatedRoute);

    get repositorySectorId(): number | null {
        const id = Number(this.sheetRoute.snapshot.queryParamMap.get('repositorySectorId'));
        return Number.isSafeInteger(id) && id > 0 ? id : null;
    }
    private authValue = inject(Auth);
    private httpValue = inject(HttpClient);
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    // Só uma área ocupa a tela por vez. Usamos [hidden] para preservar os formulários ainda não salvos.
    view = 'EQUIPAMENTOS';
    scheduleLimit = 8;
    limiteOrdens = 8;
    orderSearch = '';
    /** Indicadores são atalhos para a agenda, mantendo o filtro escolhido visível no seletor. */
    mostrarSituacaoAgenda(statusValue:string) { this.statusFilter = statusValue; this.scheduleLimit = 8; this.view = 'AGENDA'; }
    /** Pesquisa somente as OS já carregadas; mostrar mais não faz uma nova consulta ao banco. */
    get visibleOrders() {
        const term = this.orderSearch.trim().toLocaleLowerCase('pt-BR');
        return this.ordersValue.filter(orderValue => `${orderValue.number} ${orderValue.equipment_name} ${orderValue.assigned_name}`.toLocaleLowerCase('pt-BR').includes(term));
    }
    // Catálogos recebidos da API; os seletores usam essas listas, sem consultar o banco diretamente.
    typesValue: {id: number; name: string}[] = [];
    machinesValue: Equipment[] = [];
    typeId: number | null = null;
    // Estes valores representam a escolha do formulário, ainda sem uma nova OS gravada.
    machineId: number | null = null;
    private lastSheetMachine: Equipment | undefined;
    // Mantém a ficha montada durante a troca de tipo/frequência para preservar a lista geral de compra.
    get sheetMachine() { return this.machineValue || this.lastSheetMachine; }
    // As abas apenas alternam a consulta; o roteiro continua no componente que já controla a emissão da OS.
    sheetTab = 'GERAIS';
    sheetTabs = [{id:'GERAIS',label:'Equipamento'}, {id:'TIPOS_OS',label:'Tipos de OS'}, {id:'ROTEIRO',label:'Checklist / Emitir OS'}, {id:'PECAS',label:'Spare Parts'}, {id:'DOCUMENTOS',label:'Documentação'}, {id:'HISTORICO',label:'Histórico'}];
    // A configuração pertence à máquina e reutiliza as agendas do cadastro, sem um catálogo paralelo.
    orderTypeSelection:Record<string,boolean>={};
    orderTypeDates:Record<string,string>={};
    orderTypesChanged=false;
    orderTypesError='';
    orderTypesMessage='';
    private orderTypeMachine:number|null=null;
    private orderTypeAlertsLoaded=false;
    managePreventiveWork(){return this.authValue.userValue()?.role==='ADMINISTRADOR';}
    selectSheetTab(tab:string){
        if(this.working)return;
        if(tab==='ROTEIRO' && this.orderTypesChanged && this.orderTypeMachine===this.machineId){this.sheetTab='TIPOS_OS';this.orderTypesError='Salve ou descarte a configuração antes de preparar a preventiva.';return;}
        this.sheetTab=tab;
        if(tab==='TIPOS_OS' && (this.orderTypeMachine!==this.machineId || !this.orderTypesChanged))this.resetOrderTypes();
    }
    resetOrderTypes(useRegistration=false){
        this.orderTypeMachine=this.machineId;
        this.orderTypeSelection={};this.orderTypeDates={};this.orderTypesChanged=false;this.orderTypesError=this.orderTypesMessage='';
        for(const scheduleValue of (!useRegistration && this.orderTypeAlertsLoaded ? this.schedulesValue.filter(a=>a.equipment_id===this.machineId) : this.machineValue?.preventive_schedules||[])){this.orderTypeSelection[scheduleValue.frequency]=true;this.orderTypeDates[scheduleValue.frequency]=scheduleValue.next_due;}
    }
    changeOrderTypes(){this.orderTypesChanged=true;this.orderTypesError=this.orderTypesMessage='';}
    orderTypeSchedule(frequencia:string){return this.schedulesValue.find(a=>a.equipment_id===this.machineId && a.frequency===frequencia);}
    tipoOsBloqueado(frequencia:string){const scheduleValue=this.orderTypeSchedule(frequencia);return !!scheduleValue && !!this.openedOrder(scheduleValue);}
    saveOrderTypes(){
        const machineValue=this.machineValue;
        if(!machineValue || !this.managePreventiveWork() || this.working || this.loadingAlerts || this.alertsError || !this.orderTypesChanged)return;
        this.working=true;this.orderTypesError=this.orderTypesMessage='';
        const preventiveSchedules=this.frequencies.filter(p=>this.orderTypeSelection[p.value]).map(p=>({frequency:p.value,nextDue:this.orderTypeDates[p.value]||null}));
        // PATCH envia somente as periodicidades; fotos, identificação e históricos permanecem no cadastro.
        this.httpValue.patch<Equipment>(`/api/equipment/${machineValue.id}`,{preventiveSchedules}).pipe(takeUntilDestroyed(this.destroyRef),finalize(()=>{this.working=false;this.cdr.markForCheck();})).subscribe({
            next:atualizado=>{this.machinesValue=this.machinesValue.map(e=>e.id===atualizado.id?atualizado:e);this.lastSheetMachine=atualizado;this.resetOrderTypes(true);this.orderTypesMessage='Configuração de manutenção salva para este equipamento.';this.loadAlerts();},
            error:failure=>{this.orderTypesError=failure.error?.error||'Não foi possível salvar a configuração de manutenção.';}
        });
    }
    prepararTipoOs(frequencia:string){
        if(this.orderTypesChanged || this.working || this.loading || this.loadingAlerts)return;
        const scheduleValue=this.orderTypeSchedule(frequencia);
        if(!scheduleValue){this.orderTypesError='Atualize o cronograma antes de preparar esta preventiva.';return;}
        // Se a periodicidade já tem OS aberta, consulta a ordem em vez de gerar outra.
        this.openCompletion(scheduleValue);
    }
    frequencyValue = 'MENSAL';
    frequencies = PREVENTIVE_FREQUENCIES;
    schedulesValue: PreventiveSchedule[] = [];
    executions: PreventiveExecution[] = [];
    unconfiguredCount = 0;
    today = '';
    loadingAlerts = false;
    private pendingAlertRefresh = false;
    alertsError = '';
    statusFilter = 'TODAS';
    search = '';
    ordersValue: PreventiveOrder[] = [];
    // A lista contém resumos. O modal busca o detalhe com resultados e revisão atual.
    technicians: {id: number; name: string; role: string; sector_id: number | null}[] = [];
    get eligibleTechnicians() {
        const sectorId = this.machineValue?.sector_id;
        return this.technicians.filter(user => user.role === 'ADMINISTRADOR' || (sectorId != null && user.sector_id === sectorId));
    }
    assigneeId: number | null = null;
    plannedDate = '';
    plannedTime = '';
    shifts: {time: string; label: string; available: boolean}[] = [];
    loadingShifts = false;
    shiftError = '';
    private shiftLookup = 0;
    recurrenceBase = 'PLANEJADA';
    scheduleSource = 'TIPO';
    editingOrder: PreventiveOrderDetail | null = null;
    orderError = '';
    orderToCancel: PreventiveOrder | null = null;
    cancellationReason = '';
    text = '';
    // savedText identifica um roteiro alterado localmente sem confirmação de gravação na API.
    savedText = '';
    loading = true;
    working = false;
    errorValue = '';
    messageValue = '';
    /** A consulta da ficha depende apenas do tipo. Ter uma preventiva configurada é exigido somente para editar o roteiro e emitir a OS. */
    get filteredMachines() { return this.machinesValue.filter(machineValue => machineValue.equipment_type_id === this.typeId); }
    /** Busca o cadastro independentemente da agenda, permitindo consultar máquinas ainda sem programação. */
    get machineValue() { return this.machinesValue.find(machineValue => machineValue.id === this.machineId); }
    /** Indica se o recorte de OS carregado contém registros da máquina cuja ficha está aberta. */
    /** Converte o texto do roteiro em uma lista: uma atividade por linha, sem linhas vazias nem espaços nas extremidades. */
    get items() { return this.text.split('\n').map(item => item.trim()).filter(Boolean); }
    /** Habilita a emissão somente com máquina, agenda, técnico, data e roteiro salvo, sem outra OS aberta nem operação em andamento. A API repete as validações. */
    get canGenerate() { return !!this.machineValue && !!this.selectedSchedule && !this.openedOrder(this.selectedSchedule) && this.eligibleTechnicians.some(user => user.id === this.assigneeId) && !!this.plannedDate && this.shifts.some(shift => shift.time === this.plannedTime && shift.available) && !this.loadingShifts && !!this.items.length && this.text === this.savedText && !this.loading && !this.working && !(this.orderTypesChanged && this.orderTypeMachine===this.machineId); }
    /** Recebe uma linha da agenda e procura sua OS aberta na lista carregada. Retorna o registro ou undefined, sem alterar a agenda. */
    openedOrder(row: PreventiveSchedule) { return this.ordersValue.find(orderValue => orderValue.schedule_id === row.id && orderValue.status === 'ABERTA'); }
    /** Indica se o preenchimento local pode ser concluído: data válida, ao menos um realizado e demais itens realizados ou não aplicáveis justificados. O Django valida novamente. */
    get canCompleteOrder() {
        const orderValue = this.editingOrder;
        return !!orderValue && orderValue.status === 'ABERTA' && !!orderValue.performed_date && orderValue.performed_date <= this.today &&
            orderValue.results.every(resultValue => resultValue.status === 'REALIZADO' || (resultValue.status === 'NA' && !!resultValue.notes.trim())) &&
            orderValue.results.some(resultValue => resultValue.status === 'REALIZADO');
    }
    /** Relaciona a máquina e a frequência selecionadas à agenda devolvida pelo servidor, incluindo seu vencimento e ID. */
    get selectedSchedule() { return this.schedulesValue.find(row => row.equipment_id === this.machineId && row.frequency === this.frequencyValue); }
    /** Conta as agendas que o servidor classificou como vencidas. O total se refere a periodicidades, não a máquinas distintas. */
    get overdueCount() { return this.schedulesValue.filter(row => row.status === 'VENCIDA').length; }
    /** Conta as agendas cujo vencimento é hoje, segundo a data local calculada pelo backend. */
    get dueTodayCount() { return this.schedulesValue.filter(row => row.status === 'HOJE').length; }
    /** Conta as agendas com vencimento futuro; não modifica datas nem calcula o prazo de uma execução. */
    get onTrackCount() { return this.schedulesValue.filter(row => row.status === 'EM_DIA').length; }
    /** Aplica situação e pesquisa à lista local de agendas. Busca nome, tipo, patrimônio, série, setor e linha sem consultar a API a cada tecla. */
    get visibleSchedules() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.schedulesValue.filter(row => (this.statusFilter === 'TODAS' || row.status === this.statusFilter) &&
            `${row.equipment_name} ${row.type_name} ${row.asset_number || ''} ${row.serial || ''} ${row.sector_name || ''} ${row.line_name || ''}`.toLocaleLowerCase('pt-BR').includes(term));
    }
    /** Traduz um código como BIMESTRAL para o rótulo da tela; mantém o código se não houver uma opção correspondente. */
    rotuloPeriodicidade(valueValue: string) { return this.frequencies.find(option => option.value === valueValue)?.label || valueValue; }
    /** Transforma o status e os dias restantes enviados pela API em uma mensagem legível de atraso, vencimento hoje ou prazo futuro. */
    statusLabel(row: PreventiveSchedule) {
        return row.status === 'VENCIDA' ? `Vencida há ${-row.days_remaining} dia(s)` : row.status === 'HOJE' ? 'Vence hoje' : `Em dia · ${row.days_remaining} dia(s)`;
    }

    /** Ao abrir a tela, carrega agendas, OS, históricos, máquinas, tipos e técnicos. Inicia atualização a cada minuto, encerrada automaticamente quando o componente é destruído. */
    ngOnInit() {
        this.loadAlerts();
        interval(60000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.loadAlerts());
        forkJoin({types:this.api.typesValue(), machines:this.api.machinesValue(), technicians:this.httpValue.get<typeof this.technicians>('/api/preventive-orders/technicians')}).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => { this.loading = false; this.cdr.markForCheck(); })).subscribe({
            next: resultValue => { this.typesValue = resultValue.types; this.machinesValue = resultValue.machines; this.technicians = resultValue.technicians; this.assigneeId = resultValue.technicians.find(userValue => userValue.id === this.authValue.userValue()?.id)?.id || null; const id=Number(this.sheetRoute.snapshot.queryParamMap.get('equipmentId'));if(id && this.machinesValue.some(e=>e.id===id)){this.machineId=id;this.selectEquipmentSheet();if(this.sheetRoute.snapshot.queryParamMap.get('tab')==='TIPOS_OS')this.selectSheetTab('TIPOS_OS');} },
            error: () => this.errorValue = 'Não foi possível carregar as máquinas. Recarregue a página para tentar novamente.'
        });
    }
    /** Consulta agenda, histórico e OS em paralelo. Evita consultas sobrepostas, agenda uma atualização pendente e avisa quando a leitura falha, sem ocultar o possível desatualizado. */
    loadAlerts() {
        if (this.loadingAlerts) { this.pendingAlertRefresh = true; return; }
        this.loadingAlerts = true;
        forkJoin({
            // Se uma consulta falhar, o aviso identifica que os dados visíveis podem estar antigos.
            scheduleValue: this.httpValue.get<{today:string; schedules:PreventiveSchedule[]; unconfigured_count:number}>('/api/preventive-schedules'),
            history: this.httpValue.get<PreventiveExecution[]>('/api/preventive-executions'),
            orders: this.httpValue.get<PreventiveOrder[]>('/api/preventive-orders')
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.loadingAlerts = false;
            this.cdr.markForCheck();
            if (this.pendingAlertRefresh && !this.destroyRef.destroyed) {
                this.pendingAlertRefresh = false;
                this.loadAlerts();
            }
        })).subscribe({
            next: resultValue => {
                this.orderTypeAlertsLoaded=true; this.schedulesValue = resultValue.scheduleValue.schedules; this.today = resultValue.scheduleValue.today;
                this.unconfiguredCount = resultValue.scheduleValue.unconfigured_count; this.executions = resultValue.history; this.ordersValue = resultValue.orders; this.alertsError = ''; if(this.sheetTab==='TIPOS_OS' && !this.orderTypesChanged){const messageValue=this.orderTypesMessage;this.resetOrderTypes();this.orderTypesMessage=messageValue;}
                if (this.sheetTab === 'ROTEIRO' && this.selectedSchedule) {
                    this.plannedDate ||= this.selectedSchedule.next_due;
                    this.loadShifts();
                }
            },
            error: () => this.alertsError = 'Não foi possível atualizar os alertas. Os dados exibidos podem estar desatualizados.'
        });
    }
    /** Copia a máquina, o tipo e a frequência de uma linha da agenda para o formulário; carrega seu roteiro e rola até o gerador. */
    useSchedule(row: PreventiveSchedule) {
        if (this.loading || this.working) return;
        this.view = 'EQUIPAMENTOS';
        this.typeId = row.equipment_type_id; this.frequencyValue = row.frequency; this.machineId = row.equipment_id;
        this.sheetTab = 'ROTEIRO';
        this.load();
        this.scrollToSheet();
    }
    /** Abre a identificação da máquina a partir do cronograma, reutilizando a mesma seleção do checklist. */
    showEquipment(row: PreventiveSchedule) { this.useSchedule(row); this.sheetTab = 'GERAIS'; }
    /** O seletor no topo abre qualquer equipamento. Quando há agenda, sugere uma frequência já configurada. */
    selectEquipmentSheet() {
        this.view = 'EQUIPAMENTOS';
        const machineValue = this.machineValue;
        this.sheetTab = 'GERAIS';
        if (!machineValue) return;
        this.typeId = machineValue.equipment_type_id;
        const schedules = machineValue.preventive_schedules || [];
        if (!schedules.some(scheduleValue => scheduleValue.frequency === this.frequencyValue) && schedules.length) this.frequencyValue = schedules[0].frequency;
        this.load();
    }
    /** Aguarda o Angular mostrar a seção antes de rolar até a ficha escolhida. */
    scrollToSheet() { requestAnimationFrame(() => document.getElementById('equipment-sheet')?.scrollIntoView({behavior:'smooth', block:'start'})); }
    /** Se já existir OS aberta para a agenda, abre seu preenchimento. Caso contrário, seleciona a agenda no formulário para emitir a OS primeiro. */
    openCompletion(row: PreventiveSchedule) {
        const orderValue = this.openedOrder(row);
        if (orderValue) this.openOrderDetails(orderValue); else this.useSchedule(row);
    }
    /** Limpa a máquina escolhida ao trocar o tipo e recarrega o roteiro correspondente, evitando combinar máquina e tipo incompatíveis. */
    changeType() { this.machineId = null; this.load(); }
    /** GET /api/preventive-checklists lê o roteiro do tipo ou da máquina selecionada. Reinicia mensagens e usa o vencimento da agenda como sugestão de data prevista. */
    load() {
        if (!this.filteredMachines.some(machineValue => machineValue.id === this.machineId)) this.machineId = null;
        if (this.machineValue) this.lastSheetMachine = this.machineValue;
        this.text = this.savedText = this.errorValue = this.messageValue = '';
        if (!this.typeId) return;
        this.plannedDate = this.selectedSchedule?.next_due || this.today;
        this.plannedTime = this.selectedSchedule?.planned_time?.slice(0,5) || '';
        this.loadShifts();
        // Sem agenda não consultamos o roteiro específico: a API exige uma preventiva ativa para esse endpoint.
        if (this.machineValue && !this.machineValue.preventive_schedules?.some(scheduleValue => scheduleValue.frequency === this.frequencyValue)) return;
        this.loading = true;
        const paramsValue: Record<string,string|number> = {equipmentTypeId:this.typeId, frequency:this.frequencyValue};
        // equipmentId escolhe o roteiro específico; sem ele consultamos o padrão do tipo.
        if (this.machineId) paramsValue['equipmentId'] = this.machineId;
        this.httpValue.get<{items:string[];source:string}>('/api/preventive-checklists', {params: paramsValue}).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.loading = false; this.cdr.markForCheck();})).subscribe({
            next: dataValue => { this.text = this.savedText = dataValue.items.join('\n'); this.scheduleSource = dataValue.source; },
            error: () => this.errorValue = 'Não foi possível carregar o checklist. Selecione novamente a periodicidade para tentar novamente.'
        });
    }
    loadShifts() {
        const lookup = ++this.shiftLookup;
        const schedule = this.selectedSchedule;
        this.shifts = [];
        this.shiftError = '';
        this.loadingShifts = !!schedule && !!this.plannedDate;
        if (!schedule || !this.plannedDate) return;
        this.httpValue.get<typeof this.shifts>('/api/preventive-orders/shifts', {
            params: {scheduleId: schedule.id, date: this.plannedDate},
        }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: shifts => {
                if (lookup !== this.shiftLookup) return;
                this.shifts = shifts;
                this.loadingShifts = false;
                if (!shifts.some(shift => shift.time === this.plannedTime && shift.available)) {
                    this.plannedTime = shifts.find(shift => shift.available)?.time || '';
                }
                this.cdr.markForCheck();
            },
            error: failure => {
                if (lookup !== this.shiftLookup) return;
                this.loadingShifts = false;
                this.shiftError = failure.error?.error || 'Não foi possível consultar os turnos. Tente novamente.';
                this.cdr.markForCheck();
            },
        });
    }

    /** PUT /api/preventive-checklists salva o roteiro padrão sem máquina ou um específico com equipmentId. Só atualiza o texto considerado salvo após a confirmação do servidor. */
    save() {
        if (!this.typeId || this.loading || this.working || !this.items.length || (this.machineId && !this.selectedSchedule)) return;
        this.working = true; this.errorValue = this.messageValue = '';
        this.httpValue.put<{items:string[];source:string}>('/api/preventive-checklists', {equipmentTypeId:this.typeId, equipmentId:this.machineId, frequency:this.frequencyValue, items:this.items}).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.working = false; this.cdr.markForCheck();})).subscribe({
            next: dataValue => { this.text = this.savedText = dataValue.items.join('\n'); this.scheduleSource = dataValue.source; this.messageValue = this.machineId ? 'Roteiro salvo para este equipamento e periodicidade.' : 'Roteiro padrão salvo para este tipo e periodicidade.'; },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível salvar o checklist.'
        });
    }
    /** POST /api/preventive-orders emite a OS com referência de vencimento, previsão, técnico e regra de renovação. Depois atualiza as listas e inicia o download da ficha salva. */
    gerar() {
        if (!this.canGenerate || !this.typeId || !this.machineId) return;
        this.working = true; this.errorValue = this.messageValue = '';
        this.httpValue.post<PreventiveOrderDetail>('/api/preventive-orders', {
            scheduleId:this.selectedSchedule!.id, expectedDueDate:this.selectedSchedule!.next_due,
            plannedDate:this.plannedDate, plannedTime:this.plannedTime || null, assignedToId:this.assigneeId, recurrenceBasis:this.recurrenceBase
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.working = false; this.cdr.markForCheck();})).subscribe({
            next: orderValue => {
                this.messageValue = `${orderValue.number} emitida. Após realizar a manutenção, abra “Preencher OS” para registrar cada atividade.`;
                this.loadAlerts(); this.downloadOrder(orderValue);
            },
            error: failure => { this.errorValue = failure.error?.error || 'Não foi possível emitir a OS.'; this.loadAlerts(); this.loadShifts(); }
        });
    }
    /** Remove a personalização da máquina com useTypeDefault=true e passa a exibir o roteiro padrão do tipo. As OS já emitidas continuam com seus próprios itens. */
    usarRoteiroPadrao() {
        if (!this.machineId || this.working) return;
        this.working = true; this.errorValue = '';
        this.httpValue.put<{items:string[];source:string}>('/api/preventive-checklists', {equipmentTypeId:this.typeId, equipmentId:this.machineId, frequency:this.frequencyValue, useTypeDefault:true})
            .pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.working = false; this.cdr.markForCheck();})).subscribe({
                next: dataValue => { this.text = this.savedText = dataValue.items.join('\n'); this.scheduleSource = dataValue.source; },
                error: failure => this.errorValue = failure.error?.error || 'Não foi possível usar o roteiro padrão.'
            });
    }
    /** GET do documento da OS recebe um Blob autenticado, cria um link temporário de download e libera a URL depois. Falha no download não desfaz a OS já salva. */
    downloadOrder(orderValue: PreventiveOrder) {
        this.httpValue.get(`/api/preventive-orders/${orderValue.id}/document`, {responseType:'blob'}).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.cdr.markForCheck())).subscribe({
            next: blobValue => { const urlValue = URL.createObjectURL(blobValue); const link = document.createElement('a'); link.href=urlValue; link.download=orderValue.status === 'CONCLUIDA' ? `${orderValue.number}-relatorio.html` : `${orderValue.number}.html`; link.click(); setTimeout(() => URL.revokeObjectURL(urlValue),60000); },
            error: () => {
                const message = `A OS ${orderValue.number} está salva. Tente baixar o documento novamente.`;
                if (this.editingOrder?.id === orderValue.id) this.orderError = message;
                else this.errorValue = message;
            }
        });
    }
    /** GET /api/preventive-orders/:id busca a versão atual da OS para preencher ou consultar. A resposta alimenta o modal e inclui a revisão usada para gravar com segurança. */
    openOrderDetails(orderValue: PreventiveOrder) {
        if (this.working) return;
        this.working = true; this.errorValue = this.orderError = '';
        this.httpValue.get<PreventiveOrderDetail>(`/api/preventive-orders/${orderValue.id}`).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.working=false; this.cdr.markForCheck();})).subscribe({
            next: dataValue => this.editingOrder = dataValue,
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível carregar a OS.'
        });
    }
    /** Fecha o modal quando não há gravação em andamento. Valores locais ainda não salvos não são enviados ao servidor. */
    closeOrder() { if (!this.working) this.editingOrder = null; }
    /** Com conclude=false, PATCH salva parcialmente; com true, POST /complete conclui e renova a agenda. Envia revisão, resultados, peças e data/horário, tratando conflitos ou validações. */
    saveOrder(conclude = false) {
        const orderValue = this.editingOrder;
        if (!orderValue || this.working || orderValue.status !== 'ABERTA' || (conclude && !this.canCompleteOrder)) return;
        this.working=true; this.orderError='';
        const payload = {revision:orderValue.revision, results:orderValue.results, performedDate:orderValue.performed_date, performedTime:orderValue.performed_time, parts:orderValue.parts, notes:orderValue.notes};
        // O mesmo formulário pode salvar parcialmente ou concluir com validações adicionais.
        const request = conclude ? this.httpValue.post<PreventiveOrderDetail>(`/api/preventive-orders/${orderValue.id}/complete`,payload) : this.httpValue.patch<PreventiveOrderDetail>(`/api/preventive-orders/${orderValue.id}`,payload);
        request.pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.working=false; this.cdr.markForCheck();})).subscribe({
            next: dataValue => {
                this.editingOrder = dataValue;
                this.messageValue = conclude
                    ? `${dataValue.number} concluída. Relatório final disponível.`
                    : `${dataValue.number}: preenchimento salvo.`;
                this.loadAlerts();
                if (conclude) this.downloadOrder(dataValue);
            },
            error: failure => this.orderError=failure.error?.error || 'Não foi possível salvar a OS.'
        });
    }
    /** Abre a confirmação de cancelamento para a OS escolhida e limpa a justificativa anterior. Ainda não envia nenhuma alteração. */
    openCancellation(orderValue: PreventiveOrder) { if (!this.working) {this.orderToCancel=orderValue; this.cancellationReason=this.orderError='';} }
    /** POST /api/preventive-orders/:id/cancel envia revisão e justificativa. No sucesso fecha o modal e recarrega as listas; a API preserva o vencimento. */
    cancelOrder() {
        if (!this.orderToCancel || this.working) return;
        this.working=true; this.orderError='';
        this.httpValue.post(`/api/preventive-orders/${this.orderToCancel.id}/cancel`,{revision:this.orderToCancel.revision,reason:this.cancellationReason})
            .pipe(takeUntilDestroyed(this.destroyRef),finalize(() => {this.working=false;this.cdr.markForCheck();})).subscribe({
                next: () => {this.orderToCancel=null; this.messageValue='OS cancelada. O vencimento da agenda foi preservado.';this.loadAlerts();},
                error: failure => this.orderError=failure.error?.error || 'Não foi possível cancelar a OS.'
            });
    }
}
