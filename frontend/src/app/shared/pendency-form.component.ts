/** Formulário reutilizável de pendência da OS, com envio HTTP e eventos de sucesso/cancelamento. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    EventEmitter,
    Input,
    Output,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { FormModal } from './form-modal.component';
import { LinePendency } from '../core/models/line-pendency.model';
@Component({
    selector: 'app-pendency-form',
    standalone: true,
    imports: [CommonModule, FormsModule, FormModal],
    template: `
        <app-form-modal
            title="Gerar pendência da linha"
            [subtitle]="
                'Registre uma ação pendente vinculada à OS #' +
                workOrderId +
                '.'
            "
            icon="pending_actions"
            [busy]="processing"
            (closed)="closed.emit()"
        >
            <p class="muted"
                >A linha, a máquina e o serial serão vinculados automaticamente
                a partir da OS.</p
            >
            <p *ngIf="errorMessage" class="error" role="alert">{{
                errorMessage
            }}</p>
            <label
                ><span>Descrição da pendência *</span
                ><textarea
                    rows="4"
                    maxlength="5000"
                    [(ngModel)]="description"
                    placeholder="Descreva o que precisa ser feito nesta linha..."
                ></textarea>
            </label>
            <label
                ><span>Prioridade</span
                ><select [(ngModel)]="priority"
                    ><option value="BAIXA">Baixa</option
                    ><option value="MEDIA">Média</option
                    ><option value="ALTA">Alta</option
                    ><option value="CRITICA">Crítica</option></select
                ></label
            >
            <div modalActions class="modal-actions"
                ><button
                    type="button"
                    [disabled]="processing"
                    (click)="closed.emit()"
                    >Cancelar</button
                ><button
                    type="button"
                    class="primary"
                    [disabled]="processing || description.trim().length < 5"
                    (click)="save()"
                    >{{
                        processing ? 'Registrando...' : 'Registrar pendência'
                    }}</button
                ></div
            >
        </app-form-modal>
    `,
})
export class PendencyForm {
    @Input({
        required: true,
    })
    workOrderId!: number;
    @Output()
    created = new EventEmitter<LinePendency>();
    @Output()
    closed = new EventEmitter<void>();
    private httpClient = inject(HttpClient);
    private changeDetector = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    description = '';
    priority = 'MEDIA';
    processing = false;
    errorMessage = '';
    /** POST /api/orders/:id/pendencies registra descrição/prioridade; o Django deriva linha, máquina, serial e autor e devolve o registro criado. */
    save() {
        if (this.processing || this.description.trim().length < 5) return;
        this.processing = true;
        this.errorMessage = '';
        this.httpClient
            .post<LinePendency>(`/api/orders/${this.workOrderId}/pendencies`, {
                description: this.description.trim(),
                priority: this.priority,
            })
            .pipe(
                takeUntilDestroyed(this.destroyRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (createdItem) => this.created.emit(createdItem),
                error: (failure) =>
                    (this.errorMessage =
                        failure.error?.error ||
                        'Não foi possível registrar a pendência.'),
            });
    }
}
