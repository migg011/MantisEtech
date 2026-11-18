import {RegistrationFeedback} from '../../shared/registration-feedback';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

interface EquipmentType {
    id: number;
    name: string;
}

@Component({
    standalone: true,
    imports: [FormsModule, MatButtonModule, RouterLink],
    template: `
        <div class="page">
            <a routerLink="/cadastro/manutencao">← Manutenção</a>
            <h1>Tipos de equipamento</h1>
            <section class="card">
                @if (editing()) {
                    <form (ngSubmit)="save()">
                        <label>Nome do tipo
                            <input name="name" [(ngModel)]="name" required maxlength="100" placeholder="Ex.: Inspeção 3D">
                        </label>
                        <div class="actions">
                            <button type="button" mat-stroked-button [disabled]="saving()" (click)="closeForm()">Cancelar</button>
                            <button type="submit" mat-flat-button class="primary" [disabled]="!name.trim() || saving()">Salvar</button>
                        </div>
                    </form>
                } @else {
                    <button type="button" mat-flat-button class="primary" [disabled]="types() === null" (click)="editing.set(true)">Novo tipo</button>
                }
                @if (error()) {
                    <p role="alert">{{ error() }}</p>
                }
                @if (types(); as items) {
                    <ul>
                        @for (item of items; track item.id) {
                            <li>{{ item.name }}</li>
                        } @empty {
                            <li>Nenhum tipo cadastrado.</li>
                        }
                    </ul>
                } @else if (!error()) {
                    <p>Carregando tipos de equipamento...</p>
                }
            </section>
        </div>
    `,
    styles: [`
        form { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; }
        label { display: grid; gap: 6px; }
        input { padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; font: inherit; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    `],
})
export class EquipmentTypes implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    private readonly http = inject(HttpClient);
    private readonly url = '/api/equipment-types';
    readonly types = signal<EquipmentType[] | null>(null);
    readonly editing = signal(false);
    readonly saving = signal(false);
    readonly error = signal('');
    name = '';

    ngOnInit() {
        this.http.get<EquipmentType[]>(this.url).subscribe({
            next: types => this.types.set(types),
            error: () => this.error.set('Não foi possível carregar os tipos de equipamento.'),
        });
    }

    closeForm() {
        this.name = '';
        this.error.set('');
        this.editing.set(false);
    }

    save() {
        if (!this.name.trim() || this.saving()) return;
        this.error.set('');
        this.saving.set(true);
        this.http.post<EquipmentType>(this.url, {name: this.name})
            .pipe(finalize(() => this.saving.set(false))).subscribe({
                next: item => {
                    this.types.update(types => [...(types ?? []), item]);
                    this.closeForm();
                    this.registrationFeedback.created('Tipo de equipamento cadastrado com sucesso', item.name);
                },
                error: (error: HttpErrorResponse) => this.error.set(
                    typeof error.error?.error === 'string' ? error.error.error : 'Não foi possível salvar o tipo.',
                ),
            });
    }
}
