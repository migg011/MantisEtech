/** Ficha de consulta da preventiva. Reutiliza as APIs existentes sem cadastrar compatibilidade entre peça e máquina. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    Input,
    OnChanges,
    OnDestroy,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize, Subscription } from 'rxjs';
import { Equipment } from '../../core/models/equipment.model';
import { PartQuery } from '../../shared/part-sheet.component';

interface CatalogPart {
    id: number;
    code: string;
    part_number: string | null;
    description: string;
    manufacturer: string | null;
    category: string | null;
    unit: string;
}
interface PurchaseItem {
    part: CatalogPart;
    quantity: number;
    note: string;
}
interface Attachment {
    kind: 'PHOTO' | 'MANUAL';
    filename: string;
}
interface StockMovement {
    id: number;
    created_at: string;
    from_line: string | null;
    to_line: string | null;
    performed_by_name: string;
}

@Component({
    selector: 'app-ficha-equipamento',
    standalone: true,
    imports: [PartQuery, CommonModule, FormsModule, RouterLink, MatIconModule],
    templateUrl: './equipment-sheet.component.html',
    styleUrl: './equipment-sheet.component.scss',
})
export class EquipmentSheet implements OnChanges, OnDestroy {
    @Input({ required: true }) equipment!: Equipment;
    @Input() tab = 'GERAIS';
    private httpClient = inject(HttpClient);
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    private requisitionsEquipment = new Subscription();
    private equipmentLoaded = 0;
    files: Attachment[] = [];
    movements: StockMovement[] = [];
    addressPhoto = '';
    errorFiles = '';
    errorMovements = '';
    errorPhoto = '';
    loadingFiles = false;
    loadingMovements = false;
    parts: CatalogPart[] = [];
    managers: { id: number; name: string }[] = [];
    catalogLoaded = false;
    loadingCatalog = false;
    managersLoaded = false;
    errorCatalog = '';
    errorPurchase = '';
    search = '';
    lines: PurchaseItem[] = [];
    managerId = 0;
    justification = '';
    priority = 'MEDIA';
    typePurchase = 'NACIONAL';
    saving = false;
    idCreated: number | null = null;

    /** Trocar de máquina cancela consultas antigas. A lista de compra permanece geral durante a navegação na tela. */
    ngOnChanges() {
        if (this.equipmentLoaded !== this.equipment.id) {
            this.equipmentLoaded = this.equipment.id;
            this.requisitionsEquipment.unsubscribe();
            this.requisitionsEquipment = new Subscription();
            this.releasePhoto();
            this.files = [];
            this.movements = [];
            this.errorFiles = this.errorMovements = this.errorPhoto = '';
            this.loadingFiles = this.loadingMovements = true;
            const base = `/api/equipment/${this.equipment.id}`;
            this.requisitionsEquipment.add(
                this.httpClient
                    .get<Attachment[]>(`${base}/attachments`)
                    .subscribe({
                        next: (files) => {
                            this.files = files;
                            this.loadingFiles = false;
                            if (files.some((file) => file.kind === 'PHOTO'))
                                this.loadPhoto(base);
                            this.changeDetector.markForCheck();
                        },
                        error: () => {
                            this.loadingFiles = false;
                            this.errorFiles =
                                'Não foi possível carregar os documentos.';
                            this.changeDetector.markForCheck();
                        },
                    })
            );
            this.requisitionsEquipment.add(
                this.httpClient
                    .get<StockMovement[]>(`${base}/movements`)
                    .subscribe({
                        next: (rows) => {
                            this.movements = rows;
                            this.loadingMovements = false;
                            this.changeDetector.markForCheck();
                        },
                        error: () => {
                            this.loadingMovements = false;
                            this.errorMovements =
                                'Não foi possível carregar as movimentações.';
                            this.changeDetector.markForCheck();
                        },
                    })
            );
        }
        if (this.tab === 'PECAS' && !this.catalogLoaded && !this.loadingCatalog)
            this.loadCatalog();
    }

    /** A foto usa Blob porque o download exige o cabeçalho de autenticação enviado pelo interceptor HTTP. */
    private loadPhoto(base: string) {
        this.requisitionsEquipment.add(
            this.httpClient
                .get(`${base}/attachments/PHOTO/download`, {
                    responseType: 'blob',
                })
                .subscribe({
                    next: (contentFile) => {
                        this.addressPhoto = URL.createObjectURL(contentFile);
                        this.changeDetector.markForCheck();
                    },
                    error: () => {
                        this.errorPhoto = 'Não foi possível carregar a foto.';
                        this.changeDetector.markForCheck();
                    },
                })
        );
    }
    /** URLs de Blob ocupam memória até serem liberadas; uma troca de máquina descarta a foto anterior. */
    private releasePhoto() {
        if (this.addressPhoto) URL.revokeObjectURL(this.addressPhoto);
        this.addressPhoto = '';
    }
    /** Encerra consultas e libera a imagem quando o usuário sai do módulo de preventivas. */
    ngOnDestroy() {
        this.requisitionsEquipment.unsubscribe();
        this.releasePhoto();
    }

    /** Consulta todo o catálogo disponível para compras: não envia equipmentId nem usa compatibilidade como filtro. */
    loadCatalog() {
        this.loadingCatalog = true;
        this.errorCatalog = '';
        this.httpClient
            .get<CatalogPart[]>('/api/spare-purchase/parts')
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loadingCatalog = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (rows) => {
                    this.parts = rows;
                    this.catalogLoaded = true;
                },
                error: () =>
                    (this.errorCatalog =
                        'Falha ao carregar o catálogo. Tente novamente.'),
            });
        this.httpClient
            .get<{ id: number; name: string }[]>('/api/spare-purchase/managers')
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => this.changeDetector.markForCheck())
            )
            .subscribe({
                next: (rows) => {
                    this.managers = rows;
                    this.managersLoaded = true;
                },
                error: () => {
                    this.managersLoaded = false;
                    this.errorPurchase =
                        'Falha ao carregar gestores. Use Atualizar catálogo para tentar novamente.';
                },
            });
    }
    /** Pesquisa local por identificação e fabricante. Limita apenas a apresentação, mantendo o total de resultados visível. */
    get resultsSearch() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.parts.filter((part) =>
            `${part.code} ${part.part_number || ''} ${part.description} ${part.manufacturer || ''} ${part.category || ''}`
                .toLocaleLowerCase('pt-BR')
                .includes(term)
        );
    }
    /** Impede linhas duplicadas: para pedir mais unidades, altere a quantidade do item já selecionado. */
    hasPart(id: number) {
        return this.lines.some((line) => line.part.id === id);
    }
    /** Adiciona somente à lista local; nenhuma compra existe no banco até o usuário gerar a solicitação. */
    add(part: CatalogPart) {
        if (this.saving || this.hasPart(part.id) || this.lines.length >= 100)
            return;
        this.lines.push({ part: part, quantity: 1, note: '' });
    }
    /** Repete os limites principais do formulário Django; a validação definitiva permanece no servidor. */
    get purchaseValid() {
        return (
            this.managersLoaded &&
            !!this.managerId &&
            this.justification.trim().length >= 10 &&
            this.lines.length > 0 &&
            this.lines.length <= 100 &&
            this.lines.every(
                (line) =>
                    Number.isFinite(line.quantity) &&
                    line.quantity > 0 &&
                    line.quantity <= 100000 &&
                    Math.abs(
                        line.quantity * 1000 - Math.round(line.quantity * 1000)
                    ) < 0.00001
            )
        );
    }

    /** Grava todas as peças num único rascunho. Não envia máquina/OS nem altera estoque; envio e aprovação continuam no módulo Compras. */
    createPurchase() {
        if (!this.purchaseValid || this.saving) return;
        this.saving = true;
        this.errorPurchase = '';
        this.idCreated = null;
        this.httpClient
            .post<{ id: number }>('/api/spare-purchase/requests', {
                purchaseType: this.typePurchase,
                managerId: this.managerId,
                priority: this.priority,
                justification: this.justification.trim(),
                items: this.lines.map((line) => ({
                    sparePartId: line.part.id,
                    quantity: line.quantity,
                    itemNote: line.note.trim(),
                })),
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.saving = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (result) => {
                    this.idCreated = result.id;
                    this.lines = [];
                    this.justification = '';
                },
                error: (failure) =>
                    (this.errorPurchase =
                        failure.error?.error ||
                        'Não foi possível criar a compra. Sua lista foi preservada.'),
            });
    }
    /** Downloads usam o mesmo endpoint autenticado da tela de cadastro e liberam a URL temporária após o uso. */
    download(file: Attachment) {
        this.errorFiles = '';
        this.requisitionsEquipment.add(
            this.httpClient
                .get(
                    `/api/equipment/${this.equipment.id}/attachments/${file.kind}/download`,
                    { responseType: 'blob' }
                )
                .subscribe({
                    next: (contentFile) => {
                        const address = URL.createObjectURL(contentFile);
                        const link = document.createElement('a');
                        link.href = address;
                        link.download = file.filename;
                        link.click();
                        setTimeout(() => URL.revokeObjectURL(address), 60000);
                    },
                    error: () => {
                        this.errorFiles =
                            'Falha ao baixar o documento. Tente novamente.';
                        this.changeDetector.markForCheck();
                    },
                })
        );
    }
}
