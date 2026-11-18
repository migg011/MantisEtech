/** Formulário reutilizável de pendência da OS, com envio HTTP e eventos de sucesso/cancelamento. */
import { ChangeDetectorRef, Component, DestroyRef, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { FormModal } from './form-modal.component';
import { LinePendency } from '../core/models/line-issue.model';
@Component({
    selector: 'app-formulario-pendencia', standalone: true, imports: [CommonModule, FormsModule, FormModal],
    template: `
        <app-modal-formulario titulo="Gerar pendência da linha" [subtitle]="'Registre uma ação pendente vinculada à OS #' + orderId + '.'" icone="pending_actions" [busy]="working" (closedValue)="closedValue.emit()">
            <p class="muted">A linha, a máquina e o serial serão vinculados automaticamente a partir da OS.</p>
            <p *ngIf="errorValue" class="error" role="alert">{{errorValue}}</p>
            <label><span>Descrição da pendência *</span><textarea rows="4" maxlength="5000" [(ngModel)]="descriptionValue" placeholder="Descreva o que precisa ser feito nesta linha..."></textarea></label>
            <label><span>Prioridade</span><select [(ngModel)]="priorityValue"><option value="BAIXA">Baixa</option><option value="MEDIA">Média</option><option value="ALTA">Alta</option><option value="CRITICA">Crítica</option></select></label>
            <div modalActions class="modal-actions"><button type="button" [disabled]="working" (click)="closedValue.emit()">Cancelar</button><button type="button" class="primary" [disabled]="working || descriptionValue.trim().length < 5" (click)="save()">{{working ? 'Registrando...' : 'Registrar pendência'}}</button></div>
        </app-modal-formulario>
    `
})
export class PendingForm {
    @Input({
        required: true
    })
    orderId!: number;
    @Output()
    created = new EventEmitter<LinePendency>();
    @Output()
    closedValue = new EventEmitter<void>();
    private httpValue = inject(HttpClient);
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    descriptionValue = '';
    priorityValue = 'MEDIA';
    working = false;
    errorValue = '';
    /** Envia a descrição e a prioridade da pendência. O servidor completa os dados da ordem. */
    save() {
        if (this.working || this.descriptionValue.trim().length < 5)
            return;
        this.working = true;
        this.errorValue = '';
        this.httpValue.post<LinePendency>(`/api/orders/${this.orderId}/pendencies`, {
            description: this.descriptionValue.trim(), priority: this.priorityValue
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.working = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: item => this.created.emit(item), error: failure => this.errorValue = failure.error?.error || 'Não foi possível registrar a pendência.'
        });
    }
}
