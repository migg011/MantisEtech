/** Ficha de consulta da preventiva. Reutiliza as APIs existentes sem cadastrar compatibilidade entre peça e máquina. */
import { ChangeDetectorRef, Component, DestroyRef, Input, OnChanges, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize, Subscription } from 'rxjs';
import { Equipment } from '../../core/models/equipment.model';
import {PartLookup} from '../../shared/part-sheet.component';

interface CatalogPart { id:number; code:string; part_number:string|null; description:string; manufacturer:string|null; category:string|null; unit:string; }
interface PurchaseLine { part:CatalogPart; quantity:number; note:string; }
import { EquipmentAttachment, EquipmentDocuments } from '../../shared/equipment-documents.component';
interface HistoryEntry {
    key: string;
    number: string | null;
    type: 'CORRETIVA' | 'PREVENTIVA';
    finishedAt: string | null;
    performedDate?: string | null;
    reason: string;
    services: string[];
    requestedParts?: { id: number; partNumber: string | null; description: string; quantity: string }[];
}

interface Movement { id:number; created_at:string; from_line:string|null; to_line:string|null; performed_by_name:string; }

@Component({
    selector:'app-ficha-equipamento', standalone:true, imports:[PartLookup, EquipmentDocuments, CommonModule, FormsModule, RouterLink, MatIconModule],
    templateUrl:'./equipment-sheet.component.html', styleUrl:'./equipment-sheet.component.scss'
})
export class EquipmentSheet implements OnChanges, OnDestroy {
    @Input({required:true}) equipmentValue!:Equipment;
    @Input() tab = 'GERAIS';
    private httpValue = inject(HttpClient);
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    private equipmentRequests = new Subscription();
    private equipmentLoaded = 0;
    stockMovements:Movement[] = [];
    history: HistoryEntry[] = [];
    historyType = '';
    historyError = '';
    loadingHistory = false;

    get filteredHistory() {
        return this.historyType ? this.history.filter(entry => entry.type === this.historyType) : this.history;
    }
    photoAddress = '';
    movementsError = '';
    photoError = '';
    loadingPhoto = false;
    loadingMovements = false;
    partsValue:CatalogPart[] = [];
    managers:{id:number;name:string}[] = [];
    catalogLoaded = false;
    loadingCatalog = false;
    managersLoaded = false;
    catalogError = '';
    purchaseError = '';
    search = '';
    linesValue:PurchaseLine[] = [];
    managerId = 0;
    justification = '';
    priorityValue = 'MEDIA';
    purchaseType = 'NACIONAL';
    saving = false;
    createdId:number|null = null;

    /** Trocar de máquina cancela consultas antigas. A lista de compra permanece geral durante a navegação na tela. */
    ngOnChanges() {
        if (this.equipmentLoaded !== this.equipmentValue.id) {
            this.equipmentLoaded = this.equipmentValue.id;
            this.equipmentRequests.unsubscribe(); this.equipmentRequests = new Subscription();
            this.releasePhoto(); this.stockMovements = [];
            this.movementsError = this.photoError = '';
            this.loadingPhoto = this.loadingMovements = true;
            const base = `/api/equipment/${this.equipmentValue.id}`;
            this.equipmentRequests.add(this.httpValue.get<EquipmentAttachment[]>(`${base}/attachments`).subscribe({
                next: filesValue => {
                    if (filesValue.some(file => file.kind === 'PHOTO')) this.loadPhoto(base);
                    else this.loadingPhoto = false;
                    this.cdr.markForCheck();
                },
                error: () => { this.loadingPhoto = false; this.photoError = 'Não foi possível consultar a foto.'; this.cdr.markForCheck(); }
            }));
            this.equipmentRequests.add(this.httpValue.get<Movement[]>(`${base}/movements`).subscribe({
                next: rows => { this.stockMovements = rows; this.loadingMovements = false; this.cdr.markForCheck(); },
                error: () => { this.loadingMovements = false; this.movementsError = 'Não foi possível carregar as movimentações.'; this.cdr.markForCheck(); }
            }));
        }
        if (this.tab === 'HISTORICO') this.loadHistory();
        if (this.tab === 'PECAS' && !this.catalogLoaded && !this.loadingCatalog) this.loadCatalog();
    }

    loadHistory() {
        this.history = [];
        this.loadingHistory = true;
        this.historyError = '';
        this.equipmentRequests.add(this.httpValue.get<HistoryEntry[]>('/api/equipment/' + this.equipmentValue.id + '/history').pipe(
            finalize(() => { this.loadingHistory = false; this.cdr.markForCheck(); }),
        ).subscribe({
            next: entries => { this.history = entries; },
            error: () => { this.historyError = 'Não foi possível carregar o histórico de OS.'; },
        }));
    }

