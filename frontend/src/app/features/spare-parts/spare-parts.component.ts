import {MatAutocompleteModule} from '@angular/material/autocomplete';
import {RegistrationFeedback} from '../../shared/registration-feedback';
import {PartImageSearch} from './part-image-search.component';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
/** Módulo spare-parts: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {PartStock} from '../../shared/part-stock.component';
import {FormModal} from '../../shared/form-modal.component';
import {CommonModule} from '@angular/common';
import {Component, ChangeDetectorRef, DestroyRef, inject, OnInit, OnDestroy} from '@angular/core';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {firstValueFrom, Subscription} from 'rxjs';
import {PartLookup} from '../../shared/part-sheet.component';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {MatMenuModule} from '@angular/material/menu';
import {Auth} from '../../services';

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
    categories: {id:number;name:string;active:boolean}[];
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
    imports: [PartImageSearch, PartStock, PartLookup, FormModal,
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule, MatAutocompleteModule,
        MatIconModule, MatMenuModule
    ],
    templateUrl: './spare-parts.component.html',
    styleUrl: './spare-parts.component.scss'
})
/** Cadastro de peças com saldo movimentado em uma operação separada e auditável. */
export class SpareParts implements OnInit, OnDestroy {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    // A mesma tela funciona como cadastro normal ou como catálogo chamado por uma OS.
    readonly selectionContext = inject<{selectForWorkOrder?:number}>(MAT_DIALOG_DATA,{optional:true});
    private catalogDialog = inject(MatDialogRef<SpareParts>,{optional:true});
    get selectingForOrder(){return !!this.selectionContext?.selectForWorkOrder;}
    closeCatalog(){this.catalogDialog?.close();}
    selectForWorkOrder(partValue:SparePart){if(this.selectingForOrder)this.catalogDialog?.close(partValue);}

