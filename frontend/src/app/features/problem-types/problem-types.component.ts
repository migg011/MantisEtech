import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo problem-types: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { finalize } from 'rxjs';
import { Api } from '../../services';
import { ProblemType, PRIORITY_LABELS } from '../../core/models/problem-type.model';
import { FormModal } from '../../shared/form-modal.component';
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, MatButtonModule, MatIconModule, FormModal],
    template: `
        <section class="page">
            <div class="catalog-heading"><div><div class="eyebrow">CENTRAL DE CADASTROS / MANUTENÇÃO</div><h1>Problemas de manutenção</h1><p class="muted">Cadastre as opções que o operador seleciona ao abrir uma ordem de serviço.</p></div><button mat-flat-button class="primary" (click)="novoProblema()"><mat-icon>add</mat-icon>Novo problema</button></div>
            <p *ngIf="messageValue" class="success" role="status">{{messageValue}}</p>
            <p *ngIf="errorValue && !showForm" class="error" role="alert">{{errorValue}}</p>
            <div class="card"><h2>Problemas cadastrados</h2><p class="muted">Problemas inativos deixam de aparecer na abertura de OS. O histórico é preservado.</p>
                <p *ngIf="loading" class="muted" role="status">Carregando catálogo...</p>
                <div class="table-wrap"><table><thead><tr><th>Problema</th><th>Equipamento</th><th>Prioridade padrão</th><th>Situação</th><th>Ações</th></tr></thead><tbody>
                    <tr *ngFor="let problem of problemsValue"><td><strong>{{problem.name}}</strong></td><td>{{problem.type_name || 'Todos os tipos'}}</td><td>{{priorities[problem.priority]}}</td><td><span class="catalog-status" [class.inactive]="!problem.active">{{problem.active ? 'Ativo' : 'Inativo'}}</span></td><td><button mat-icon-button [disabled]="working" (click)="edit(problem)" [attr.aria-label]="'Editar ' + problem.name"><mat-icon>edit</mat-icon></button><button mat-icon-button [disabled]="working" (click)="toggleActive(problem)" [attr.aria-label]="(problem.active ? 'Desativar ' : 'Reativar ') + problem.name"><mat-icon>{{problem.active ? 'toggle_on' : 'toggle_off'}}</mat-icon></button></td></tr>
                    <tr *ngIf="!loading && !problemsValue.length"><td colspan="5" class="muted">Nenhum problema cadastrado.</td></tr>
                </tbody></table></div>
            </div>
        </section>
        <app-modal-formulario *ngIf="showForm" [titleValue]="currentEditId ? 'Editar problema' : 'Novo problema'" subtitulo="Defina uma opção clara para o operador e sua prioridade padrão." icone="report_problem" [busy]="working" (closedValue)="closeValue()">
            <p class="error" *ngIf="errorValue" role="alert">{{errorValue}}</p>
            <label><span>Problema *</span><input [(ngModel)]="form.name" maxlength="180" placeholder="Ex.: Equipamento não liga"></label>
            <label><span>Tipo de equipamento</span><select [(ngModel)]="form.equipmentTypeId"><option [ngValue]="null">Todos os tipos</option><option *ngFor="let type of typesValue" [ngValue]="type.id">{{type.name}}</option></select></label>
            <label><span>Prioridade padrão *</span><select [(ngModel)]="form.priority"><option value="BAIXA">Baixa</option><option value="MEDIA">Média</option><option value="ALTA">Alta</option><option value="CRITICA">Crítica</option></select></label>
            <p class="muted">Ao selecionar este problema, o operador recebe a prioridade definida acima.</p>
            <div modalActions class="modal-actions"><button type="button" [disabled]="working" (click)="closeValue()">Cancelar</button><button type="button" class="primary" [disabled]="working || form.name.trim().length < 5" (click)="save()">{{working ? 'Salvando...' : 'Salvar problema'}}</button></div>
        </app-modal-formulario>
    `,
    styles: [`
        .catalog-heading { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:20px; margin-bottom:24px; }
        h1 { margin-top:8px; } .catalog-status { display:inline-block; padding:5px 10px; border-radius:20px; background:#e7f7f0; color:#168c6d; font-size:12px; font-weight:600; }
        .catalog-status.inactive { background:#f1f3f5; color:#778092; } td strong { font-size:13px; } td { font-size:13px; } th { white-space:nowrap; }
    `]
})
export class ProblemTypes implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    private api = inject(Api);
    private httpValue = inject(HttpClient);
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    problemsValue: ProblemType[] = [];
    typesValue: {
        id: number;
        name: string;
    }[] = [];
    priorities = PRIORITY_LABELS;
    loading = false;
    working = false;
    showForm = false;
    currentEditId: number | null = null;
    messageValue = '';
    errorValue = '';
    form = this.initialForm();
    /** Cria valores iniciais independentes para cadastrar um problema do catálogo. */
    private initialForm() {
        return {
            name: '', equipmentTypeId: null as number | null, priority: 'MEDIA', active: true
        };
    }
    /** Consulta problemas e tipos de equipamento para montar a lista e o formulário. */
    ngOnInit() {
        this.loadData();
        this.api.typesValue().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.cdr.markForCheck())).subscribe({
            next: types => this.typesValue = types,
            error: () => this.errorValue = 'Não foi possível carregar os tipos de equipamento.'
        });
    }
    /** GET /api/problem-types inclui inativos para que possam ser reativados pelo cadastro. */
    loadData() {
        this.loading = true;
        this.api.problemTypes(undefined, true).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.loading = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: problems => this.problemsValue = problems,
            error: () => this.errorValue = 'Não foi possível carregar os problemas cadastrados.'
        });
    }
    /** Limpa o formulário e abre o modal de inclusão. */
    novoProblema() {
        if (this.working)
            return;
        this.form = this.initialForm();
        this.currentEditId = null;
        this.messageValue = this.errorValue = '';
        this.showForm = true;
    }
    /** Copia a opção escolhida para edição sem alterar a lista antes da confirmação. */
    edit(problem: ProblemType) {
        if (this.working)
            return;
        this.currentEditId = problem.id;
        this.form = {
            name: problem.name, equipmentTypeId: problem.equipment_type_id, priority: problem.priority, active: problem.active
        };
        this.errorValue = this.messageValue = '';
        this.showForm = true;
    }
    /** Fecha o formulário quando não há gravação em andamento. */
    closeValue() {
        if (!this.working) {
            this.showForm = false;
            this.currentEditId = null;
            this.errorValue = '';
            this.form = this.initialForm();
        }
    }
    /** Usa POST ou PATCH no catálogo e recarrega a lista após validar nome, tipo e prioridade no Django. */
    save() {
        if (this.working || this.form.name.trim().length < 5)
            return;
        this.working = true;
        this.errorValue = '';
        const payload = {
            ...this.form, name: this.form.name.trim()
        };
        const editing = this.currentEditId !== null;
        const request = this.currentEditId ? this.httpValue.patch('/api/problem-types/' + this.currentEditId, payload) : this.httpValue.post('/api/problem-types', payload);
        request.pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.working = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: () => {
                this.showForm = false;
                this.currentEditId = null;
                this.messageValue = editing ? 'Alterações salvas.' : '';
                if (!editing) this.registrationFeedback.created('Problema cadastrado com sucesso', payload.name);
                this.loadData();
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível salvar o problema.'
        });
    }
    /** PATCH no catálogo muda a situação ativa, preservando as OS que já usaram o problema. */
    toggleActive(problem: ProblemType) {
        if (this.working)
            return;
        this.working = true;
        this.errorValue = this.messageValue = '';
        this.httpValue.patch('/api/problem-types/' + problem.id, {
            active: !problem.active
        }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.working = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: () => {
                this.messageValue = problem.active ? 'Problema desativado.' : 'Problema reativado.';
                this.loadData();
            },
            error: failure => this.errorValue = failure.error?.error || 'Não foi possível alterar a situação.'
        });
    }
}
