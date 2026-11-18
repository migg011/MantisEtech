import {RegistrationFeedback} from '../../shared/registration-feedback';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectorRef, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

interface Part {
    id: number;
    description: string;
    manufacturer: string | null;
    unit: string;
    stock_quantity: string | number | null;
}

interface ReceiptItem {
    partNumber: string;
    matches: Part[] | null;
    part: Part | null;
    description: string;
    manufacturer: string;
    unit: string;
    quantity: number | null;
    previousQuantity: number | null;
    searching: boolean;
    error: string;
}

const emptyItem = (): ReceiptItem => ({
    partNumber: '', matches: null, part: null, description: '', manufacturer: '',
    unit: 'UN', quantity: null, previousQuantity: null, searching: false, error: '',
});

@Component({
    standalone: true,
    imports: [FormsModule, RouterLink],
    templateUrl: './stock-receipt.component.html',
    styleUrl: './stock-receipt.component.scss',
})
export class StockReceipt {
    private readonly feedback = inject(RegistrationFeedback);
    private http = inject(HttpClient);
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    readonly today = new Date().toLocaleDateString('sv-SE');
    movementDate = this.today;
    sectors: {id: number; name: string; cost_center: string}[] = [];
    sectorId: number | null = null;
    ngOnInit() {
        this.http.get<typeof this.sectors>('/api/sectors').pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({next: sectors => {
                this.sectors = sectors;
                if (sectors.length === 1) this.sectorId = sectors[0].id;
                this.cdr.markForCheck();
            }, error: () => this.error.set('Não foi possível carregar os setores.')});
    }

    selectSector(id: number | null) {
        this.sectorId = id;
        this.items.forEach(item => this.resetLookup(item));
    }

    supplier = '';
    documentReference = '';
    items = [emptyItem()];
    readonly busy = signal(false);
    readonly error = signal('');
    private pending: { snapshot: string; key: string } | null = null;

    add() { if (this.items.length < 100) this.items.push(emptyItem()); }
    remove(index: number) { if (this.items.length > 1) this.items.splice(index, 1); }

    resetLookup(item: ReceiptItem) {
        item.matches = null;
        item.part = null;
        item.error = '';
    }

    lookup(item: ReceiptItem) {
        const partNumber = item.partNumber.trim();
        if (!this.sectorId || !partNumber || item.searching) return;
        this.resetLookup(item);
        item.searching = true;
        const sectorId = this.sectorId;
        this.http.get<Part[]>('/api/spare-parts', { params: { partNumber, sectorId } }).pipe(
            takeUntilDestroyed(this.destroyRef),
            finalize(() => { item.searching = false; this.cdr.markForCheck(); }),
        ).subscribe({
            next: matches => {
                if (this.sectorId !== sectorId || item.partNumber.trim() !== partNumber) return;
                item.matches = matches;
                if (matches.length === 1) item.part = matches[0];
            },
            error: () => { item.error = 'Não foi possível consultar a peça. Tente novamente.'; },
        });
    }

    save() {
        if (this.busy()) return;
        this.error.set('');
        if (!this.sectorId) {
            this.error.set('Selecione o setor de destino.');
            return;
        }
        if (!this.supplier.trim() || !this.documentReference.trim() || !this.movementDate) {
            this.error.set('Preencha o fornecedor, o número da nota e a data de recebimento.');
            return;
        }
        const incomplete = this.items.findIndex(item =>
            item.searching || item.matches === null || (item.matches.length > 0 && !item.part)
            || (!item.part && (!item.description.trim() || !item.unit.trim()))
            || item.quantity === null || item.quantity <= 0
            || (item.part?.stock_quantity === null && (item.previousQuantity === null || item.previousQuantity < 0)));
        if (incomplete !== -1) {
            this.error.set('Confira a peça, a quantidade e o saldo anterior quando solicitado no item ' + (incomplete + 1) + '.');
            return;
        }
        const payload = {
            sectorId: this.sectorId,
            supplier: this.supplier.trim(), documentReference: this.documentReference.trim(),
            movementDate: this.movementDate,
            items: this.items.map(item => item.part ? {
                partId: item.part.id, quantity: item.quantity, previousQuantity: item.previousQuantity,
            } : {
                partNumber: item.partNumber.trim(), description: item.description.trim(),
                manufacturer: item.manufacturer.trim(), unit: item.unit.trim(), quantity: item.quantity,
            }),
        };
        const snapshot = JSON.stringify(payload);
        if (this.pending?.snapshot !== snapshot) this.pending = { snapshot, key: crypto.randomUUID() };
        this.busy.set(true);
        this.http.post<{ items: unknown[] }>('/api/spare-parts/receipts', {
            ...payload, requestKey: this.pending.key,
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false))).subscribe({
            next: result => {
                const count = result.items.length;
                this.feedback.show('Entrada registrada com sucesso',
                    count === 1 ? '1 item recebido' : `${count} itens recebidos`, 'OK');
                this.pending = null;
                this.items = [emptyItem()];
                this.supplier = this.documentReference = '';
                this.movementDate = this.today;
            },
            error: response => this.error.set(response.error?.error || 'Não foi possível confirmar a entrada. Tente novamente.'),
        });
    }
}
