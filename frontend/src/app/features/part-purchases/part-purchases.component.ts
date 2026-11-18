import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo spare-purchase: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ActivatedRoute } from '@angular/router';
import { FormModal } from '../../shared/form-modal.component';
import {PartSheet, PartLookup} from '../../shared/part-sheet.component';
import { finalize } from 'rxjs';
import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Auth } from '../../services';
interface Part {
    id: number;
    code: string;
    part_number: string | null;
    description: string;
    unit: string;
    fiscal_status: string | null;
    manufacturer?: string | null;
}
interface Manager {
    id: number;
    name: string;
}
interface Request {
    sector_name?: string | null;
    cost_center?: string;
    equipment_serial?: string | null;
    equipment_model?: string | null;
    work_order_id?: number | null;
    id: number;
    status: string;
    purchase_type: string;
    requester_id: number;
    manager_id: number;
    requester_name: string;
    manager_name: string;
    priority: string;
    created_at: string;
}
@Component({
    selector: 'app-compras-pecas', standalone: true, imports: [PartSheet, PartLookup, FormModal, CommonModule, FormsModule], templateUrl: './part-purchases.component.html', styleUrl: './part-purchases.component.scss'
})
/** Coordena ficha técnica, rascunho, envio e decisão; aprovação e histórico ficam no Django. */
export class SparePurchase implements OnInit {
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private readonly feedback = inject(RegistrationFeedback);
    private cdr = inject(ChangeDetectorRef);
    private routeValue = inject(ActivatedRoute);
    private httpValue = inject(HttpClient);
    private authValue = inject(Auth);
    partsValue: Part[] = [];
    partSearch = '';
    get filteredParts() {
        const searchTerm = this.partSearch.trim().toLocaleLowerCase('pt-BR');
        return this.partsValue.filter(partValue => partValue.id === this.draft.sparePartId || partValue.id === this.editingPart || [partValue.part_number,partValue.description,partValue.manufacturer].some(valueValue=>(valueValue||'').toLocaleLowerCase('pt-BR').includes(searchTerm)));
    }
    managers: Manager[] = [];
    sectors: {id: number; name: string; cost_center: string}[] = [];
    requests: Request[] = [];
    busy = false;
    errorValue = '';
    messageValue = '';
    selected = 0;
    details: any = null;
    readonly statusLabels: Record<string, string> = {
        RASCUNHO: 'Rascunho', EM_APROVACAO: 'Aguardando aprovação',
        DEVOLVIDA: 'Devolvida para revisão', REJEITADA: 'Rejeitada',
        APROVADA: 'Aprovada · aguardando recebimento', RECEBIDA_PARCIALMENTE: 'Recebida parcialmente', RECEBIDA: 'Recebida · encerrada',
    };
    readonly today = new Date().toLocaleDateString('sv-SE');
    receipt: {supplier: string; documentReference: string; movementDate: string;
        items: {partId: number; label: string; unit: string; pending: number; quantity: number;
            previousQuantity: number | null; needsCount: boolean}[]} | null = null;
    receiptError = '';
    private receiptAttempt: {payload: string; key: string} | null = null;

    startReceipt() {
        const items = new Map<number, NonNullable<typeof this.receipt>['items'][number]>();
        for (const row of this.details.items) {
            const pending = Number(row.pending_quantity);
            if (pending <= 0) continue;
            const partId = row.spare_part_id;
            const existing = items.get(partId);
            if (existing) {
                existing.pending += pending;
            } else {
                items.set(partId, {partId, label: row.part_number || row.description, unit: row.unit,
                    pending, quantity: 0, previousQuantity: null, needsCount: row.stock_quantity === null});
            }
        }
        this.receiptError = '';
        this.receipt = {supplier: '', documentReference: '', movementDate: this.today, items: [...items.values()]};
    }

