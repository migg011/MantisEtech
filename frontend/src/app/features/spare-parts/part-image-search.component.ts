import {CommonModule} from '@angular/common';
import {HttpClient} from '@angular/common/http';
import {Component, DestroyRef, inject, signal} from '@angular/core';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {timeout} from 'rxjs';
import {FormModal} from '../../shared/form-modal.component';
import {PartLookup} from '../../shared/part-sheet.component';

interface ImageSearchResult {
    id: number;
    code: string;
    part_number: string | null;
    description: string;
    manufacturer: string | null;
    stock_quantity: number | null;
    storage_location: string | null;
    unit: string;
    evidence: 'codigo' | 'texto' | 'visual';
    visual_similarity: number | null;
}

interface ImageSearchResponse {
    results: ImageSearchResult[];
    codes: string[];
    label: string;
    ocr_available: boolean;
}

@Component({
    selector: 'app-part-image-search',
    standalone: true,
    imports: [CommonModule, FormsModule, FormModal, PartLookup, MatButtonModule, MatIconModule],
    templateUrl: './part-image-search.component.html',
    styles: [`
        .search-fields {display: grid; gap: 14px;}
        .photo-panel {display: grid; gap: 8px; padding: 12px; background: #f4f6f9; border-radius: 12px;}
        .photo-actions {display: flex; flex-wrap: wrap; gap: 8px;}
        .reference-row {display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 12px;}
        .reference-row label {display: block;}
        .reference-row input {display: block; width: 100%; min-height: 40px; margin-top: 4px; box-sizing: border-box;}
        .reference-row button {min-height: 40px;}
        .results-title {margin: 18px 0 4px;}
        .result {border: 1px solid #dce3eb; border-radius: 10px; padding: 10px 14px; margin: 8px 0;}
        .result p {margin: 4px 0;}
        .detected {overflow-wrap: anywhere;}
        .reading-details {margin-top: 12px;}
        .reading-details summary {cursor: pointer;}
        @media (max-width: 540px) {
            .reference-row {grid-template-columns: 1fr;}
            .photo-actions button {flex: 1 1 auto;}
        }
    `],
})
export class PartImageSearch {
    private http = inject(HttpClient);
    private destroyRef = inject(DestroyRef);
    open = false;
    file: File | null = null;
    reference = '';
    readonly busy = signal(false);
    readonly error = signal('');
    readonly response = signal<ImageSearchResponse | null>(null);
    readonly evidence = {
        codigo: 'Código correspondente',
        texto: 'Código reconhecido na etiqueta ou gravação',
        visual: 'Sugestão por semelhança visual',
    };

    close() {
        this.open = false;
        this.file = null;
        this.reference = '';
        this.error.set('');
        this.response.set(null);
    }

    capture(event: Event) {
        this.choose(event);
        (event.target as HTMLInputElement).value = '';
        this.search();
    }

    choose(event: Event) {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0] ?? null;
        this.response.set(null);
        this.error.set('');
        if (file && file.size > 6 * 1024 * 1024) {
            this.file = null;
            this.error.set('Escolha uma imagem de até 6 MB.');
            input.value = '';
            return;
        }
        this.file = file;
    }

    search() {
        if (!this.file || this.busy()) return;
        const payload = new FormData();
        payload.set('image', this.file);
        payload.set('reference', this.reference.trim());
        this.busy.set(true);
        this.error.set('');
        this.response.set(null);
        this.http.post<ImageSearchResponse>('/api/spare-parts/image-search', payload)
            .pipe(timeout(30000), takeUntilDestroyed(this.destroyRef))
            .subscribe({
                next: response => {
                    this.response.set(response);
                    this.busy.set(false);
                },
                error: error => {
                    this.error.set(error.error?.error || 'Não foi possível concluir a busca por imagem.');
                    this.busy.set(false);
                },
            });
    }
}