    /** A foto usa Blob porque o download exige o cabeçalho de autenticação enviado pelo interceptor HTTP. */
    private loadPhoto(base:string) {
        this.equipmentRequests.add(this.httpValue.get(`${base}/attachments/PHOTO/download`, {responseType:'blob'}).subscribe({
            next: blobValue => { this.loadingPhoto = false; this.photoAddress = URL.createObjectURL(blobValue); this.cdr.markForCheck(); },
            error: () => { this.loadingPhoto = false; this.photoError = 'Não foi possível carregar a foto.'; this.cdr.markForCheck(); }
        }));
    }
    /** URLs de Blob ocupam memória até serem liberadas; uma troca de máquina descarta a foto anterior. */
    private releasePhoto() { if (this.photoAddress) URL.revokeObjectURL(this.photoAddress); this.photoAddress = ''; }
    /** Encerra consultas e libera a imagem quando o usuário sai do módulo de preventivas. */
    ngOnDestroy() { this.equipmentRequests.unsubscribe(); this.releasePhoto(); }

    /** Consulta todo o catálogo disponível para compras: não envia equipmentId nem usa compatibilidade como filtro. */
    loadCatalog() {
        this.loadingCatalog = true; this.catalogError = '';
        this.httpValue.get<CatalogPart[]>('/api/spare-purchase/parts').pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.loadingCatalog = false; this.cdr.markForCheck();})).subscribe({
            next: rows => { this.partsValue = rows; this.catalogLoaded = true; },
            error: () => this.catalogError = 'Falha ao carregar o catálogo. Tente novamente.'
        });
        this.httpValue.get<{id:number;name:string}[]>('/api/spare-purchase/managers').pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.cdr.markForCheck())).subscribe({
            next: rows => { this.managers = rows; this.managersLoaded = true; },
            error: () => { this.managersLoaded = false; this.purchaseError = 'Falha ao carregar gestores. Use Atualizar catálogo para tentar novamente.'; }
        });
    }
    /** Pesquisa local por identificação e fabricante. Limita apenas a apresentação, mantendo o total de resultados visível. */
    get searchResults() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.partsValue.filter(partValue => `${partValue.code} ${partValue.part_number || ''} ${partValue.description} ${partValue.manufacturer || ''} ${partValue.category || ''}`.toLocaleLowerCase('pt-BR').includes(term));
    }
    /** Impede linhas duplicadas: para pedir mais unidades, altere a quantidade do item já selecionado. */
    hasPart(id:number) { return this.linesValue.some(lineValue => lineValue.part.id === id); }
    /** Adiciona somente à lista local; nenhuma compra existe no banco até o usuário gerar a solicitação. */
    adicionar(partValue:CatalogPart) {
        if (this.saving || this.hasPart(partValue.id) || this.linesValue.length >= 100) return;
        this.linesValue.push({part: partValue, quantity:1, note:''});
    }
    /** Repete os limites principais do formulário Django; a validação definitiva permanece no servidor. */
    get validPurchase() {
        return this.managersLoaded && !!this.managerId && this.justification.trim().length >= 10 && this.linesValue.length > 0 && this.linesValue.length <= 100 &&
            this.linesValue.every(lineValue => Number.isFinite(lineValue.quantity) && lineValue.quantity > 0 && lineValue.quantity <= 100000 && Math.abs(lineValue.quantity * 1000 - Math.round(lineValue.quantity * 1000)) < 0.00001);
    }

    /** Grava todas as peças num único rascunho. Não envia máquina/OS nem altera estoque; envio e aprovação continuam no módulo Compras. */
    createPurchase() {
        if (!this.validPurchase || this.saving) return;
        this.saving = true; this.purchaseError = ''; this.createdId = null;
        this.httpValue.post<{id:number}>('/api/spare-purchase/requests', {
            purchaseType:this.purchaseType, managerId:this.managerId, priority:this.priorityValue, justification:this.justification.trim(),
            items:this.linesValue.map(lineValue => ({sparePartId:lineValue.part.id, quantity:lineValue.quantity, itemNote:lineValue.note.trim()}))
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {this.saving = false; this.cdr.markForCheck();})).subscribe({
            next: resultValue => { this.createdId = resultValue.id; this.linesValue = []; this.justification = ''; },
            error: failure => this.purchaseError = failure.error?.error || 'Não foi possível criar a compra. Sua lista foi preservada.'
        });
    }
}
