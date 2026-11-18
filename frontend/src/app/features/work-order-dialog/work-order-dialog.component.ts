import {SpareParts} from '../spare-parts/spare-parts.component';
/** Módulo order-dialog: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ChangeDetectorRef, Component, DestroyRef, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { finalize } from 'rxjs';
import { PendingForm } from '../../shared/issue-form.component';
import {PartSheet, PartLookup} from '../../shared/part-sheet.component';
import { Auth } from '../../services';
import { OrderPartRequisition, OrderSparePart, WorkOrder } from '../../core/models/work-order.model';
@Component({
    standalone: true,
    imports: [PartSheet, PartLookup, CommonModule, FormsModule, MatButtonModule, MatIconModule, MatDialogModule, PendingForm],
    templateUrl: './work-order-dialog.component.html',
    styleUrl: './work-order-dialog.component.scss'
})
export class OrderDialog implements OnInit {
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    private httpValue = inject(HttpClient);
    authValue = inject(Auth);
    registrationValue = this.authValue.userValue()?.registration || '';
    passwordValue = '';
    /** Libera alteração somente para o técnico responsável por uma OS iniciada e ainda não concluída. */
    get canEdit() {
        return !!this.orderValue.started_at && this.orderValue.status !== 'CONCLUIDA' && this.orderValue.assigned_to === this.authValue.userValue()?.id;
    }
    /** POST /api/orders/:id/start: confirma as credenciais da conta conectada e recebe técnico, status e início gravados pelo servidor. */
    // Confirma a senha e registra quem começou o atendimento.
    startAttendance() {
        if (this.busy || !this.passwordValue)
            return;
        this.working = true;
        this.errorValue = '';
        this.dialogRefValue.disableClose = true;
        this.httpValue.post<WorkOrder>(`/api/orders/${this.orderValue.id}/start`, {
            registration: this.registrationValue, password: this.passwordValue
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.passwordValue = '';
            this.working = false;
            this.dialogRefValue.disableClose = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: orderValue => {
                this.orderValue = orderValue;

                this.messageValue = 'Início do atendimento registrado.';
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível iniciar o atendimento.'
        });
    }
    orderValue = inject<WorkOrder>(MAT_DIALOG_DATA);
    dialogRefValue = inject(MatDialogRef<OrderDialog>);
    @ViewChild('requestForm')
    requestForm?: ElementRef<HTMLElement>;

    rootCauseValue = this.orderValue.root_cause || '';
    correctiveActionValue = this.orderValue.corrective_action || '';
    preventiveActionValue = this.orderValue.preventive_action || '';
    errorValue = '';
    messageValue = '';
    working = false;
    concluding = false;
    requesting = false;
    loading = true;
    partsLoading = false;
    partsLoaded = false;
    showPending = false;
    tab: 'attendance' | 'parts' = 'attendance';
    requests: OrderPartRequisition[] = [];
    selectedPart: OrderSparePart | null = null;
    draft = {
        quantity: 1, note: ''
    };
    /** Unifica os bloqueios de gravação do atendimento e da solicitação de peças para impedir ações simultâneas. */
    get busy() {
        return this.working || this.requesting;
    }
    /** Documentos (manual e esquema elétrico) da máquina vinculada à OS. */
    readonly docLabels: Record<'MANUAL' | 'ELECTRICAL', string> = {MANUAL: 'Manual técnico', ELECTRICAL: 'Esquema elétrico'};
    docKinds: Array<'MANUAL' | 'ELECTRICAL'> = [];
    docsLoading = false;
    docOpening: 'MANUAL' | 'ELECTRICAL' | null = null;
    docError = '';

    /** GET /api/equipment/:id/attachments: mostra só os PDFs que existem para a máquina. */
    loadDocuments() {
        if (!this.orderValue.equipment_id) return;
        this.docsLoading = true;
        this.httpValue.get<{kind: string}[]>(`/api/equipment/${this.orderValue.equipment_id}/attachments`).pipe(
            takeUntilDestroyed(this.destroyRef),
            finalize(() => { this.docsLoading = false; this.cdr.markForCheck(); }),
        ).subscribe({
            next: files => this.docKinds = (['MANUAL', 'ELECTRICAL'] as const).filter(kind => files.some(file => file.kind === kind)),
            error: () => this.docError = 'Não foi possível consultar a documentação da máquina.',
        });
    }

    /** Abre o PDF em nova aba; a aba é criada antes do download para não ser bloqueada como pop-up. */
    openDocument(kind: 'MANUAL' | 'ELECTRICAL') {
        if (this.docOpening) return;
        this.docError = '';
        const tab = window.open('about:blank', '_blank');
        if (!tab) {
            this.docError = 'Permita pop-ups para abrir o PDF em outra aba.';
            return;
        }
        tab.opener = null;
        this.docOpening = kind;
        let opened = false;
        this.httpValue.get(`/api/equipment/${this.orderValue.equipment_id}/attachments/${kind}/view`, {responseType: 'blob'}).pipe(
            takeUntilDestroyed(this.destroyRef),
            finalize(() => {
                this.docOpening = null;
                if (!opened) tab.close();
                this.cdr.markForCheck();
            }),
        ).subscribe({
            next: blob => {
                if (tab.closed) return;
                const url = URL.createObjectURL(blob);
                tab.location.href = url;
                opened = true;
                setTimeout(() => URL.revokeObjectURL(url), 60000);
            },
            error: () => this.docError = 'Não foi possível abrir o documento. Tente novamente.',
        });
    }

    /** GET /api/orders/:id: lê a versão atual da OS e preenche diagnóstico e soluções do modal. */
    ngOnInit() {
        this.loadDocuments();
        this.httpValue.get<WorkOrder>(`/api/orders/${this.orderValue.id}`).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.loading = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: orderValue => {
                this.orderValue = orderValue;

                this.rootCauseValue = orderValue.root_cause || '';
                this.correctiveActionValue = orderValue.corrective_action || '';
                this.preventiveActionValue = orderValue.preventive_action || '';
            }, error: () => this.errorValue = 'Não foi possível atualizar os dados da OS.'
        });
    }
    /** Exibe a seção de peças e consulta seus dados somente quando ainda não foram carregados. */
    showParts() {
        this.tab = 'parts';
        if (!this.partsLoaded && !this.partsLoading)
            this.loadParts();
    }
    /** A OS carrega apenas suas solicitações. O catálogo é aberto pelo card quando necessário. */
    loadParts() {
        this.partsLoading = true;
        this.errorValue = '';
        this.httpValue.get<OrderPartRequisition[]>(`/api/orders/${this.orderValue.id}/part-requisitions`)
            .pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
                this.partsLoading = false;
                this.cdr.markForCheck();
            })).subscribe({
                next: rowsValue => { this.requests = rowsValue; this.partsLoaded = true; },
                error: () => this.errorValue = 'Não foi possível consultar as solicitações desta OS. Tente novamente.'
            });
    }
    private dialog = inject(MatDialog);
    /** Reutiliza a própria tela Spare Parts em modo de seleção, sem gravar ou abandonar a OS. */
    openPartsCatalog() {
        if(this.busy || this.loading)return;
        this.dialog.open(SpareParts, {
            width:'1180px',maxWidth:'96vw',maxHeight:'92vh',autoFocus:false,
            ariaLabel:'Spare Parts para a OS '+this.orderValue.id,
            data:{selectForWorkOrder:this.orderValue.id}
        }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(partValue => {
            if(partValue){this.choosePart(partValue);this.cdr.markForCheck();}
        });
    }
    /** Seleciona uma peça, inicia quantidade/observação e leva a rolagem até o formulário de solicitação. */
    choosePart(partValue: OrderSparePart) {
        this.selectedPart = partValue;
        this.errorValue = this.messageValue = '';
        this.draft = {
            quantity: 1, note: ''
        };
        setTimeout(() => this.requestForm?.nativeElement.scrollIntoView({
            block: 'nearest'
        }));
    }
    /** POST /api/orders/:id/part-requisitions registra a peça diretamente. Não cria compra, rascunho ou envio ao gestor. */
    createRequest() {
        if (this.busy || !this.selectedPart || this.draft.quantity <= 0)
            return;
        this.requesting = true;
        this.dialogRefValue.disableClose = true;
        this.errorValue = this.messageValue = '';
        this.httpValue.post<OrderPartRequisition>(`/api/orders/${this.orderValue.id}/part-requisitions`, {
            sparePartId: this.selectedPart.id, quantity: this.draft.quantity, note: this.draft.note.trim()
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.requesting = false;
            this.dialogRefValue.disableClose = this.busy;
            this.cdr.markForCheck();
        })).subscribe({
            next: request => {
                this.requests = [request, ...this.requests];
                this.selectedPart = null;
                this.messageValue = `Solicitação de peça SP-${request.id} registrada para esta OS e máquina.`;
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível criar a solicitação da peça.'
        });
    }
    /** PATCH /api/orders/:id envia status e os três campos técnicos; o Django determina responsável, fechamento e duração. */
    // Envia as alterações da OS para o servidor.
    save(conclude = false) {
        if (this.busy || this.loading || !this.canEdit)
            return;
        if (conclude && [this.rootCauseValue, this.correctiveActionValue, this.preventiveActionValue].some(value => !value.trim())) {
            this.errorValue = 'Preencha a causa raiz, a solução corretiva e a solução preventiva para concluir a OS.';
            return;
        }
        this.working = true;
        this.dialogRefValue.disableClose = true;
        this.errorValue = '';
        this.concluding = conclude;
        this.httpValue.patch<WorkOrder>(`/api/orders/${this.orderValue.id}`, {
            status: conclude ? 'CONCLUIDA' : 'EM_ANDAMENTO', rootCause: this.rootCauseValue, correctiveAction: this.correctiveActionValue, preventiveAction: this.preventiveActionValue
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.working = false;
            this.concluding = false;
            this.dialogRefValue.disableClose = this.busy;
            this.cdr.markForCheck();
        })).subscribe({
            next: () => {
                this.dialogRefValue.close(true);
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível salvar o atendimento.'
        });
    }
}
