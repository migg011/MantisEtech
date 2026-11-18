/** Módulo report-dialog: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { finalize, interval } from 'rxjs';
import {WorkOrder} from '../../core/models/work-order.model';
import { Api, Auth, Equipment as EquipmentData } from '../../services';
import { ProblemType, PRIORITY_LABELS } from '../../core/models/problem-type.model';
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, MatButtonModule, MatIconModule, MatDialogModule, MatAutocompleteModule],
    templateUrl: './incident-dialog.component.html',
    styleUrl: './incident-dialog.component.scss'
})
export class ReportDialog implements OnInit {
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    private api = inject(Api);
    private authValue = inject(Auth);
    private httpValue = inject(HttpClient);
    machineValue = inject<EquipmentData>(MAT_DIALOG_DATA);
    dialogRefValue = inject(MatDialogRef<ReportDialog>);
    // O relógio exibido é uma prévia. O servidor registra o horário definitivo ao confirmar a OS.
    currentTime = new Date();
    occurrenceDescription = '';
    createdRecord: WorkOrder | null = null;
    get operatorName(){return this.authValue.userValue()?.name || 'Usuário autenticado';}
    problemsValue: ProblemType[] = [];
    problemTypeIdValue: number | null = null;
    problemQuery = '';
    priorityValue = 'MEDIA';
    priorities = PRIORITY_LABELS;
    errorValue = '';
    loadError = '';
    success = false;
    working = false;
    loadingProblems = false;
    /** Distingue o operador para exibir a prioridade definida no catálogo em vez de permitir sua alteração. */
    get isOperator() {
        return this.authValue.userValue()?.role === 'OPERADOR';
    }
    /** Carrega os problemas assim que o diálogo de abertura da OS é criado. */
    ngOnInit() {
        this.loadProblems();
        interval(1000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            if(!this.createdRecord){this.currentTime=new Date();this.cdr.markForCheck();}
        });
    }
    /** Consulta problemas ativos compatíveis com o tipo da máquina e reinicia a seleção anterior. */
    loadProblems() {
        this.loadingProblems = true;
        this.loadError = '';
        this.problemTypeIdValue = null;
        this.problemQuery = '';
        this.api.problemTypes(this.machineValue.equipment_type_id).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.loadingProblems = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: problems => this.problemsValue = problems,
            error: () => this.loadError = 'Não foi possível carregar os problemas cadastrados.'
        });
    }
    /** Copia a prioridade da opção escolhida para a abertura da OS e limpa mensagens anteriores. */
    private searchText(text: string): string {
        return text.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('pt-BR').trim();
    }

    get filteredProblems(): ProblemType[] {
        const query = this.searchText(this.problemQuery);
        return this.problemsValue.filter(problem => this.searchText(problem.name).includes(query));
    }

    searchProblems(query: string | ProblemType) {
        if (typeof query !== 'string') return;
        this.problemQuery = query;
        this.problemTypeIdValue = null;
        this.errorValue = '';
    }

    displayProblem = (value: ProblemType | string) => typeof value === 'string' ? value : value?.name || '';

    selectProblem(problem: ProblemType) {
        this.problemQuery = problem.name;
        this.problemTypeIdValue = problem.id;
        this.priorityValue = problem.priority;
        this.errorValue = '';
        this.success = false;
    }
    /** POST /api/orders: envia máquina, problema cadastrado e prioridade; o Django identifica o operador pelo token e grava a abertura. */
    save() {
        if (this.working || this.success || this.loadingProblems || !this.problemTypeIdValue || this.occurrenceDescription.trim().length > 3000)
            return;
        this.errorValue = '';
        this.success = false;
        this.dialogRefValue.disableClose = true;
        this.working = true;
        this.httpValue.post<WorkOrder>('/api/orders', {
            equipmentId: this.machineValue.id,
            problemTypeId: this.problemTypeIdValue,
            priority: this.priorityValue,
            occurrenceDescription: this.occurrenceDescription.trim()
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.working = false;
            this.dialogRefValue.disableClose = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: registro => {
                this.createdRecord = registro;
                this.success = true;
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível registrar a ocorrência.'
        });
    }
}
