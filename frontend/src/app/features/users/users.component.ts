/** Módulo usuarios: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatDialog } from '@angular/material/dialog';
import { ResetPasswordDialog } from './reset-password-dialog.component';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { Api, Line, Authentication } from '../../services';
type UserRole = 'ADMINISTRADOR' | 'TECNICO' | 'OPERADOR';
interface SystemUser {
    id: number;
    name: string;
    registration: string;
    role: UserRole;
    line_id: number | null;
    active: boolean;
}
interface UserForm {
    name: string;
    registration: string;
    password: string;
    role: UserRole | '';
    lineId: number | null;
}
@Component({
    standalone: true,
    imports: [
        FormModal,
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatSelectModule,
        MatIconModule,
    ],
    templateUrl: './users.component.html',
    styleUrl: './users.component.scss',
})
/** Gerencia contas, perfis, linha do operador, situação e senha através da API administrativa. */
export class Users implements OnInit {
    api = inject(Api);
    httpClient = inject(HttpClient);
    authentication = inject(Authentication);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    private dialogs = inject(MatDialog);
    lines: Line[] = [];
    users: SystemUser[] = [];
    form: UserForm = this.emptyForm();
    error = '';
    successMessage = '';
    search = '';
    formOpen = false;
    editingId: number | null = null;
    loading = false;
    loadingUsers = false;
    /** Consulta linhas e contas para montar o cadastro de usuários. */
    ngOnInit(): void {
        this.api
            .lines()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (lines) => (this.lines = lines),
                error: () =>
                    (this.error = 'Não foi possível carregar as linhas SMT.'),
            });
        this.loadData();
    }
    /** Retorna um formulário vazio sem reutilizar os dados da conta anterior. */
    private emptyForm(): UserForm {
        return {
            name: '',
            registration: '',
            password: '',
            role: '',
            lineId: null,
        };
    }
    /** GET /api/users carrega contas, normaliza IDs e trata erros de sessão/permissão. */
    loadData(): void {
        this.loadingUsers = true;
        this.error = '';
        this.api
            .users()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (users) => {
                    this.users = (users as SystemUser[]).map((user) => ({
                        ...user,
                        id: Number(user.id),
                        line_id:
                            user.line_id == null ? null : Number(user.line_id),
                    }));
                    this.loadingUsers = false;
                    this.changeDetector.detectChanges();
                },
                error: (err) => {
                    this.loadingUsers = false;
                    if (err.status === 401) {
                        this.error = 'Sessão expirada. Faça login novamente.';
                    } else if (err.status === 403) {
                        this.error =
                            'Você não possui permissão para consultar usuários.';
                    } else {
                        this.error = 'Não foi possível carregar os usuários.';
                    }
                    console.error('Erro ao carregar usuários:', err);
                    this.changeDetector.detectChanges();
                },
            });
    }
    /** Converte o ID da linha no nome exibido na tabela de usuários. */
    getLine(id: number | null): string {
        if (!id) return '—';
        return this.lines.find((x) => x.id === id)?.name || '—';
    }
    /** Filtra a lista local por nome, matrícula ou perfil sem chamar a API a cada tecla. */
    get usersFiltered(): SystemUser[] {
        const term = this.search.trim().toLowerCase();
        if (!term) return this.users;
        return this.users.filter(
            (user) =>
                user.name.toLowerCase().includes(term) ||
                user.registration.toLowerCase().includes(term) ||
                user.role.toLowerCase().includes(term)
        );
    }
    /** Prepara cadastro vazio e abre o modal de nova conta. */
    newUser(): void {
        this.form = this.emptyForm();
        this.editingId = null;
        this.error = '';
        this.successMessage = '';
        this.formOpen = true;
    }
    /** Copia os dados públicos da conta; a senha existente nunca é retornada nem preenchida. */
    editUser(user: SystemUser): void {
        this.form = {
            name: user.name,
            registration: user.registration,
            password: '',
            role: user.role,
            lineId: user.line_id,
        };
        this.editingId = user.id;
        this.error = '';
        this.successMessage = '';
        this.formOpen = true;
    }
    /** Descarta os campos locais e fecha o cadastro. */
    cancel(): void {
        this.form = this.emptyForm();
        this.editingId = null;
        this.formOpen = false;
        this.error = '';
    }
    /** POST cria a conta com senha inicial; PATCH altera dados públicos da conta existente. O servidor aplica as regras de acesso. */
    register(): void {
        if (this.loading) return;
        this.error = '';
        this.successMessage = '';
        if (
            !this.form.name.trim() ||
            !this.form.registration.trim() ||
            !this.form.role
        ) {
            this.error = 'Preencha os campos obrigatórios.';
            return;
        }
        if (this.form.role === 'OPERADOR' && !this.form.lineId) {
            this.error = 'Selecione uma linha SMT para o operador.';
            return;
        }
        if (this.editingId === null && this.form.password.length < 12) {
            this.error =
                'A senha inicial deve possuir no mínimo 12 caracteres.';
            return;
        }
        this.loading = true;
        const dataSubmission = {
            name: this.form.name.trim(),
            registration: this.form.registration.trim(),
            role: this.form.role,
            lineId: this.form.role === 'OPERADOR' ? this.form.lineId : null,
        };
        if (this.editingId !== null) {
            this.httpClient
                .patch(`/api/users/${this.editingId}`, dataSubmission)
                .pipe(finalize(() => this.changeDetector.markForCheck()))
                .subscribe({
                    next: () => this.finish('Usuário atualizado com sucesso.'),
                    error: (e) =>
                        this.handleFailure(e, 'Erro ao atualizar usuário.'),
                });
        } else {
            this.httpClient
                .post('/api/users', {
                    ...dataSubmission,
                    password: this.form.password,
                })
                .pipe(finalize(() => this.changeDetector.markForCheck()))
                .subscribe({
                    next: () => this.finish('Usuário cadastrado com sucesso.'),
                    error: (e) =>
                        this.handleFailure(e, 'Erro ao cadastrar usuário.'),
                });
        }
    }
    // Confirma a mudança de situação e envia um booleano; a API também impede autodesativação.
    /** PATCH /api/users/:id/status ativa/desativa a conta, bloqueando a autodesativação também no Django. */
    toggleActive(user: SystemUser): void {
        const action = user.active ? 'desativar' : 'reativar';
        if (user.id === this.authentication.user()?.id && user.active) {
            this.error = 'Você não pode desativar sua própria conta.';
            return;
        }
        if (!confirm(`Deseja realmente ${action} o usuário ${user.name}?`)) {
            return;
        }
        this.error = '';
        this.successMessage = '';
        this.httpClient
            .patch(`/api/users/${user.id}/status`, {
                active: !user.active,
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.successMessage = user.active
                        ? 'Usuário desativado com sucesso.'
                        : 'Usuário reativado com sucesso.';
                    this.loadData();
                },
                error: (e) =>
                    this.handleFailure(e, `Erro ao ${action} usuário.`),
            });
    }
    // Coleta a nova senha pelo diálogo e pede sua validação e gravação na API.
    /** Recebe a nova senha pelo diálogo e envia PATCH ao endpoint protegido de redefinição. */
    resetPassword(user: SystemUser): void {
        const dialogRef = this.dialogs.open(ResetPasswordDialog, {
            width: '680px',
            panelClass: 'mantis-form-dialog',
            backdropClass: 'sector-dialog-backdrop',
            maxWidth: '95vw',
            disableClose: true,
            data: {
                name: user.name,
            },
        });
        dialogRef
            .afterClosed()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe((password?: string) => {
                if (!password) {
                    return;
                }
                this.error = '';
                this.successMessage = '';
                this.httpClient
                    .patch(`/api/users/${user.id}/password`, {
                        password,
                    })
                    .pipe(finalize(() => this.changeDetector.markForCheck()))
                    .subscribe({
                        next: () => {
                            this.successMessage =
                                'Senha redefinida com sucesso.';
                            this.changeDetector.detectChanges();
                        },
                        error: (err) => {
                            this.handleFailure(
                                err,
                                'Erro ao redefinir a senha.'
                            );
                            this.changeDetector.detectChanges();
                        },
                    });
            });
    }
    /** Finaliza a gravação bem-sucedida, fecha o modal e consulta novamente as contas. */
    private finish(message: string): void {
        this.loading = false;
        this.formOpen = false;
        this.editingId = null;
        this.form = this.emptyForm();
        this.successMessage = message;
        this.loadData();
    }
    /** Libera o estado de carregamento e exibe a mensagem de erro devolvida pela API. */
    private handleFailure(failure: any, fallback: string): void {
        this.loading = false;
        this.error = failure.error?.error || fallback;
    }
}
