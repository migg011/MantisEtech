/** Cadastro central de categorias. Spare Parts apenas consulta e seleciona esta lista. */
import {
    Component,
    ChangeDetectorRef,
    DestroyRef,
    inject,
    OnInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { FormModal } from '../../shared/form-modal.component';
interface Category {
    id: number;
    name: string;
    description: string;
    active: boolean;
    part_count: number;
}
@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        RouterLink,
        MatButtonModule,
        MatIconModule,
        FormModal,
    ],
    templateUrl: './material-categories.component.html',
    styleUrl: './material-categories.component.scss',
})
export class MaterialCategories implements OnInit {
    private http = inject(HttpClient);
    private detector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    categories: Category[] = [];
    search = '';
    loading = false;
    saving = false;
    formOpen = false;
    editingId: number | null = null;
    name = '';
    description = '';
    errorMessage = '';
    successMessage = '';
    get filtered() {
        const q = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.categories.filter(
            (category) =>
                !q ||
                (category.name + ' ' + category.description)
                    .toLocaleLowerCase('pt-BR')
                    .includes(q)
        );
    }
    ngOnInit() {
        this.load();
    }
    /** Inclui inativas para permitir reativação sem duplicar o cadastro antigo. */
    load() {
        this.loading = true;
        this.http
            .get<Category[]>('/api/part-categories', {
                params: { includeInactive: 'true' },
            })
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe({
                next: (records) => {
                    this.categories = records;
                    this.loading = false;
                    this.detector.markForCheck();
                },
                error: () => {
                    this.errorMessage =
                        'Não foi possível carregar as categorias.';
                    this.loading = false;
                    this.detector.markForCheck();
                },
            });
    }
    open(category?: Category) {
        this.editingId = category?.id ?? null;
        this.name = category?.name ?? '';
        this.description = category?.description ?? '';
        this.errorMessage = '';
        this.successMessage = '';
        this.formOpen = true;
    }
    close() {
        if (!this.saving) this.formOpen = false;
    }
    async save() {
        if (this.saving || !this.name.trim()) return;
        this.saving = true;
        this.errorMessage = '';
        try {
            const payload = { name: this.name, description: this.description };
            await firstValueFrom(
                this.editingId
                    ? this.http.patch(
                          '/api/part-categories/' + this.editingId,
                          payload
                      )
                    : this.http.post('/api/part-categories', payload)
            );
            this.formOpen = false;
            this.successMessage = 'Categoria salva com sucesso.';
            this.load();
        } catch (e: any) {
            this.errorMessage =
                e.error?.error || 'Não foi possível salvar a categoria.';
        } finally {
            this.saving = false;
            this.detector.markForCheck();
        }
    }
    /** Alterar a situação preserva as classificações das peças já cadastradas. */
    async toggle(category: Category) {
        if (this.saving) return;
        this.saving = true;
        this.errorMessage = '';
        this.successMessage = '';
        try {
            await firstValueFrom(
                this.http.patch('/api/part-categories/' + category.id, {
                    active: !category.active,
                })
            );
            this.successMessage = category.active
                ? 'Categoria desativada.'
                : 'Categoria reativada.';
            this.load();
        } catch (e: any) {
            this.errorMessage =
                e.error?.error || 'Não foi possível alterar a categoria.';
        } finally {
            this.saving = false;
            this.detector.markForCheck();
        }
    }
}
