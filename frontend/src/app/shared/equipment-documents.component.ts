import { Component, DestroyRef, Input, OnChanges, OnDestroy, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, finalize } from 'rxjs';

export type AttachmentKind = 'PHOTO' | 'MANUAL' | 'ELECTRICAL';

export interface EquipmentAttachment {
    kind: AttachmentKind;
    filename: string;
}

@Component({
    selector: 'app-equipment-documents',
    standalone: true,
    imports: [MatButtonModule],
    templateUrl: './equipment-documents.component.html',
    styles: [`
        :host { display:block; }
        ul { padding:0; margin:0; list-style:none; }
        li { display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; }
        img { display:block; max-width:100%; max-height:360px; object-fit:contain; margin:12px 0; }
    `]
})
export class EquipmentDocuments implements OnChanges, OnDestroy {
    @Input({required:true}) equipmentId!: number;
    private http = inject(HttpClient);
    private destroyRef = inject(DestroyRef);
    private requests = new Subscription();
    readonly labels = {PHOTO: 'Foto', MANUAL: 'Manual técnico', ELECTRICAL: 'Esquema elétrico'};
    readonly files = signal<EquipmentAttachment[]>([]);
    readonly loading = signal(false);
    readonly opening = signal<AttachmentKind | null>(null);
    readonly error = signal('');
    readonly photo = signal('');

    ngOnChanges() {
        this.requests.unsubscribe();
        this.requests = new Subscription();
        this.clearPhoto();
        this.files.set([]);
        this.error.set('');
        this.loading.set(true);
        this.requests.add(this.http.get<EquipmentAttachment[]>(this.baseUrl).pipe(
            finalize(() => this.loading.set(false)),
        ).subscribe({
            next: files => this.files.set(files),
            error: () => this.error.set('Não foi possível consultar os documentos do equipamento.'),
        }));
    }

    private get baseUrl() { return `/api/equipment/${this.equipmentId}/attachments`; }

    open(file: EquipmentAttachment) {
        if (this.opening()) return;
        this.error.set('');
        if (file.kind === 'PHOTO' && this.photo()) {
            this.clearPhoto();
            return;
        }
        const tab = file.kind === 'PHOTO' ? null : window.open('about:blank', '_blank');
        if (file.kind !== 'PHOTO' && !tab) {
            this.error.set('Permita pop-ups para abrir o PDF em outra aba.');
            return;
        }
        if (tab) tab.opener = null;
        this.opening.set(file.kind);
        let opened = false;
        this.requests.add(this.http.get(`${this.baseUrl}/${file.kind}/view`, {responseType:'blob'}).pipe(
            takeUntilDestroyed(this.destroyRef),
            finalize(() => {
                this.opening.set(null);
                if (tab && !opened) tab.close();
            }),
        ).subscribe({
            next: blob => {
                if (tab?.closed) return;
                const url = URL.createObjectURL(blob);
                if (tab) {
                    tab.location.href = url;
                    opened = true;
                    // A nova aba precisa carregar o PDF antes de liberar a URL.
                    setTimeout(() => URL.revokeObjectURL(url), 60000);
                } else {
                    this.photo.set(url);
                }
            },
            error: () => this.error.set('Não foi possível abrir o arquivo. Tente novamente.'),
        }));
    }

    private clearPhoto() {
        if (this.photo()) URL.revokeObjectURL(this.photo());
        this.photo.set('');
    }

    ngOnDestroy() {
        this.requests.unsubscribe();
        this.clearPhoto();
    }
}
