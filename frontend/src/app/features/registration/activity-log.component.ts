import {DatePipe} from '@angular/common';
import {HttpClient} from '@angular/common/http';
import {Component, DestroyRef, inject, OnInit, signal} from '@angular/core';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {finalize} from 'rxjs';

interface Activity {
    id: number;
    actor_name: string;
    actor_registration: string;
    method: string;
    route: string;
    target: Record<string, number>;
    created_at: string;
}

@Component({
    imports: [DatePipe, FormsModule, RouterLink],
    template: `
        <main class="page">
            <a routerLink="/cadastro">← Central de Cadastros</a>
            <h1>Registro de atividades</h1>
            <form class="filters" (ngSubmit)="load(1)">
                <label>Usuário ou matrícula <input name="actor" [(ngModel)]="actor" maxlength="160"></label>
                <label>Método
                    <select name="method" [(ngModel)]="method">
                        <option value="">Todos</option>
                        <option value="POST">Registros e operações</option>
                        <option value="PATCH">Alterações (PATCH)</option>
                        <option value="PUT">Alterações (PUT)</option>
                        <option value="DELETE">Exclusões e desativações</option>
                    </select>
                </label>
                <button type="submit" [disabled]="loading()">Filtrar</button>
            </form>
            @if (error()) { <p role="alert">{{error()}}</p> }
            @if (loading()) { <p role="status">Consultando atividades…</p> }
            @if (!loading() && !error() && !items().length) { <p>Nenhuma atividade encontrada.</p> }
            @if (items().length) {
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>Data e hora</th><th>Usuário</th><th>Ação</th><th>Registro</th></tr></thead>
                        <tbody>
                        @for (row of items(); track row.id) {
                            <tr><td>{{row.created_at | date:'dd/MM/yyyy HH:mm:ss'}}</td>
                                <td>{{row.actor_name}} <small>{{row.actor_registration}}</small></td>
                                <td>{{action(row)}}</td><td>{{reference(row)}}</td></tr>
                        }
                        </tbody>
                    </table>
                </div>
                <nav class="filters" aria-label="Paginação">
                    <button type="button" (click)="load(page()-1, false)" [disabled]="loading() || page() === 1">Anterior</button>
                    <span>Página {{page()}}</span>
                    <button type="button" (click)="load(page()+1, false)" [disabled]="loading() || !hasNext()">Próxima</button>
                </nav>
            }
        </main>
    `,
    styles: [`
        .page {max-width: 1200px; margin: auto; padding: 24px;}
        .filters {display:flex; align-items:end; flex-wrap:wrap; gap:12px; margin-block:16px;}
        label, small {display:block;}
        input, select, button {min-height:40px;}
        .table-wrap {overflow-x:auto;}
        table {width:100%; border-collapse:collapse;}
        td, th {padding:10px; text-align:left; border-bottom:1px solid #d4dbe3;}
    `],
})
export class ActivityLogPage implements OnInit {
    private readonly http = inject(HttpClient);
    private readonly destroyRef = inject(DestroyRef);
    actor = '';
    method = '';
    private applied = {actor: '', method: ''};
    readonly items = signal<Activity[]>([]);
    readonly page = signal(1);
    readonly hasNext = signal(false);
    readonly error = signal('');
    readonly loading = signal(false);

    ngOnInit() { this.load(1); }

    load(page: number, apply = true) {
        if (this.loading()) return;
        if (apply) this.applied = {actor: this.actor.trim(), method: this.method};
        this.loading.set(true);
        this.error.set('');
        this.http.get<{items: Activity[]; has_next: boolean}>('/api/activity-log', {
            params: {...this.applied, page},
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.loading.set(false))).subscribe({
            next: response => {
                this.items.set(response.items);
                this.page.set(page);
                this.hasNext.set(response.has_next);
            },
            error: () => this.error.set('Não foi possível consultar o registro de atividades.'),
        });
    }

    action(row: Activity) {
        if (row.route === 'api/auth/login') return 'Login';
        if (row.route.endsWith('/password')) return 'Redefiniu a senha';
        if (row.route.endsWith('/status')) return 'Alterou a situação';
        if (row.route.endsWith('/receipts')) return 'Registrou recebimento';
        if (row.route.endsWith('/stock-movements')) return 'Movimentou estoque';
        if (row.route.endsWith('/decision')) return 'Registrou decisão de compra';
        if (row.method === 'PATCH' || row.method === 'PUT') return 'Alterou registro';
        return row.method === 'DELETE' ? 'Excluiu ou desativou registro' : 'Registrou operação';
    }

    reference(row: Activity) {
        if (row.route === 'api/auth/login') return 'Sessão';
        const route = row.route.replace(/^api\//, '').replace(/<int:(\w+)>/g,
            (segment, key: string) => String(row.target[key] ?? segment));
        return row.target['id'] ? route + ' #' + row.target['id'] : route;
    }
}
