import { SpareParts } from '../spare-parts/spare-parts.component';
/** Módulo order-dialog: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    ElementRef,
    OnInit,
    ViewChild,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import {
    MAT_DIALOG_DATA,
    MatDialog,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import { finalize } from 'rxjs';
import { PendencyForm } from '../../shared/pendency-form.component';
import { PartSheet, PartQuery } from '../../shared/part-sheet.component';
import { Authentication } from '../../services';
import {
    WorkOrderPartRequisition,
    WorkOrderPart,
    WorkOrder,
} from '../../core/models/work-order.model';
@Component({
    standalone: true,
    imports: [
        PartSheet,
        PartQuery,
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatIconModule,
        MatDialogModule,
        PendencyForm,
    ],
    templateUrl: './work-order-dialog.component.html',
    styleUrl: './work-order-dialog.component.scss',
})
export class WorkOrderDialog implements OnInit {
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    private httpClient = inject(HttpClient);
    authentication = inject(Authentication);
    registration = this.authentication.user()?.registration || '';
    password = '';
    /** Libera alteração somente para o técnico responsável por uma OS iniciada e ainda não concluída. */
    get canEdit() {
        return (
            !!this.order.started_at &&
            this.order.status !== 'CONCLUIDA' &&
            this.order.assigned_to === this.authentication.user()?.id
        );
    }
    /** POST /api/orders/:id/start: confirma as credenciais da conta conectada e recebe técnico, status e início gravados pelo servidor. */
    startService() {
        if (this.busy || !this.password) return;
        this.processing = true;
        this.error = '';
        this.dialogReference.disableClose = true;
        this.httpClient
            .post<WorkOrder>(`/api/orders/${this.order.id}/start`, {
                registration: this.registration,
                password: this.password,
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.password = '';
                    this.processing = false;
                    this.dialogReference.disableClose = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (order) => {
                    this.order = order;
                    this.status = order.status;
                    this.message = 'Início do atendimento registrado.';
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível iniciar o atendimento.'),
            });
    }
    order = inject<WorkOrder>(MAT_DIALOG_DATA);
    dialogReference = inject(MatDialogRef<WorkOrderDialog>);
    @ViewChild('requestForm')
    requestForm?: ElementRef<HTMLElement>;
    status = this.order.status;
    rootCause = this.order.root_cause || '';
    correctiveAction = this.order.corrective_action || '';
    preventiveAction = this.order.preventive_action || '';
    error = '';
    message = '';
    processing = false;
    requesting = false;
    loading = true;
    loadingParts = false;
    partsLoaded = false;
    showPendency = false;
    tab: 'attendance' | 'parts' = 'attendance';
    requests: WorkOrderPartRequisition[] = [];
    partSelected: WorkOrderPart | null = null;
    draft = {
        quantity: 1,
        note: '',
    };
    /** Unifica os bloqueios de gravação do atendimento e da solicitação de peças para impedir ações simultâneas. */
    get busy() {
        return this.processing || this.requesting;
    }
    /** GET /api/orders/:id: lê a versão atual da OS e preenche diagnóstico e soluções do modal. */
    ngOnInit() {
        this.httpClient
            .get<WorkOrder>(`/api/orders/${this.order.id}`)
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (order) => {
                    this.order = order;
                    this.status = order.status;
                    this.rootCause = order.root_cause || '';
                    this.correctiveAction = order.corrective_action || '';
                    this.preventiveAction = order.preventive_action || '';
                },
                error: () =>
                    (this.error = 'Não foi possível atualizar os dados da OS.'),
            });
    }
    /** Exibe a seção de peças e consulta seus dados somente quando ainda não foram carregados. */
    showParts() {
        this.tab = 'parts';
        if (!this.partsLoaded && !this.loadingParts) this.loadParts();
    }
    /** A OS carrega apenas suas solicitações. O catálogo é aberto pelo card quando necessário. */
    loadParts() {
        this.loadingParts = true;
        this.error = '';
        this.httpClient
            .get<WorkOrderPartRequisition[]>(
                `/api/orders/${this.order.id}/part-requisitions`
            )
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loadingParts = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (records) => {
                    this.requests = records;
                    this.partsLoaded = true;
                },
                error: () =>
                    (this.error =
                        'Não foi possível consultar as solicitações desta OS. Tente novamente.'),
            });
    }
    private dialogs = inject(MatDialog);
    /** Reutiliza a própria tela Spare Parts em modo de seleção, sem gravar ou abandonar a OS. */
    openCatalogParts() {
        if (this.busy || this.loading) return;
        this.dialogs
            .open(SpareParts, {
                width: '1180px',
                maxWidth: '96vw',
                maxHeight: '92vh',
                autoFocus: false,
                ariaLabel: 'Spare Parts para a OS ' + this.order.id,
                data: { selectForWorkOrder: this.order.id },
            })
            .afterClosed()
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe((part) => {
                if (part) {
                    this.choosePart(part);
                    this.changeDetector.markForCheck();
                }
            });
    }
    /** Seleciona uma peça, inicia quantidade/observação e leva a rolagem até o formulário de solicitação. */
    choosePart(part: WorkOrderPart) {
        this.partSelected = part;
        this.error = this.message = '';
        this.draft = {
            quantity: 1,
            note: '',
        };
        setTimeout(() =>
            this.requestForm?.nativeElement.scrollIntoView({
                block: 'nearest',
            })
        );
    }
    /** POST /api/orders/:id/part-requisitions registra a peça diretamente. Não cria compra, rascunho ou envio ao gestor. */
    createRequest() {
        if (this.busy || !this.partSelected || this.draft.quantity <= 0) return;
        this.requesting = true;
        this.dialogReference.disableClose = true;
        this.error = this.message = '';
        this.httpClient
            .post<WorkOrderPartRequisition>(
                `/api/orders/${this.order.id}/part-requisitions`,
                {
                    sparePartId: this.partSelected.id,
                    quantity: this.draft.quantity,
                    note: this.draft.note.trim(),
                }
            )
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.requesting = false;
                    this.dialogReference.disableClose = this.busy;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (requestHttp) => {
                    this.requests = [requestHttp, ...this.requests];
                    this.partSelected = null;
                    this.message = `Solicitação de peça SP-${requestHttp.id} registrada para esta OS e máquina.`;
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível criar a solicitação da peça.'),
            });
    }
    /** PATCH /api/orders/:id envia status e os três campos técnicos; o Django determina responsável, fechamento e duração. */
    save() {
        if (this.busy || this.loading || !this.canEdit) return;
        this.processing = true;
        this.dialogReference.disableClose = true;
        this.error = '';
        this.httpClient
            .patch<WorkOrder>(`/api/orders/${this.order.id}`, {
                status: this.status,
                rootCause: this.rootCause,
                correctiveAction: this.correctiveAction,
                preventiveAction: this.preventiveAction,
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.dialogReference.disableClose = this.busy;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: () => {
                    this.dialogReference.close(true);
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível salvar o atendimento.'),
            });
    }
}
