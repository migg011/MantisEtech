import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo usuarios: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatDialog } from '@angular/material/dialog';
import { ResetPasswordDialogComponent } from './reset-password-dialog.component';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { Api, Auth } from '../../services';
type UserRole = 'ADMINISTRADOR' | 'TECNICO' | 'OPERADOR';
interface SystemUser {
    id: number;
    name: string;
    registration: string;
    role: UserRole;
    active: boolean;
    sector_id: number | null;
}
interface UserForm {
    name: string;
    registration: string;
    password: string;
    role: UserRole | '';
    sectorId: number | null;
}
@Component({
    standalone: true,
    imports: [FormModal,
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatSelectModule,
        MatIconModule
    ],
    templateUrl: './users.component.html',
    styleUrl: './users.component.scss'
})
/** Gerencia contas, perfis, situação e senha através da API administrativa. */
export class Users implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    api = inject(Api);
    httpValue = inject(HttpClient);
    authValue = inject(Auth);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    private dialog = inject(MatDialog);
    private route = inject(ActivatedRoute);
    sectorId = Number(this.route.snapshot.paramMap.get('id')) || null;
    sectors: {id: number; name: string}[] = [];
    usersValue: SystemUser[] = [];
    form: UserForm = this.emptyForm();
    errorValue = '';
    success = '';
    search = '';
    showForm = false;
    currentEditId: number | null = null;
    loading = false;
    loadingUsers = false;
    /** Consulta contas para montar o cadastro de usuários. */
    ngOnInit(): void {
        this.loadData();
        this.api.sectors().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: sectors => this.sectors = sectors,
            error: () => this.errorValue = 'Não foi possível carregar os setores.'
        });
    }
    /** Retorna um formulário vazio sem reutilizar os dados da conta anterior. */
    private emptyForm(): UserForm {
        return {
            name: '',
            registration: '',
            password: '',
            role: '',
            sectorId: this.sectorId
        };
    }
    /** GET /api/users carrega contas, normaliza IDs e trata erros de sessão/permissão. */
    loadData(): void {
        this.loadingUsers = true;
        this.errorValue = '';
        this.api.usersValue().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: users => {
                this.usersValue = (users as SystemUser[]).map(userValue => ({
                    ...userValue,
                    id: Number(userValue.id)
                }));
                this.loadingUsers = false;
                this.cdr.detectChanges();
            },
            error: err => {
                this.loadingUsers = false;
                if (err.status === 401) {
                    this.errorValue = 'Sessão expirada. Faça login novamente.';
                }
                else if (err.status === 403) {
                    this.errorValue = 'Você não possui permissão para consultar usuários.';
                }
                else {
                    this.errorValue = 'Não foi possível carregar os usuários.';
                }
                console.error('Erro ao carregar usuários:', err);
                this.cdr.detectChanges();
            }
        });
    }
    /** Filtra a lista local por nome, matrícula ou perfil sem chamar a API a cada tecla. */
    get filteredUsers(): SystemUser[] {
        const users = this.sectorId ? this.usersValue.filter(user => user.sector_id === this.sectorId) : this.usersValue;
        const term = this.search.trim().toLowerCase();
        if (!term)
            return users;
        return users.filter(userValue => userValue.name.toLowerCase().includes(term) ||
            userValue.registration.toLowerCase().includes(term) ||
            userValue.role.toLowerCase().includes(term));
    }
    sectorName(id: number | null) {
        return this.sectors.find(sector => sector.id === id)?.name || 'Sem setor';
    }
    /** Prepara cadastro vazio e abre o modal de nova conta. */
    newUser(): void {
        this.form = this.emptyForm();
        this.currentEditId = null;
        this.errorValue = '';
        this.success = '';
        this.showForm = true;
    }
    /** Copia os dados públicos da conta; a senha existente nunca é retornada nem preenchida. */
    editUser(userValue: SystemUser): void {
        this.form = {
            name: userValue.name,
            registration: userValue.registration,
            password: '',
            role: userValue.role,
            sectorId: userValue.sector_id
        };
        this.currentEditId = userValue.id;
        this.errorValue = '';
        this.success = '';
        this.showForm = true;
    }
    /** Descarta os campos locais e fecha o cadastro. */
    cancel(): void {
        this.form = this.emptyForm();
        this.currentEditId = null;
        this.showForm = false;
        this.errorValue = '';
    }
    /** POST cria a conta com senha inicial; PATCH altera dados públicos da conta existente. O servidor aplica as regras de acesso. */
    cadastrar(): void {
        if (this.loading)
            return;
        this.errorValue = '';
        this.success = '';
        if (!this.form.name.trim() || !this.form.registration.trim() || !this.form.role) {
            this.errorValue = 'Preencha os campos obrigatórios.';
            return;
        }
        if (this.form.role !== 'ADMINISTRADOR' && !this.form.sectorId) {
            this.errorValue = 'Selecione o setor do operador ou técnico.';
            return;
        }
        if (this.currentEditId === null && this.form.password.length < 12) {
            this.errorValue = 'A senha inicial deve possuir no mínimo 12 caracteres.';
            return;
        }
        this.loading = true;
        const payload = {
            name: this.form.name.trim(),
            registration: this.form.registration.trim(),
            role: this.form.role,
            sectorId: this.form.role === 'ADMINISTRADOR' ? null : this.form.sectorId
        };
        if (this.currentEditId !== null) {
            this.httpValue.patch(`/api/users/${this.currentEditId}`, payload).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: () => this.finish('Alterações salvas.'),
                error: e => this.handleFailure(e, 'Erro ao atualizar usuário.')
            });
        }
        else {
            this.httpValue.post('/api/users', {
                ...payload,
                password: this.form.password
            }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: () => {
                    this.finish('');
                    this.registrationFeedback.created('Usuário cadastrado com sucesso', payload.name);
                },
                error: e => this.handleFailure(e, 'Erro ao cadastrar usuário.')
            });
        }
    }
    // Confirma a mudança de situação e envia um booleano; a API também impede autodesativação.
    /** PATCH /api/users/:id/status ativa/desativa a conta, bloqueando a autodesativação também no Django. */
    toggleActive(userValue: SystemUser): void {
        const action = userValue.active ? 'desativar' : 'reativar';
        if (userValue.id === this.authValue.userValue()?.id && userValue.active) {
            this.errorValue = 'Você não pode desativar sua própria conta.';
            return;
        }
        if (!confirm(`Deseja realmente ${action} o usuário ${userValue.name}?`)) {
            return;
        }
        this.errorValue = '';
        this.success = '';
        this.httpValue.patch(`/api/users/${userValue.id}/status`, {
            active: !userValue.active
        }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.success = userValue.active
                    ? 'Usuário desativado com sucesso.'
                    : 'Usuário reativado com sucesso.';
                this.loadData();
            },
            error: e => this.handleFailure(e, `Erro ao ${action} usuário.`)
        });
    }
    // Coleta a nova senha pelo diálogo e pede sua validação e gravação na API.
    /** Recebe a nova senha pelo diálogo e envia PATCH ao endpoint protegido de redefinição. */
    resetPassword(userValue: SystemUser): void {
        const dialogRef = this.dialog.open(ResetPasswordDialogComponent, {
            width: '680px',
            panelClass: 'mantis-form-dialog',
            backdropClass: 'sector-dialog-backdrop',
            maxWidth: '95vw',
            disableClose: true,
            data: {
                name: userValue.name
            }
        });
        dialogRef.afterClosed().pipe(finalize(() => this.cdr.markForCheck())).subscribe((password?: string) => {
            if (!password) {
                return;
            }
            this.errorValue = '';
            this.success = '';
            this.httpValue.patch(`/api/users/${userValue.id}/password`, {
                password
            }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: () => {
                    this.success = 'Senha redefinida com sucesso.';
                    this.cdr.detectChanges();
                },
                error: err => {
                    this.handleFailure(err, 'Erro ao redefinir a senha.');
                    this.cdr.detectChanges();
                }
            });
        });
    }
    /** Finaliza a gravação bem-sucedida, fecha o modal e consulta novamente as contas. */
    private finish(messageValue: string): void {
        this.loading = false;
        this.showForm = false;
        this.currentEditId = null;
        this.form = this.emptyForm();
        this.success = messageValue;
        this.loadData();
    }
    /** Libera o estado de carregamento e exibe a mensagem de erro devolvida pela API. */
    private handleFailure(failure: any, fallback: string): void {
        this.loading = false;
        this.errorValue = failure.error?.error || fallback;
    }
}
