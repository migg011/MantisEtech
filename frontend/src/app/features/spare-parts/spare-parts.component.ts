import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
/** Módulo spare-parts: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { PartStock } from '../../shared/part-stock.component';
import { FormModal } from '../../shared/form-modal.component';
import { CommonModule } from '@angular/common';
import {
    Component,
    ChangeDetectorRef,
    DestroyRef,
    inject,
    OnInit,
    OnDestroy,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom, Subscription } from 'rxjs';
import { PartQuery } from '../../shared/part-sheet.component';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { Authentication } from '../../services';

interface SparePart {
    stock_quantity: number | null;
    stock_status: string;
    photo_filename?: string | null;
    id: number;
    code: string;
    description: string;
    part_number: string | null;
    manufacturer: string | null;
    category: string | null;
    category_ids: number[];
    categories: { id: number; name: string; active: boolean }[];
    unit: string;
    minimum_stock: number;
    maximum_stock: number | null;
    reorder_point: number;
    storage_location: string | null;
    preferred_supplier: string | null;
    average_cost: number | null;
    last_cost: number | null;
    average_cost_currency: '' | 'BRL' | 'USD' | 'EUR';
    last_cost_currency: '' | 'BRL' | 'USD' | 'EUR';
    equipment_ids: number[];
}

@Component({
    standalone: true,
    imports: [
        PartStock,
        PartQuery,
        FormModal,
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule,
        MatMenuModule,
    ],
    templateUrl: './spare-parts.component.html',
    styleUrl: './spare-parts.component.scss',
})
/** Cadastro de peças com saldo movimentado em uma operação separada e auditável. */
export class SpareParts implements OnInit, OnDestroy {
    // A mesma tela funciona como cadastro normal ou como catálogo chamado por uma OS.
    readonly contextSelection = inject<{ selectForWorkOrder?: number }>(
        MAT_DIALOG_DATA,
        { optional: true }
    );
    private catalogDialog = inject(MatDialogRef<SpareParts>, {
        optional: true,
    });
    get selectingForWorkOrder() {
        return !!this.contextSelection?.selectForWorkOrder;
    }
    closeCatalog() {
        this.catalogDialog?.close();
    }
    selectForWorkOrder(part: SparePart) {
        if (this.selectingForWorkOrder) this.catalogDialog?.close(part);
    }

