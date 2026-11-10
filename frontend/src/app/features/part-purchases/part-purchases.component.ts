/** Módulo spare-purchase: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ActivatedRoute } from '@angular/router';
import { FormModal } from '../../shared/form-modal.component';
import { PartSheet, PartQuery } from '../../shared/part-sheet.component';
import { finalize } from 'rxjs';
import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Authentication } from '../../services';
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
interface PurchaseRequest {
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
    selector: 'app-compras-pecas',
    standalone: true,
    imports: [PartSheet, PartQuery, FormModal, CommonModule, FormsModule],
    templateUrl: './part-purchases.component.html',
    styleUrl: './part-purchases.component.scss',
})
/** Coordena ficha técnica, rascunho, envio e decisão; aprovação e histórico ficam no Django. */
export class PartPurchases implements OnInit {
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    private route = inject(ActivatedRoute);
    private httpClient = inject(HttpClient);
    private authentication = inject(Authentication);
    parts: Part[] = [];
    searchParts = '';
    get partsFiltered() {
        const term = this.searchParts.trim().toLocaleLowerCase('pt-BR');
        return this.parts.filter(
            (part) =>
                part.id === this.draft.sparePartId ||
                part.id === this.partInEditing ||
                [part.part_number, part.description, part.manufacturer].some(
                    (value) =>
                        (value || '').toLocaleLowerCase('pt-BR').includes(term)
                )
        );
    }
    managers: Manager[] = [];
    requests: PurchaseRequest[] = [];
    busy = false;
    error = '';
    message = '';
    selected = 0;
    details: any = null;
    partInEditing = 0;
    showSheetTechnical = false;
    showPurchase = false;
    /** Abre uma solicitação de COMPRA com valores iniciais; este fluxo é separado da solicitação direta na OS. */
    newPurchase() {
        this.searchParts = '';
        this.error = '';
        this.draft = {
            purchaseType: 'NACIONAL',
            managerId: 0,
            workOrderId: null,
            equipmentId: null,
            justification: '',
            priority: 'MEDIA',
            sparePartId: 0,
            quantity: 1,
        };
        this.showPurchase = true;
    }
    sheetTechnical: any = {};
    fieldsMissing: string[] = [];
    draft = {
        purchaseType: 'NACIONAL',
        managerId: 0,
        workOrderId: null as number | null,
        equipmentId: null as number | null,
        justification: '',
        priority: 'MEDIA',
        sparePartId: 0,
        quantity: 1,
    };
    fields = [
        ['description_en', 'Descrição inglês'],
        ['description_pt', 'Descrição técnica em português'],
        ['ncm', 'NCM (validar com área fiscal)'],
        ['pli_description', 'Descrição para PLI'],
        ['classification', 'Máquina / Equipamento / Peça de reposição'],
        ['independent_function', 'Funcionamento / função própria'],
        ['connection_details', 'Registrador / conexões'],
        ['useful_life', 'Vida útil estimada'],
        ['asset_classification', 'Ativo fixo ou uso e consumo'],
        ['main_function', 'Função principal'],
        ['secondary_function', 'Função secundária'],
        ['raw_material', 'Matéria-prima'],
        ['intended_use', 'Utilização e linha de produção'],
        ['application_machine', 'Máquina / nº de série / PO'],
        ['mechanical_electrical', 'Mecânico ou elétrico'],
        ['current_type', 'Tipo de corrente'],
        ['power', 'Potência'],
        ['voltage', 'Voltagem'],
        ['amperage', 'Amperagem'],
        ['picture_reference', 'Referência da foto'],
    ];
    /** Carrega peças, gestores e compras; abre o detalhe indicado por requestId quando a URL o contém. */
    ngOnInit() {
        this.loadData();
        const requestId = Number(
            this.route.snapshot.queryParamMap.get('requestId')
        );
        if (Number.isInteger(requestId) && requestId > 0) this.open(requestId);
    }
    /** Consulta o perfil local para apresentar ações administrativas da compra. */
    administrator() {
        return this.authentication.user()?.role === 'ADMINISTRADOR';
    }
    /** Consulta os três endpoints de compras para preencher peças, gestores e solicitações. */
    loadData() {
        this.httpClient
            .get<Part[]>('/api/spare-purchase/parts')
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.parts = x),
                error: () =>
                    (this.error =
                        'Falha ao carregar peças. Verifique se a API e a migração estão instaladas.'),
            });
        this.httpClient
            .get<Manager[]>('/api/spare-purchase/managers')
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.managers = x),
            });
        this.httpClient
            .get<PurchaseRequest[]>('/api/spare-purchase/requests')
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.requests = x),
            });
    }
    // Consulta a ficha reutilizável da peça selecionada.
    /** GET da ficha técnica carrega os campos reutilizáveis da peça selecionada. */
    openSheetTechnical() {
        if (!this.partInEditing) return;
        this.httpClient
            .get<any>(
                `/api/spare-purchase/parts/${this.partInEditing}/technical`
            )
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.sheetTechnical = x),
                error: (e) =>
                    (this.error = e.error?.error || 'Erro ao buscar ficha'),
            });
    }
    // Envia os campos técnicos; uma mudança faz o backend revogar a validação fiscal anterior.
    /** PUT atualiza a ficha técnica; o Django retorna a validação fiscal ao estado pendente. */
    saveSheetTechnical() {
        if (this.busy) return;
        const data: any = {};
        for (const [key] of this.fields)
            data[key] = this.sheetTechnical[key] ?? null;
        this.busy = true;
        this.httpClient
            .put(
                `/api/spare-purchase/parts/${this.partInEditing}/technical`,
                data
            )
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.busy = false;
                    this.showSheetTechnical = false;
                    this.message =
                        'Ficha técnica salva. Classificação fiscal voltou para PENDENTE.';
                    this.loadData();
                },
                error: (e) => {
                    this.busy = false;
                    this.error = e.error?.error || 'Falha ao salvar ficha';
                },
            });
    }
    // Pede validação interna; o Django exige administrador, NCM e descrição PLI.
    /** POST de validação fiscal interna exige administrador e campos obrigatórios no servidor. */
    validate() {
        if (this.busy) return;
        this.busy = true;
        this.httpClient
            .post(
                `/api/spare-purchase/parts/${this.partInEditing}/validate`,
                {}
            )
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.busy = false;
                    this.message = 'Validação interna registrada';
                    this.openSheetTechnical();
                    this.loadData();
                },
                error: (e) => {
                    this.busy = false;
                    this.error = e.error?.error || 'Falha na validação';
                },
            });
    }
    // Converte a peça selecionada no array items; a API aceita também compras com várias peças.
    /** POST /api/spare-purchase/requests cria o rascunho de compra com os itens escolhidos e abre seu detalhe. */
    register() {
        if (this.busy) return;
        this.error = '';
        if (
            !this.draft.managerId ||
            !this.draft.sparePartId ||
            !this.draft.justification.trim()
        ) {
            this.error = 'Informe gestor, peça e justificativa.';
            return;
        }
        this.busy = true;
        const { sparePartId, quantity, ...rest } = this.draft;
        this.httpClient
            .post<any>('/api/spare-purchase/requests', {
                ...rest,
                items: [
                    {
                        sparePartId,
                        quantity,
                    },
                ],
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (r) => {
                    this.busy = false;
                    this.showPurchase = false;
                    this.message = `Rascunho SC-${r.id} criado`;
                    this.loadData();
                    this.open(r.id);
                },
                error: (e) => {
                    this.busy = false;
                    this.error =
                        e.error?.error || 'Erro ao cadastrar solicitação';
                },
            });
    }
    /** GET /api/spare-purchase/requests/:id carrega cabeçalho, itens e eventos da compra. */
    open(id: number) {
        this.selected = id;
        this.httpClient
            .get<any>(`/api/spare-purchase/requests/${id}`)
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (r) => {
                    this.details = r;
                    this.fieldsMissing = [];
                },
                error: (e) =>
                    (this.error =
                        e.error?.error || 'Erro ao consultar solicitação'),
            });
    }
    // Solicita validação e congelamento dos dados técnicos antes de encaminhar ao gestor.
    // TODO integração: a tela espera error.missing, mas o Django ainda envia somente error neste fluxo.
    /** POST de envio pede validação e congelamento das fichas antes de encaminhar a compra ao gestor; a API registra o encaminhamento sem disparar e-mail. */
    send() {
        this.error = '';
        this.fieldsMissing = [];
        this.httpClient
            .post<any>(
                `/api/spare-purchase/requests/${this.selected}/submit`,
                {}
            )
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (r) => {
                    this.message =
                        r.notification === 'PENDENTE'
                            ? 'Encaminhada ao gestor. Notificação registrada para envio.'
                            : 'Encaminhada ao gestor. E-mail ainda não configurado.';
                    this.open(this.selected);
                    this.loadData();
                },
                error: (e) => {
                    this.error = e.error?.error || 'Erro ao submeter';
                    this.fieldsMissing = (e.error?.missing || []).map(
                        (x: any) => `${x.part_number}: ${x.field}`
                    );
                },
            });
    }
    // Envia decisão e observação; somente o administrador designado pode decidir no servidor.
    /** Envia decisão e observação; o Django exige o gestor designado e a compra em aprovação. */
    decide(decision: string) {
        const comment = prompt('Justificativa / observação (opcional):') ?? '';
        this.httpClient
            .post(`/api/spare-purchase/requests/${this.selected}/decision`, {
                decision,
                comment,
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.message = 'Decisão registrada';
                    this.open(this.selected);
                    this.loadData();
                },
                error: (e) =>
                    (this.error = e.error?.error || 'Falha na decisão'),
            });
    }
    // Baixa um CSV autenticado dos dados congelados no envio, quando a compra está disponível para exportação.
    /** GET export.csv baixa os dados congelados em Blob autenticado e cria um download temporário. */
    download() {
        const token = sessionStorage.getItem('mantisToken');
        this.httpClient
            .get(`/api/spare-purchase/requests/${this.selected}/export.csv`, {
                responseType: 'blob',
                headers: token
                    ? {
                          Authorization: `Bearer ${token}`,
                      }
                    : {},
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (b) => {
                    const u = URL.createObjectURL(b),
                        a = document.createElement('a');
                    a.href = u;
                    a.download = `SC-${this.selected}-DADOS-TECNICOS.csv`;
                    a.click();
                    URL.revokeObjectURL(u);
                },
                error: () =>
                    (this.error =
                        'Exportação indisponível. Encaminhe a solicitação primeiro.'),
            });
    }
    // Exibe envio ao autor de um rascunho ou de uma solicitação devolvida; a API repete a restrição.
    /** Exibe envio somente ao solicitante de uma compra em rascunho ou devolvida. */
    canSend() {
        return (
            this.details &&
            this.details.requester_id === this.authentication.user()?.id &&
            ['RASCUNHO', 'DEVOLVIDA'].includes(this.details.status)
        );
    }
    // Exibe decisões para o gestor designado; o backend também confere perfil e estado da compra.
    /** Exibe decisão apenas ao administrador designado enquanto a compra aguarda aprovação. */
    canDecide() {
        return (
            this.details &&
            this.details.manager_id === this.authentication.user()?.id &&
            this.details.status === 'EM_APROVACAO' &&
            this.administrator()
        );
    }
}
