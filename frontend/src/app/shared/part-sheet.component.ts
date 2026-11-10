/** Ficha única de consulta: cadastro, OS e compras exibem os mesmos dados da peça. */
import {
    Component,
    Input,
    Output,
    EventEmitter,
    OnChanges,
    OnDestroy,
    ChangeDetectorRef,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Subscription } from 'rxjs';
import { PartStock } from './part-stock.component';
import { FormModal } from './form-modal.component';

@Component({
    selector: 'app-part-sheet',
    standalone: true,
    imports: [CommonModule, PartStock],
    templateUrl: './part-sheet.component.html',
    styleUrl: './part-sheet.component.scss',
})
export class PartSheet implements OnChanges, OnDestroy {
    @Input({ required: true }) partId!: number;
    @Output() stockBusy = new EventEmitter<boolean>();
    movingStock = false;
    lockStock(value: boolean) {
        this.movingStock = value;
        this.stockBusy.emit(value);
    }
    private http = inject(HttpClient);
    private detector = inject(ChangeDetectorRef);
    private subscriptions = new Subscription();
    part: any = null;
    photoUrl = '';
    errorMessage = '';
    photoError = '';
    loading = false;
    tab = 'DADOS';
    ngOnChanges() {
        this.subscriptions.unsubscribe();
        this.subscriptions = new Subscription();
        if (this.photoUrl) URL.revokeObjectURL(this.photoUrl);
        this.part = null;
        this.photoUrl = this.errorMessage = this.photoError = '';
        this.tab = 'DADOS';
        if (!this.partId) return;
        this.loading = true;
        this.subscriptions.add(
            this.http
                .get<any>(`/api/spare-parts/${this.partId}/details`)
                .subscribe({
                    next: (part) => {
                        this.part = part;
                        this.loading = false;
                        if (part.photo_filename)
                            this.subscriptions.add(
                                this.http
                                    .get(`/api/spare-parts/${part.id}/photo`, {
                                        responseType: 'blob',
                                    })
                                    .subscribe({
                                        next: (blob) => {
                                            this.photoUrl =
                                                URL.createObjectURL(blob);
                                            this.detector.markForCheck();
                                        },
                                        error: () => {
                                            this.photoError =
                                                'Foto indisponível no momento.';
                                            this.detector.markForCheck();
                                        },
                                    })
                            );
                        this.detector.markForCheck();
                    },
                    error: () => {
                        this.loading = false;
                        this.errorMessage =
                            'Não foi possível consultar a ficha da peça.';
                        this.detector.markForCheck();
                    },
                })
        );
    }
    formatCost(value: any, currency: string) {
        if (value === null || value === undefined || value === '')
            return 'Não informado';
        const amount = Number(value);
        return currency
            ? new Intl.NumberFormat('pt-BR', {
                  style: 'currency',
                  currency: currency,
              }).format(amount)
            : amount.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) +
                  ' (moeda não informada)';
    }
    ngOnDestroy() {
        this.subscriptions.unsubscribe();
        if (this.photoUrl) URL.revokeObjectURL(this.photoUrl);
    }
}

@Component({
    selector: 'app-part-query',
    standalone: true,
    imports: [CommonModule, FormModal, PartSheet],
    template: `<button type="button" class="query-part" (click)="open = true">{{
            label
        }}</button
        ><app-form-modal
            *ngIf="open"
            title="Ficha da peça"
            subtitle="Identificação, foto e informações da peça cadastrada."
            icon="inventory_2"
            [wide]="true"
            [busy]="movingStock"
            (closed)="open = false"
            ><app-part-sheet
                [partId]="partId"
                (stockBusy)="movingStock = $event"
        /></app-form-modal>`,
    styles: [
        `
            .query-part {
                border: 0;
                background: transparent;
                color: #c8102e;
                font: inherit;
                font-weight: 600;
                text-align: left;
                padding: 6px 0;
                text-decoration: underline;
                text-underline-offset: 3px;
                cursor: pointer;
                overflow-wrap: anywhere;
            }
        `,
    ],
})
export class PartQuery {
    @Input({ required: true }) partId!: number;
    @Input() label = 'Ver ficha';
    open = false;
    movingStock = false;
}