    private destroyRef = inject(DestroyRef);
    private queryPhoto = 0;
    photoSelected: File | null = null;
    photoPreview: string | null = null;
    namePhotoSaved = '';
    loadingPhoto = false;
    errorPhoto = '';
    photoViewed: SparePart | null = null;
    /** O arquivo original fica no banco; a URL Blob existe somente durante a visualização. */
    private clearPhoto() {
        ++this.queryPhoto;
        if (this.photoPreview) URL.revokeObjectURL(this.photoPreview);
        this.photoPreview = null;
        this.photoSelected = null;
        this.namePhotoSaved = this.errorPhoto = '';
        this.loadingPhoto = false;
    }
    private loadPhoto(part: SparePart) {
        this.clearPhoto();
        this.namePhotoSaved = part.photo_filename || '';
        if (!part.photo_filename) return;
        const query = this.queryPhoto;
        this.loadingPhoto = true;
        this.httpClient
            .get(`/api/spare-parts/${part.id}/photo`, { responseType: 'blob' })
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (file) => {
                    if (query !== this.queryPhoto) return;
                    this.photoPreview = URL.createObjectURL(file);
                    this.loadingPhoto = false;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    if (query !== this.queryPhoto) return;
                    this.errorPhoto =
                        'Não foi possível carregar a foto salva. Ela será mantida ao salvar sem escolher outra.';
                    this.loadingPhoto = false;
                    this.changeDetector.markForCheck();
                },
            });
    }
    selectPhoto(event: Event) {
        const field = event.target as HTMLInputElement;
        const file = field.files?.[0];
        if (!file) return;
        if (
            !['image/png', 'image/jpeg'].includes(file.type) ||
            !file.size ||
            file.size > 3 * 1024 * 1024
        ) {
            field.value = '';
            this.errorPhoto = 'Selecione uma foto JPG ou PNG de até 3 MB.';
            return;
        }
        ++this.queryPhoto;
        if (this.photoPreview) URL.revokeObjectURL(this.photoPreview);
        this.photoSelected = file;
        this.photoPreview = URL.createObjectURL(file);
        this.errorPhoto = '';
        this.loadingPhoto = false;
    }
    viewPhoto(part: SparePart) {
        this.photoViewed = part;
        this.loadPhoto(part);
    }
    closePhoto() {
        this.photoViewed = null;
        this.clearPhoto();
    }
    ngOnDestroy() {
        this.clearPhoto();
        this.queryCatalog?.unsubscribe();
    }
    partStock: SparePart | null = null;
    movingStock = false;
    inventory: any = null;
    loadingInventory = false;
    errorInventory = '';
    downloadingInventory = false;
    // O relatório consulta o catálogo completo; o filtro atual é enviado explicitamente.
    openInventory() {
        this.inventory = null;
        this.errorInventory = '';
        this.loadingInventory = true;
        this.httpClient
            .get('/api/spare-parts/inventory', {
                params: {
                    q: this.search.trim(),
                    categoryId: this.categoryFilter,
                },
            })
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (r) => {
                    this.inventory = r;
                    this.loadingInventory = false;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    this.errorInventory =
                        'Não foi possível carregar o inventário.';
                    this.loadingInventory = false;
                    this.changeDetector.markForCheck();
                },
            });
    }
    downloadInventory() {
        if (this.downloadingInventory) return;
        this.downloadingInventory = true;
        const term = this.inventory?.query ?? this.search.trim();
        this.httpClient
            .get('/api/spare-parts/inventory.csv', {
                params: {
                    q: term,
                    categoryId: this.inventory?.category_id || '',
                },
                responseType: 'blob',
            })
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (blob) => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'INVENTARIO_PECAS.csv';
                    a.click();
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                    this.downloadingInventory = false;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    this.errorInventory = 'Falha ao baixar o CSV.';
                    this.downloadingInventory = false;
                    this.changeDetector.markForCheck();
                },
            });
    }
    printInventory() {
        if (!this.inventory) return;
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            this.errorInventory =
                'Permita abrir a janela de impressão neste navegador.';
            return;
        }
        // Criação por textContent impede que descrições sejam interpretadas como HTML.
        const doc = printWindow.document;
        doc.title = 'Inventário de peças MANTIS';
        const style = doc.createElement('style');
        style.textContent =
            'body{font:12px Arial;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:7px;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}button{padding:10px;margin:12px 0}@media print{button{display:none}}';
        doc.head.append(style);
        const title = doc.createElement('h1');
        title.textContent = 'Inventário de peças MANTIS';
        doc.body.append(title);
        const note = doc.createElement('p');
        note.textContent =
            'Gerado em ' +
            new Date(this.inventory.generated_at).toLocaleString('pt-BR') +
            ' · Filtro: ' +
            (this.inventory.query || 'Todos os itens ativos') +
            ' · Categoria: ' +
            (this.inventory.category_name || 'Todas') +
            ' · ' +
            this.inventory.uninitialized_items +
            ' item(ns) sem contagem inicial.';
        doc.body.append(note);
        const warning = doc.createElement('p');
        warning.textContent =
            'Saldo registrado em estoque, sem reservas ou baixas automáticas por OS. Quantidades de unidades diferentes não são somadas.';
        doc.body.append(warning);
        const button = doc.createElement('button');
        button.textContent = 'Imprimir / Salvar PDF';
        button.onclick = () => printWindow.print();
        doc.body.append(button);
        const table = doc.createElement('table'),
            header = table.createTHead().insertRow();
        [
            'Part Number',
            'Descrição',
            'Fabricante',
            'Localização',
            'Unidade',
            'Saldo disponível',
            'Situação',
            'Categorias',
        ].forEach((t) => {
            const th = doc.createElement('th');
            th.textContent = t;
            header.append(th);
        });
        const body = table.createTBody();
        for (const p of this.inventory.items) {
            const tr = body.insertRow();
            [
                p.part_number || '—',
                p.description,
                p.manufacturer || '—',
                p.storage_location || '—',
                p.unit,
                p.stock_quantity === null
                    ? 'Não informado'
                    : Number(p.stock_quantity).toLocaleString('pt-BR', {
                          maximumFractionDigits: 3,
                      }),
                p.stock_status,
                (p.categories || []).join(', '),
            ].forEach((v) => {
                tr.insertCell().textContent = String(v);
            });
        }
        doc.body.append(table);
    }
    closeStock() {
        this.partStock = null;
        this.loadData();
    }
    categoryFilter = '';
    categories: {
        id: number;
        name: string;
        description: string;
        active: boolean;
        part_count: number;
    }[] = [];
    errorCategory = '';
    /** O cadastro central evita grafias diferentes para a mesma classificação. */
    loadCategories() {
        this.httpClient
            .get<typeof this.categories>('/api/part-categories', {
                params: { includeInactive: 'true' },
            })
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: (r) => {
                    this.categories = r;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    this.errorCategory =
                        'Não foi possível carregar as categorias.';
                    this.changeDetector.markForCheck();
                },
            });
    }
    get categoriesAvailable() {
        return this.categories.filter(
            (c) => c.active && !this.form.categoryIds.includes(c.id)
        );
    }
    get categoriesSelected() {
        return this.categories.filter((c) =>
            this.form.categoryIds.includes(c.id)
        );
    }
    /** A lista suspensa adiciona uma categoria por vez, sem duplicar nem apagar classificações existentes. */
    addCategory(event: Event) {
        const field = event.target as HTMLSelectElement;
        const id = Number(field.value);
        if (!this.saving && this.categoriesAvailable.some((c) => c.id === id))
            this.form.categoryIds = [...this.form.categoryIds, id];
        field.value = '';
    }
    removeCategory(id: number) {
        if (!this.saving)
            this.form.categoryIds = this.form.categoryIds.filter(
                (c) => c !== id
            );
    }
    search = '';
    private queryCatalog?: Subscription;
    private httpClient = inject(HttpClient);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    private authentication = inject(Authentication);
    parts: SparePart[] = [];
    formOpen = false;

    /** Limpa a peça em edição e abre o cadastro de uma nova peça. */
    newPart() {
        this.cancel();
        this.successMessage = '';
        this.formOpen = true;
    }

    editingId: number | null = null;
    saving = false;
    error = '';
    successMessage = '';
    form = this.formInitial();

    /** Cria os valores iniciais de estoque de referência, custos e compatibilidade. */
    private formInitial() {
        return {
            description: '',
            partNumber: '',
            manufacturer: '',
            categoryIds: [] as number[],
            unit: 'UN',
            minimumStock: 0,
            maximumStock: null as number | null,
            reorderPoint: 0,
            storageLocation: '',
            preferredSupplier: '',
            averageCost: null as number | null,
            lastCost: null as number | null,
            averageCostCurrency: 'BRL' as '' | 'BRL' | 'USD' | 'EUR',
            lastCostCurrency: 'BRL' as '' | 'BRL' | 'USD' | 'EUR',
            equipmentIds: [] as number[],
        };
    }

    /** Consulta o perfil local para mostrar ações exclusivas de administrador. */
    administrator() {
        return this.authentication.user()?.role === 'ADMINISTRADOR';
    }

    /** Carrega peças e equipamentos necessários ao cadastro de compatibilidade. */
    ngOnInit() {
        this.loadData();
        this.loadCategories();
    }

    /** GET /api/spare-parts recarrega o catálogo de peças ativas. */
    loadData() {
        this.queryCatalog?.unsubscribe();
        this.queryCatalog = this.httpClient
            .get<
                SparePart[]
            >('/api/spare-parts', { params: { q: this.search.trim(), categoryId: this.categoryFilter } })
            .subscribe({
                next: (x) => {
                    this.parts = x;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    this.error = 'Não foi possível carregar as peças.';
                    this.changeDetector.markForCheck();
                },
            });
    }

    /** Converte os dados retornados para os campos do formulário da peça escolhida. */
    edit(p: SparePart) {
        if (!this.administrator()) return;
        this.formOpen = true;
        this.editingId = p.id;
        this.loadPhoto(p);
        this.form = {
            description: p.description,
            partNumber: p.part_number || '',
            manufacturer: p.manufacturer || '',
            categoryIds: [...(p.category_ids || [])],
            unit: p.unit,
            minimumStock: Number(p.minimum_stock),
            maximumStock:
                p.maximum_stock === null ? null : Number(p.maximum_stock),
            reorderPoint: Number(p.reorder_point),
            storageLocation: p.storage_location || '',
            preferredSupplier: p.preferred_supplier || '',
            averageCost:
                p.average_cost === null ? null : Number(p.average_cost),
            lastCost: p.last_cost === null ? null : Number(p.last_cost),
            equipmentIds: p.equipment_ids.map(Number),
            averageCostCurrency: p.average_cost_currency || '',
            lastCostCurrency: p.last_cost_currency || '',
        };
        this.error = '';
        this.successMessage = '';
    }

    /** Descarta os campos locais e fecha o modal. */
    cancel() {
        this.clearPhoto();
        this.formOpen = false;
        this.editingId = null;
        this.form = this.formInitial();
        this.error = '';
    }

    /** POST ou PATCH grava o cadastro mestre e seus vínculos de compatibilidade; não movimenta saldo de estoque. */
    async save() {
        if (
            !this.administrator() ||
            this.saving ||
            !this.form.description.trim()
        )
            return;
        this.saving = true;
        this.error = '';
        this.successMessage = '';
        if (
            (this.form.averageCost !== null &&
                !this.form.averageCostCurrency) ||
            (this.form.lastCost !== null && !this.form.lastCostCurrency)
        ) {
            this.error = 'Selecione R$ ou US$ para cada custo preenchido.';
            this.saving = false;
            return;
        }
        try {
            const idPart = this.editingId;
            const data: any = { ...this.form };
            const photo = this.photoSelected;
            if (photo) {
                const base64 = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () =>
                        resolve(String(reader.result).split(',')[1]);
                    reader.onerror = () =>
                        reject(new Error('Não foi possível ler a foto.'));
                    reader.readAsDataURL(photo);
                });
                data.photo = {
                    filename: photo.name,
                    mimeType: photo.type,
                    base64,
                };
            }
            await firstValueFrom(
                idPart
                    ? this.httpClient.patch('/api/spare-parts/' + idPart, data)
                    : this.httpClient.post('/api/spare-parts', data)
            );
            this.cancel();
            this.successMessage = 'Peça salva com sucesso.';
            this.loadCategories();
            this.loadData();
        } catch (e: any) {
            this.error = e.error?.error || e.message || 'Falha ao salvar peça.';
        } finally {
            this.saving = false;
            this.changeDetector.markForCheck();
        }
    }

    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE desativa a peça preservando os históricos de solicitações. */
    deactivate(p: SparePart) {
        if (!this.administrator() || !confirm('Desativar esta peça?')) return;
        this.httpClient.delete('/api/spare-parts/' + p.id).subscribe({
            next: () => this.loadData(),
            error: (e) => {
                this.error = e.error?.error || 'Falha ao desativar.';
                this.changeDetector.markForCheck();
            },
        });
    }
}