    receive() {
        const receipt = this.receipt;
        if (!receipt || this.busy) return;
        const purchaseRequestId = this.selected;
        const payload = {purchaseRequestId, supplier: receipt.supplier.trim(),
            documentReference: receipt.documentReference.trim(), movementDate: receipt.movementDate,
            items: receipt.items.filter(item => item.quantity > 0).map(item => ({partId: item.partId, quantity: item.quantity.toFixed(3),
                previousQuantity: item.previousQuantity}))};
        if (!payload.items.length) {
            this.receiptError = 'Informe a quantidade de pelo menos uma peça recebida.';
            return;
        }
        const snapshot = JSON.stringify(payload);
        if (this.receiptAttempt?.payload !== snapshot) {
            this.receiptAttempt = {payload: snapshot, key: crypto.randomUUID()};
        }
        this.receiptError = '';
        this.busy = true;
        this.httpValue.post('/api/spare-parts/receipts', {...payload, requestKey: this.receiptAttempt.key})
            .pipe(finalize(() => {this.busy = false; this.cdr.markForCheck();}))
            .subscribe({
                next: () => {
                    this.receipt = null;
                    this.receiptAttempt = null;
                    this.openValue(purchaseRequestId);
                    this.loadData();
                    this.feedback.show('Recebimento confirmado', 'SC-' + purchaseRequestId + ' · NF ' + payload.documentReference, 'OK');
                },
                error: error => this.receiptError = error.error?.error || 'Não foi possível registrar o recebimento.',
            });
    }
    editingPart = 0;
    showTechnicalSheet = false;
    showPurchase = false;
    /** Abre uma solicitação de COMPRA com valores iniciais; este fluxo é separado da solicitação direta na OS. */
    newPurchase() {
        this.partSearch = '';
        this.errorValue = '';
        this.draft = {
            purchaseType: 'NACIONAL', sectorId: this.sectors.length === 1 ? this.sectors[0].id : null, managerId: 0, workOrderId: null, equipmentId: null, justification: '', priority: 'MEDIA', sparePartId: 0, quantity: 1
        };
        this.showPurchase = true;
    }
    technicalSheet: any = {};
    missingFields: string[] = [];
    draft = {
        purchaseType: 'NACIONAL', sectorId: null as number | null, managerId: 0, workOrderId: null as number | null, equipmentId: null as number | null, justification: '', priority: 'MEDIA', sparePartId: 0, quantity: 1
    };
    fields = [['description_en', 'Descrição inglês'], ['description_pt', 'Descrição técnica em português'], ['ncm', 'NCM (validar com área fiscal)'], ['pli_description', 'Descrição para PLI'], ['classification', 'Máquina / Equipamento / Peça de reposição'], ['independent_function', 'Funcionamento / função própria'], ['connection_details', 'Registrador / conexões'], ['useful_life', 'Vida útil estimada'], ['asset_classification', 'Ativo fixo ou uso e consumo'], ['main_function', 'Função principal'], ['secondary_function', 'Função secundária'], ['raw_material', 'Matéria-prima'], ['intended_use', 'Utilização e linha de produção'], ['application_machine', 'Máquina / nº de série / PO'], ['mechanical_electrical', 'Mecânico ou elétrico'], ['current_type', 'Tipo de corrente'], ['power', 'Potência'], ['voltage', 'Voltagem'], ['amperage', 'Amperagem'], ['picture_reference', 'Referência da foto']];
    /** Carrega peças, gestores e compras; abre o detalhe indicado por requestId quando a URL o contém. */
    ngOnInit() {
        if (this.authValue.userValue()?.role !== 'OPERADOR') {
            this.httpValue.get<typeof this.sectors>('/api/sectors')
                .pipe(finalize(() => this.cdr.markForCheck()))
                .subscribe({next: sectors => this.sectors = sectors,
                    error: () => this.errorValue = 'Não foi possível carregar os setores.'});
        }
        this.loadData();
        const requestId = Number(this.routeValue.snapshot.queryParamMap.get('requestId'));
        if (Number.isInteger(requestId) && requestId > 0)
            this.openValue(requestId);
    }
    /** Consulta o perfil local para apresentar ações administrativas da compra. */
    isAdmin() {
        return this.authValue.userValue()?.role === 'ADMINISTRADOR';
    }
    /** Consulta os três endpoints de compras para preencher peças, gestores e solicitações. */
    loadData() {
        this.httpValue.get<Part[]>('/api/spare-purchase/parts').pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.partsValue = x, error: () => this.errorValue = 'Falha ao carregar peças. Verifique se a API e a migração estão instaladas.'
        });
        this.httpValue.get<Manager[]>('/api/spare-purchase/managers').pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.managers = x
        });
        this.httpValue.get<Request[]>('/api/spare-purchase/requests').pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.requests = x
        });
    }
    // Consulta a ficha reutilizável da peça selecionada.
    /** GET da ficha técnica carrega os campos reutilizáveis da peça selecionada. */
    openTechnicalSheet() {
        if (!this.editingPart)
            return;
        this.httpValue.get<any>(`/api/spare-purchase/parts/${this.editingPart}/technical`).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.technicalSheet = x, error: e => this.errorValue = e.error?.error || 'Erro ao buscar ficha'
        });
    }
    // Envia os campos técnicos; uma mudança faz o backend revogar a validação fiscal anterior.
    /** PUT atualiza a ficha técnica; o Django retorna a validação fiscal ao estado pendente. */
    saveTechnicalSheet() {
        if (this.busy)
            return;
        const dataValue: any = {};
        for (const [key] of this.fields)
            dataValue[key] = this.technicalSheet[key] ?? null;
        this.busy = true;
        this.httpValue.put(`/api/spare-purchase/parts/${this.editingPart}/technical`, dataValue).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.busy = false;
                this.showTechnicalSheet = false;
                this.messageValue = 'Ficha técnica salva. Classificação fiscal voltou para PENDENTE.';
                this.loadData();
            }, error: e => {
                this.busy = false;
                this.errorValue = e.error?.error || 'Falha ao salvar ficha';
            }
        });
    }
    // Pede validação interna; o Django exige administrador, NCM e descrição PLI.
    /** POST de validação fiscal interna exige administrador e campos obrigatórios no servidor. */
    validar() {
        if (this.busy)
            return;
        this.busy = true;
        this.httpValue.post(`/api/spare-purchase/parts/${this.editingPart}/validate`, {}).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.busy = false;
                this.messageValue = 'Validação interna registrada';
                this.openTechnicalSheet();
                this.loadData();
            }, error: e => {
                this.busy = false;
                this.errorValue = e.error?.error || 'Falha na validação';
            }
        });
    }
    // Converte a peça selecionada no array items; a API aceita também compras com várias peças.
    /** POST /api/spare-purchase/requests cria o rascunho de compra com os itens escolhidos e abre seu detalhe. */
    cadastrar() {
        if (this.busy)
            return;
        this.errorValue = '';
        if (!this.draft.sectorId && !this.draft.workOrderId && !this.draft.equipmentId && this.isAdmin()) {
            this.errorValue = 'Selecione o setor de destino da compra.';
            return;
        }
        if (!this.draft.managerId || !this.draft.sparePartId || !this.draft.justification.trim()) {
            this.errorValue = 'Informe gestor, peça e justificativa.';
            return;
        }
        this.busy = true;
        const { sparePartId, quantity, ...rest } = this.draft;
        this.httpValue.post<any>('/api/spare-purchase/requests', {
            ...rest, items: [{
                    sparePartId, quantity
                }]
        }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: r => {
                this.busy = false;
                this.showPurchase = false;
                this.messageValue = `Rascunho SC-${r.id} criado`;
                this.loadData();
                this.openValue(r.id);
            }, error: e => {
                this.busy = false;
                this.errorValue = e.error?.error || 'Erro ao cadastrar solicitação';
            }
        });
    }
    /** GET /api/spare-purchase/requests/:id carrega cabeçalho, itens e eventos da compra. */
    openValue(id: number) {
        this.selected = id;
        this.receipt = null;
        this.details = null;
        this.httpValue.get<any>(`/api/spare-purchase/requests/${id}`).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: r => {
                if (this.selected !== id) return;
                this.details = r;
                this.missingFields = [];
            }, error: e => this.errorValue = e.error?.error || 'Erro ao consultar solicitação'
        });
    }
    // Solicita validação e congelamento dos dados técnicos antes de encaminhar ao gestor.
    // TODO integração: a tela espera error.missing, mas o Django ainda envia somente error neste fluxo.
    /** POST de envio pede validação e congelamento das fichas antes de encaminhar a compra ao gestor; a API registra o encaminhamento sem disparar e-mail. */
    enviar() {
        this.errorValue = '';
        this.missingFields = [];
        this.httpValue.post<any>(`/api/spare-purchase/requests/${this.selected}/submit`, {}).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: r => {
                this.messageValue = r.notification === 'PENDENTE' ? 'Encaminhada ao gestor. Notificação registrada para envio.' : 'Encaminhada ao gestor. E-mail ainda não configurado.';
                this.openValue(this.selected);
                this.loadData();
            }, error: e => {
                this.errorValue = e.error?.error || 'Erro ao submeter';
                this.missingFields = (e.error?.missing || []).map((x: any) => `${x.part_number}: ${x.field}`);
            }
        });
    }
    // Envia decisão e observação; somente o administrador designado pode decidir no servidor.
    /** Envia decisão e observação; o Django exige o gestor designado e a compra em aprovação. */
    decidir(decision: string) {
        const comment = prompt(decision === 'APROVADA' ? 'Observação (opcional)' : 'Informe o motivo da decisão');
        if (comment === null) return;
        if (decision !== 'APROVADA' && !comment.trim()) {
            this.errorValue = 'Informe o motivo para devolver ou rejeitar a solicitação.';
            return;
        }
        this.httpValue.post(`/api/spare-purchase/requests/${this.selected}/decision`, {
            decision, comment
        }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.messageValue = 'Decisão registrada';
                this.openValue(this.selected);
                this.loadData();
            }, error: e => this.errorValue = e.error?.error || 'Falha na decisão'
        });
    }
    // Baixa um CSV autenticado dos dados congelados no envio, quando a compra está disponível para exportação.
    /** GET export.csv baixa os dados congelados em Blob autenticado e cria um download temporário. */
    baixar() {
        const token = sessionStorage.getItem('mantisToken');
        this.httpValue.get(`/api/spare-purchase/requests/${this.selected}/export.csv`, {
            responseType: 'blob', headers: token ? {
                Authorization: `Bearer ${token}`
            } : {}
        }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: b => {
                const u = URL.createObjectURL(b), a = document.createElement('a');
                a.href = u;
                a.download = `SC-${this.selected}-DADOS-TECNICOS.csv`;
                a.click();
                URL.revokeObjectURL(u);
            }, error: () => this.errorValue = 'Exportação indisponível. Encaminhe a solicitação primeiro.'
        });
    }
    // Exibe envio ao autor de um rascunho ou de uma solicitação devolvida; a API repete a restrição.
    /** Exibe envio somente ao solicitante de uma compra em rascunho ou devolvida. */
    podeEnviar() {
        return this.details && this.details.requester_id === this.authValue.userValue()?.id && ['RASCUNHO', 'DEVOLVIDA'].includes(this.details.status);
    }
    // Exibe decisões para o gestor designado; o backend também confere perfil e estado da compra.
    /** Exibe decisão apenas ao administrador designado enquanto a compra aguarda aprovação. */
    podeDecidir() {
        return this.details && this.details.manager_id === this.authValue.userValue()?.id && this.details.status === 'EM_APROVACAO' && this.isAdmin();
    }
}