    private destroyRef = inject(DestroyRef);
    private photoLookup = 0;
    chosenPhoto: File | null = null;
    photoPreview: string | null = null;
    savedPhotoName = '';
    loadingPhoto = false;
    photoError = '';
    previewedPhoto: SparePart | null = null;
    /** O arquivo original fica no banco; a URL Blob existe somente durante a visualização. */
    private clearPhoto() {
        ++this.photoLookup;
        if (this.photoPreview) URL.revokeObjectURL(this.photoPreview);
        this.photoPreview = null;
        this.chosenPhoto = null;
        this.savedPhotoName = this.photoError = '';
        this.loadingPhoto = false;
    }
    private loadPhoto(partValue: SparePart) {
        this.clearPhoto();
        this.savedPhotoName = partValue.photo_filename || '';
        if (!partValue.photo_filename) return;
        const lookup = this.photoLookup;
        this.loadingPhoto = true;
        this.httpValue.get(`/api/spare-parts/${partValue.id}/photo`, {responseType:'blob'}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: file => {
                if (lookup !== this.photoLookup) return;
                this.photoPreview = URL.createObjectURL(file);
                this.loadingPhoto = false;
                this.cdr.markForCheck();
            },
            error: () => {
                if (lookup !== this.photoLookup) return;
                this.photoError = 'Não foi possível carregar a foto salva. Ela será mantida ao salvar sem escolher outra.';
                this.loadingPhoto = false;
                this.cdr.markForCheck();
            }
        });
    }
    selectPhoto(event: Event) {
        const fieldValue = event.target as HTMLInputElement;
        const file = fieldValue.files?.[0];
        if (!file) return;
        if (!['image/png','image/jpeg'].includes(file.type) || !file.size || file.size > 3*1024*1024) {
            fieldValue.value = '';
            this.photoError = 'Selecione uma foto JPG ou PNG de até 3 MB.';
            return;
        }
        ++this.photoLookup;
        if (this.photoPreview) URL.revokeObjectURL(this.photoPreview);
        this.chosenPhoto = file;
        this.photoPreview = URL.createObjectURL(file);
        this.photoError = '';
        this.loadingPhoto = false;
    }
    previewPhoto(partValue: SparePart) { this.previewedPhoto = partValue; this.loadPhoto(partValue); }
    closePhoto() { this.previewedPhoto = null; this.clearPhoto(); }
    ngOnDestroy() { this.clearPhoto(); this.catalogLookup?.unsubscribe(); }
    stockPart: SparePart | null = null;
    updatingStock=false;
    inventory: any = null;
    loadingInventory = false;
    inventoryError = '';
    downloadingInventory = false;
    // O relatório consulta o catálogo completo; o filtro atual é enviado explicitamente.
    openInventory() {
        this.inventory=null;this.inventoryError='';this.loadingInventory=true;
        this.httpValue.get('/api/spare-parts/inventory',{params:{q:this.search.trim(),categoryId:this.categoryFilter,sectorId:this.sectorFilter}}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:r=>{this.inventory=r;this.loadingInventory=false;this.cdr.markForCheck();},error:()=>{this.inventoryError='Não foi possível carregar o inventário.';this.loadingInventory=false;this.cdr.markForCheck();}});
    }
    downloadInventory() {
        if(this.downloadingInventory)return;
        this.downloadingInventory=true;
        const searchTerm=this.inventory?.query ?? this.search.trim();
        this.httpValue.get('/api/spare-parts/inventory.csv',{params:{q:searchTerm,categoryId:this.inventory?.category_id || '',sectorId:this.inventory?.sector_id || ''},responseType:'blob'}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:blob=>{const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='INVENTARIO_PECAS.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);this.downloadingInventory=false;this.cdr.markForCheck();},error:()=>{this.inventoryError='Falha ao baixar o CSV.';this.downloadingInventory=false;this.cdr.markForCheck();}});
    }
    printInventory() {
        if(!this.inventory)return;
        const popup=window.open('','_blank');if(!popup){this.inventoryError='Permita abrir a janela de impressão neste navegador.';return;}
        // Criação por textContent impede que descrições sejam interpretadas como HTML.
        const doc=popup.document;doc.title='Inventário de peças MANTIS';
        const style=doc.createElement('style');style.textContent='body{font:12px Arial;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:7px;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}button{padding:10px;margin:12px 0}@media print{button{display:none}}';doc.head.append(style);
        const titleValue=doc.createElement('h1');titleValue.textContent='Inventário de peças MANTIS';doc.body.append(titleValue);
        const noteValue=doc.createElement('p');noteValue.textContent='Gerado em '+new Date(this.inventory.generated_at).toLocaleString('pt-BR')+' · Filtro: '+(this.inventory.query||'Todos os itens ativos')+' · Categoria: '+(this.inventory.category_name || 'Todas')+' · '+this.inventory.uninitialized_items+' item(ns) sem contagem inicial.';doc.body.append(noteValue);
        const warningMessage=doc.createElement('p');warningMessage.textContent='Saldo registrado em estoque, sem reservas ou baixas automáticas por OS. Quantidades de unidades diferentes não são somadas.';doc.body.append(warningMessage);
        const button=doc.createElement('button');button.textContent='Imprimir / Salvar PDF';button.onclick=()=>popup.print();doc.body.append(button);
        const table=doc.createElement('table'),cab=table.createTHead().insertRow();
        ['Part Number','Descrição','Fabricante','Localização','Unidade','Saldo disponível','Situação','Categorias'].forEach(t=>{const th=doc.createElement('th');th.textContent=t;cab.append(th);});
        const bodyValue=table.createTBody();for(const p of this.inventory.items){const tr=bodyValue.insertRow();[p.part_number||'—',p.description,p.manufacturer||'—',p.storage_location||'—',p.unit,p.stock_quantity===null?'Não informado':Number(p.stock_quantity).toLocaleString('pt-BR',{maximumFractionDigits:3}),p.stock_status,(p.categories || []).join(', ')].forEach(v=>{tr.insertCell().textContent=String(v);});}doc.body.append(table);
    }
    closeStock(){this.stockPart=null;this.loadData();}
    categoryFilter = '';
    sectorFilter = '';
    sectors: {id: number; name: string; cost_center: string}[] = [];
    categoriesValue: {id:number;name:string;description:string;active:boolean;part_count:number}[] = [];
    categoryError='';
    /** O cadastro central evita grafias diferentes para a mesma classificação. */
    loadCategories() {
        this.httpValue.get<typeof this.categoriesValue>('/api/part-categories',{params:{includeInactive:'true'}}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:r=>{this.categoriesValue=r;this.cdr.markForCheck();},error:()=>{this.categoryError='Não foi possível carregar as categorias.';this.cdr.markForCheck();}});
    }
    get availableCategories(){return this.categoriesValue.filter(c=>c.active && !this.form.categoryIds.includes(c.id));}
    get selectedCategories(){return this.categoriesValue.filter(c=>this.form.categoryIds.includes(c.id));}
    /** A lista suspensa adiciona uma categoria por vez, sem duplicar nem apagar classificações existentes. */
    addCategory(event:Event) {
        const fieldValue=event.target as HTMLSelectElement;
        const id=Number(fieldValue.value);
        if(!this.saving && this.availableCategories.some(c=>c.id===id))this.form.categoryIds=[...this.form.categoryIds,id];
        fieldValue.value='';
    }
    removeCategory(id:number){if(!this.saving)this.form.categoryIds=this.form.categoryIds.filter(c=>c!==id);}
    search = '';
    suggestions: SparePart[] = [];

    searchChanged(value: string) {
        this.search = value;
        this.loadData();
    }
    private catalogLookup?: Subscription;
    private httpValue = inject(HttpClient);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    private authValue = inject(Auth);
    partsValue: SparePart[] = [];
    showForm = false;

    /** Limpa a peça em edição e abre o cadastro de uma nova peça. */
    newPart() {
        this.cancel();
        this.success = '';
        this.showForm = true;
    }

    currentEditId: number | null = null;
    saving = false;
    errorValue = '';
    success = '';
    form = this.initialForm();

    /** Cria os valores iniciais de estoque de referência, custos e compatibilidade. */
    private initialForm() {
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
            equipmentIds: [] as number[]
        };
    }

    /** Consulta o perfil local para mostrar ações exclusivas de administrador. */
    isAdmin() {
        return this.authValue.userValue()?.role === 'ADMINISTRADOR';
    }

    /** Carrega peças e equipamentos necessários ao cadastro de compatibilidade. */
    ngOnInit() {
        this.httpValue.get<typeof this.sectors>('/api/sectors').pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: sectors => { this.sectors = sectors; this.cdr.markForCheck(); },
            error: () => { this.errorValue = 'Não foi possível carregar os setores.'; this.cdr.markForCheck(); },
        });
        this.loadData();
        this.loadCategories();
    }

    /** GET /api/spare-parts recarrega o catálogo de peças ativas. */
    loadData() {
        this.catalogLookup?.unsubscribe();
        this.suggestions = [];
        this.catalogLookup = this.httpValue.get<SparePart[]>('/api/spare-parts', {params:{q:this.search.trim(),categoryId:this.categoryFilter,sectorId:this.sectorFilter}})
            .subscribe({
                next: x => {
                    this.partsValue = x;
                    this.suggestions = this.search.trim().length >= 2 ? x.slice(0, 8) : [];
                    this.cdr.markForCheck();
                },
                error: () => {
                    this.errorValue = 'Não foi possível carregar as peças.';
                    this.cdr.markForCheck();
                }
            });
    }

    /** Converte os dados retornados para os campos do formulário da peça escolhida. */
    edit(p: SparePart) {
        if (!this.isAdmin())
            return;
        this.showForm = true;
        this.currentEditId = p.id;
        this.loadPhoto(p);
        this.form = {
            description: p.description,
            partNumber: p.part_number || '',
            manufacturer: p.manufacturer || '',
            categoryIds: [...(p.category_ids || [])],
            unit: p.unit,
            minimumStock: Number(p.minimum_stock),
            maximumStock: p.maximum_stock === null
                ? null
                : Number(p.maximum_stock),
            reorderPoint: Number(p.reorder_point),
            storageLocation: p.storage_location || '',
            preferredSupplier: p.preferred_supplier || '',
            averageCost: p.average_cost === null
                ? null
                : Number(p.average_cost),
            lastCost: p.last_cost === null
                ? null
                : Number(p.last_cost),
            equipmentIds: p.equipment_ids.map(Number),
            averageCostCurrency: p.average_cost_currency || '',
            lastCostCurrency: p.last_cost_currency || ''
        };
        this.errorValue = '';
        this.success = '';
    }

    /** Descarta os campos locais e fecha o modal. */
    cancel() {
        this.clearPhoto();
        this.showForm = false;
        this.currentEditId = null;
        this.form = this.initialForm();
        this.errorValue = '';
    }

    /** POST ou PATCH grava o cadastro mestre e seus vínculos de compatibilidade; não movimenta saldo de estoque. */
    async save() {
        if (!this.isAdmin() ||
            this.saving ||
            !this.form.description.trim())
            return;
        this.saving = true;
        this.errorValue = '';
        this.success = '';
        if ((this.form.averageCost !== null && !this.form.averageCostCurrency) ||
            (this.form.lastCost !== null && !this.form.lastCostCurrency)) {
            this.errorValue = 'Selecione R$ ou US$ para cada custo preenchido.';
            this.saving = false;
            return;
        }
        try {
            const partId = this.currentEditId;
            const dataValue: any = {...this.form};
            const photoValue = this.chosenPhoto;
            if (photoValue) {
                const base64 = await new Promise<string>((resolve,reject)=>{
                    const fileReader = new FileReader();
                    fileReader.onload = ()=>resolve(String(fileReader.result).split(',')[1]);
                    fileReader.onerror = ()=>reject(new Error('Não foi possível ler a foto.'));
                    fileReader.readAsDataURL(photoValue);
                });
                dataValue.photo = {filename:photoValue.name, mimeType:photoValue.type, base64};
            }
            await firstValueFrom(partId
                ? this.httpValue.patch('/api/spare-parts/' + partId, dataValue)
                : this.httpValue.post('/api/spare-parts', dataValue));
            this.cancel();
            if (partId) this.success = 'Alterações salvas.';
            else this.registrationFeedback.created('Peça cadastrada com sucesso',
                [dataValue.partNumber?.trim(), dataValue.description.trim()].filter(Boolean).join(' · '));
            this.loadCategories();
            this.loadData();
        } catch (e: any) {
            this.errorValue = e.error?.error || e.message || 'Falha ao salvar peça.';
        } finally {
            this.saving = false;
            this.cdr.markForCheck();
        }
    }

    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE desativa a peça preservando os históricos de solicitações. */
    deactivate(p: SparePart) {
        if (!this.isAdmin() ||
            !confirm('Desativar esta peça?'))
            return;
        this.httpValue.delete('/api/spare-parts/' + p.id)
            .subscribe({
                next: () => this.loadData(),
                error: e => {
                    this.errorValue = e.error?.error ||
                        'Falha ao desativar.';
                    this.cdr.markForCheck();
                }
            });
    }
}
