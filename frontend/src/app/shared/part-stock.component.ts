/** Entrada simples de peças. Saldo e histórico são gravados juntos pelo servidor. */
import {
    Component,
    Input,
    Output,
    EventEmitter,
    OnChanges,
    OnDestroy,
    inject,
    ChangeDetectorRef,
    LOCALE_ID,
} from '@angular/core';
import { CommonModule, registerLocaleData } from '@angular/common';
import portuguese from '@angular/common/locales/pt';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Subscription, finalize } from 'rxjs';
import { Authentication } from '../services';
registerLocaleData(portuguese);
@Component({
    selector: 'app-part-stock',
    standalone: true,
    providers: [{ provide: LOCALE_ID, useValue: 'pt-BR' }],
    imports: [CommonModule, FormsModule],
    templateUrl: './part-stock.component.html',
    styleUrl: './part-stock.component.scss',
})
export class PartStock implements OnChanges, OnDestroy {
    @Input({ required: true }) partId!: number;
    @Output() busyChange = new EventEmitter<boolean>();
    private http = inject(HttpClient);
    private auth = inject(Authentication);
    private cd = inject(ChangeDetectorRef);
    private subscriptions = new Subscription();
    part: any = null;
    movements: any[] = [];
    errorMessage = '';
    message = '';
    busy = false;
    loadingHistory = false;
    historyError = '';
    kind = 'ENTRADA';
    quantity: number | null = null;
    note = '';
    requestKey = '';
    supplier = '';
    documentReference = '';
    today = this.currentDate();
    movementDate = this.today;
    private currentDate() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
    isAdministrator() {
        return this.auth.user()?.role === 'ADMINISTRADOR';
    }
    get isIncoming() {
        return this.kind === 'ENTRADA' || this.kind === 'INICIAL';
    }
    get operationTitle() {
        return (
            {
                INICIAL: 'Primeiro registro do estoque',
                ENTRADA: 'Entrada de peças',
                SAIDA: 'Saída para manutenção',
                AJUSTE: 'Ajustar quantidade contada',
            } as Record<string, string>
        )[this.kind];
    }
    get projectedBalance() {
        if (this.quantity === null || !Number.isFinite(Number(this.quantity)))
            return null;
        const amount = Number(this.quantity),
            stock = Number(this.part?.stock_quantity ?? 0);
        return this.kind === 'ENTRADA'
            ? stock + amount
            : this.kind === 'SAIDA'
              ? stock - amount
              : amount;
    }
    get canSave() {
        return (
            !!this.part &&
            this.isAdministrator() &&
            !this.busy &&
            this.quantity !== null &&
            Number.isFinite(Number(this.quantity)) &&
            this.quantity >= 0 &&
            (this.kind === 'INICIAL' ||
                this.kind === 'AJUSTE' ||
                this.quantity > 0) &&
            this.projectedBalance !== null &&
            this.projectedBalance >= 0 &&
            this.projectedBalance < 100000000000 &&
            this.movementDate.length === 10 &&
            this.movementDate <= this.today &&
            this.movementDate >= '1900-01-01' &&
            this.note.length <= 500
        );
    }
    ngOnChanges() {
        this.subscriptions.unsubscribe();
        this.subscriptions = new Subscription();
        this.part = null;
        this.movements = [];
        this.quantity = null;
        this.note =
            this.requestKey =
            this.supplier =
            this.documentReference =
            this.errorMessage =
            this.message =
                '';
        this.today = this.currentDate();
        this.movementDate = this.today;
        this.load();
    }
    load(resetOperation = true) {
        this.subscriptions.add(
            this.http
                .get<any>(`/api/spare-parts/${this.partId}/details`)
                .subscribe({
                    next: (part) => {
                        this.part = part;
                        if (resetOperation)
                            this.kind =
                                part.stock_quantity === null
                                    ? 'INICIAL'
                                    : 'ENTRADA';
                        this.cd.markForCheck();
                    },
                    error: () => {
                        this.errorMessage =
                            'Não foi possível consultar o saldo.';
                        this.cd.markForCheck();
                    },
                })
        );
        this.loadingHistory = true;
        this.historyError = '';
        this.subscriptions.add(
            this.http
                .get<any[]>(`/api/spare-parts/${this.partId}/stock-movements`)
                .subscribe({
                    next: (movements) => {
                        this.movements = movements;
                        this.loadingHistory = false;
                        this.cd.markForCheck();
                    },
                    error: () => {
                        this.historyError =
                            'Não foi possível carregar o histórico.';
                        this.loadingHistory = false;
                        this.cd.markForCheck();
                    },
                })
        );
    }
    changed() {
        this.requestKey = '';
        this.message = '';
    }
    selectKind(kind: string) {
        if (this.busy) return;
        this.kind = kind;
        this.quantity = null;
        this.note = this.supplier = this.documentReference = '';
        this.changed();
        this.errorMessage = '';
    }
    save() {
        if (!this.canSave) return;
        this.busy = true;
        this.busyChange.emit(true);
        this.errorMessage = this.message = '';
        // Reuses the key after a network error so the same receipt is not recorded twice.
        this.requestKey ||= crypto.randomUUID();
        const savedKind = this.kind;
        const payload = {
            kind: this.kind,
            quantity: this.quantity,
            movementDate: this.movementDate,
            note: this.note,
            supplier: this.isIncoming ? this.supplier : '',
            documentReference: this.isIncoming ? this.documentReference : '',
            requestKey: this.requestKey,
        };
        this.subscriptions.add(
            this.http
                .post(
                    `/api/spare-parts/${this.partId}/stock-movements`,
                    payload
                )
                .pipe(
                    finalize(() => {
                        this.busy = false;
                        this.busyChange.emit(false);
                        this.cd.markForCheck();
                    })
                )
                .subscribe({
                    next: () => {
                        this.quantity = null;
                        this.note =
                            this.requestKey =
                            this.supplier =
                            this.documentReference =
                                '';
                        this.movementDate = this.today;
                        this.message =
                            savedKind === 'ENTRADA'
                                ? 'Entrada registrada e saldo atualizado.'
                                : savedKind === 'SAIDA'
                                  ? 'Saída registrada e saldo atualizado.'
                                  : 'Contagem registrada e saldo atualizado.';
                        this.load();
                    },
                    error: (failure) => {
                        this.errorMessage =
                            failure.error?.error ||
                            'Não foi possível registrar. Você pode tentar novamente.';
                    },
                })
        );
    }
    ngOnDestroy() {
        this.subscriptions.unsubscribe();
    }
}
