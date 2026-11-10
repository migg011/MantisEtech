/** Módulo line-pendencies: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    OnInit,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { finalize } from 'rxjs';
import { LinePendency } from '../../core/models/line-pendency.model';
import { PRIORITY_LABELS } from '../../core/models/problem-type.model';
import { FormModal } from '../../shared/form-modal.component';
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
    template: `
        <section class="page">
            <a routerLink="/cadastro">Central de Cadastros</a>
            <div class="eyebrow">MANUTENÇÃO / ACOMPANHAMENTO</div
            ><h1>Pendências de linha</h1>
            <p class="muted"
                >Ações registradas nas ordens de serviço, organizadas linha por
                linha.</p
            >
            <div class="card filters"
                ><label
                    >Linha<select [(ngModel)]="lineSelected"
                        ><option [ngValue]="null">Todas as linhas</option
                        ><option
                            *ngFor="let line of lines"
                            [ngValue]="line.id"
                            >{{ line.name }}</option
                        ></select
                    ></label
                ><label
                    >Situação<select [(ngModel)]="status"
                        ><option value="PENDENTE">Pendentes</option
                        ><option value="RESOLVIDA">Resolvidas</option
                        ><option value="">Todas</option></select
                    ></label
                ><label
                    >Pesquisar<input
                        [(ngModel)]="search"
                        placeholder="Descrição, máquina, serial ou OS" /></label
            ></div>
            <p *ngIf="loading" role="status">Carregando pendências...</p
            ><p *ngIf="error" class="error" role="alert">{{ error }}</p
            ><p *ngIf="message" class="success" role="status">{{ message }}</p>
            <article class="card line-group" *ngFor="let group of groups"
                ><h2
                    ><mat-icon>pending_actions</mat-icon>{{ group.name }}
                    <span>{{ group.items.length }} registro(s)</span></h2
                >
                <div class="pendency" *ngFor="let item of group.items"
                    ><div class="pendency-heading"
                        ><strong
                            >P-{{ item.id }} · OS #{{
                                item.work_order_id
                            }}</strong
                        ><span
                            class="badge"
                            [class.resolved]="item.status === 'RESOLVIDA'"
                            >{{
                                item.status === 'PENDENTE'
                                    ? 'Pendente'
                                    : 'Resolvida'
                            }}
                            · {{ labelPriority(item.priority) }}</span
                        ></div
                    >
                    <p class="description">{{ item.description }}</p
                    ><p
                        >{{ item.equipment_model || 'Máquina' }} · Serial:
                        {{ item.equipment_serial || 'Não cadastrado' }}</p
                    ><small
                        >Registrada por {{ item.created_by_name }} em
                        {{ item.created_at | date: 'dd/MM/yyyy HH:mm' }}</small
                    >
                    <div *ngIf="item.status === 'RESOLVIDA'" class="resolution"
                        ><strong>Solução registrada</strong
                        ><p>{{ item.resolution }}</p
                        ><small
                            >{{ item.resolved_by_name }} ·
                            {{
                                item.resolved_at | date: 'dd/MM/yyyy HH:mm'
                            }}</small
                        ></div
                    >
                    <div class="actions"
                        ><a
                            mat-button
                            [routerLink]="['/ordens']"
                            [queryParams]="{ orderId: item.work_order_id }"
                            >Consultar OS</a
                        ><button
                            mat-stroked-button
                            *ngIf="item.status === 'PENDENTE'"
                            [disabled]="processing"
                            (click)="openResolution(item)"
                            >Registrar solução</button
                        ></div
                    >
                </div>
            </article>
            <div *ngIf="!loading && !error && !groups.length" class="card muted"
                >Nenhuma pendência encontrada para os filtros selecionados.
                Registre uma pendência na tela de Ordens de serviço.</div
            >
        </section>
        <app-form-modal
            *ngIf="resolving as item"
            title="Resolver pendência"
            [subtitle]="
                'P-' +
                item.id +
                ' · ' +
                item.line_name +
                ' · OS #' +
                item.work_order_id
            "
            icon="task_alt"
            [busy]="processing"
            (closed)="resolving = null"
        >
            <p>{{ item.description }}</p
            ><p *ngIf="errorResolution" class="error" role="alert">{{
                errorResolution
            }}</p>
            <label
                ><span>Solução realizada *</span
                ><textarea
                    rows="4"
                    maxlength="5000"
                    [(ngModel)]="resolution"
                ></textarea>
            </label>
            <div modalActions class="modal-actions"
                ><button
                    type="button"
                    [disabled]="processing"
                    (click)="resolving = null"
                    >Cancelar</button
                ><button
                    type="button"
                    class="primary"
                    [disabled]="processing || resolution.trim().length < 5"
                    (click)="resolve()"
                    >{{
                        processing ? 'Salvando...' : 'Marcar como resolvida'
                    }}</button
                ></div
            >
        </app-form-modal>
    `,
    styles: [
        `
            .filters {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                margin-bottom: 24px;
            }
            .filters label {
                display: grid;
                gap: 8px;
                flex: 1;
                min-width: 180px;
                font-weight: 600;
            }
            select,
            input {
                padding: 12px;
                border: 1px solid #d6dae2;
                border-radius: 8px;
                background: white;
                font: inherit;
                min-width: 0;
            }
            .line-group {
                margin-bottom: 24px;
            }
            h2 {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            h2 span {
                margin-left: auto;
                font-size: 13px;
                color: #64748b;
                font-weight: 400;
            }
            .pendency {
                border-top: 1px solid #e5e7eb;
                padding: 20px 0;
            }
            .pendency-heading {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                align-items: center;
                justify-content: space-between;
            }
            .description,
            .resolution p {
                white-space: pre-wrap;
                overflow-wrap: anywhere;
            }
            .description {
                font-weight: 600;
            }
            small {
                color: #64748b;
            }
            .badge {
                background: #fff3df;
                color: #946000;
                border-radius: 16px;
                padding: 6px 12px;
                font-size: 12px;
            }
            .badge.resolved {
                background: #dcfce7;
                color: #166534;
            }
            .resolution {
                margin-top: 16px;
                background: #f1faf5;
                padding: 16px;
                border-radius: 8px;
            }
            .actions {
                display: flex;
                gap: 12px;
                margin-top: 16px;
            }
            .eyebrow {
                margin-top: 24px;
            }
        `,
    ],
})
export class LinePendencies implements OnInit {
    private httpClient = inject(HttpClient);
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    items: LinePendency[] = [];
    lineSelected: number | null = null;
    status = 'PENDENTE';
    search = '';
    loading = true;
    processing = false;
    error = '';
    message = '';
    errorResolution = '';
    resolution = '';
    resolving: LinePendency | null = null;
    /** Traduz o código de prioridade para o rótulo apresentado ao usuário. */
    labelPriority(value: string) {
        return PRIORITY_LABELS[value] || value;
    }
    /** Deriva as linhas que possuem registros de pendência e ordena seus nomes para o filtro. */
    get lines() {
        return [
            ...new Map(
                this.items.map((item) => [
                    item.line_id,
                    {
                        id: item.line_id,
                        name: item.line_name,
                    },
                ])
            ).values(),
        ].sort((a, b) => a.name.localeCompare(b.name));
    }
    /** Aplica os filtros de linha, situação e pesquisa sobre os registros carregados e os agrupa por linha. */
    get groups() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.lines
            .filter(
                (line) => !this.lineSelected || line.id === this.lineSelected
            )
            .map((line) => ({
                name: line.name,
                items: this.items.filter(
                    (item) =>
                        item.line_id === line.id &&
                        (!this.status || item.status === this.status) &&
                        [
                            item.description,
                            item.equipment_model,
                            item.equipment_serial,
                            String(item.work_order_id),
                        ].some((value) =>
                            (value || '')
                                .toLocaleLowerCase('pt-BR')
                                .includes(term)
                        )
                ),
            }))
            .filter((group) => group.items.length);
    }
    /** GET /api/line-pendencies: carrega as pendências e seus históricos para a Central de Cadastros. */
    ngOnInit() {
        this.httpClient
            .get<LinePendency[]>('/api/line-pendencies')
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (items) => (this.items = items),
                error: () =>
                    (this.error = 'Não foi possível carregar as pendências.'),
            });
    }
    /** Seleciona a pendência e abre o modal com o campo de solução vazio. */
    openResolution(item: LinePendency) {
        this.resolving = item;
        this.resolution = '';
        this.errorResolution = '';
        this.message = '';
    }
    /** PATCH /api/line-pendencies/:id: envia a solução; no sucesso substitui o registro local pelos dados auditados do Django. */
    resolve() {
        if (
            this.processing ||
            !this.resolving ||
            this.resolution.trim().length < 5
        )
            return;
        this.processing = true;
        this.errorResolution = '';
        this.httpClient
            .patch<LinePendency>(`/api/line-pendencies/${this.resolving.id}`, {
                status: 'RESOLVIDA',
                resolution: this.resolution.trim(),
            })
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.processing = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (item) => {
                    this.items = this.items.map((old) =>
                        old.id === item.id ? item : old
                    );
                    this.resolving = null;
                    this.message = `Pendência P-${item.id} resolvida.`;
                },
                error: (failure) =>
                    (this.errorResolution =
                        failure.error?.error ||
                        'Não foi possível resolver a pendência.'),
            });
    }
}
