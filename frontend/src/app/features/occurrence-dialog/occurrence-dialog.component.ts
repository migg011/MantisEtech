/** Módulo report-dialog: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    OnInit,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import {
    MatDialogModule,
    MatDialogRef,
    MAT_DIALOG_DATA,
} from '@angular/material/dialog';
import { finalize, interval } from 'rxjs';
import { WorkOrder } from '../../core/models/work-order.model';
import {
    Api,
    Authentication,
    Equipment as EquipmentData,
} from '../../services';
import {
    ProblemType,
    PRIORITY_LABELS,
} from '../../core/models/problem-type.model';
@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatIconModule,
        MatDialogModule,
    ],
    templateUrl: './occurrence-dialog.component.html',
    styleUrl: './occurrence-dialog.component.scss',
})
export class OccurrenceDialog implements OnInit {
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    private api = inject(Api);
    private authentication = inject(Authentication);
    private httpClient = inject(HttpClient);
    machine = inject<EquipmentData>(MAT_DIALOG_DATA);
    dialogReference = inject(MatDialogRef<OccurrenceDialog>);
    // O relógio exibido é uma prévia. O servidor registra o horário definitivo ao confirmar a OS.
    timeCurrent = new Date();
    occurrenceDescription = '';
    recordCreated: WorkOrder | null = null;
    get nameOperator() {
        return this.authentication.user()?.name || 'Usuário autenticado';
    }
    problems: ProblemType[] = [];
    idTypeProblem: number | null = null;
    priority = 'MEDIA';
    priorities = PRIORITY_LABELS;
    error = '';
    errorLoading = '';
    successMessage = false;
    processing = false;
    loadingProblems = false;
    /** Distingue o operador para exibir a prioridade definida no catálogo em vez de permitir sua alteração. */
    get operator() {
        return this.authentication.user()?.role === 'OPERADOR';
    }
    /** Carrega os problemas assim que o diálogo de abertura da OS é criado. */
    ngOnInit() {
        this.loadProblems();
        interval(1000)
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                if (!this.recordCreated) {
                    this.timeCurrent = new Date();
                    this.changeDetector.markForCheck();
                }
            });
    }
    /** Consulta problemas ativos compatíveis com o tipo da máquina e reinicia a seleção anterior. */
    loadProblems() {
        this.loadingProblems = true;
        this.errorLoading = '';
        this.idTypeProblem = null;
        this.api
            .problemTypes(this.machine.equipment_type_id)
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loadingProblems = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (problems) => (this.problems = problems),
                error: () =>
                    (this.errorLoading =
                        'Não foi possível carregar os problemas cadastrados.'),
            });
    }
    /** Copia a prioridade da opção escolhida para a abertura da OS e limpa mensagens anteriores. */
    selectProblem() {
        this.priority =
            this.problems.find((problem) => problem.id === this.idTypeProblem)
                ?.priority || 'MEDIA';
        this.error = '';
        this.successMessage = false;
    }
    /** POST /api/orders: envia máquina, problema cadastrado e prioridade; o Django identifica o operador pelo token e grava a abertura. */
    save() {
        if (
            this.processing ||
            this.successMessage ||
            this.loadingProblems ||
            !this.idTypeProblem ||
            this.occurrenceDescription.trim().length > 3000
        )
            return;
        this.error = '';
        this.successMessage = false;
        this.dialogReference.disableClose = true;
        this.processing = true;
        this.httpClient
            .post<WorkOrder>('/api/orders', {
                equipmentId: this.machine.id,
                problemTypeId: this.idTypeProblem,
                priority: this.priority,
                occurrenceDescription: this.occurrenceDescription.trim(),
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.dialogReference.disableClose = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (record) => {
                    this.recordCreated = record;
                    this.successMessage = true;
                },
                error: (failure) =>
                    (this.error =
                        failure.error?.error ||
                        'Não foi possível registrar a ocorrência.'),
            });
    }
}
