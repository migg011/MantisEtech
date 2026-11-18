import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo setores: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { Component, inject, OnInit, ChangeDetectorRef, TemplateRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { Auth, Api } from '../../services';
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink, MatButtonModule, MatIconModule, MatDialogModule],
    templateUrl: './sectors.component.html',
    styleUrl: './sectors.component.scss'
})
/** Lista setores e controla cadastros; o Django valida permissões e bloqueia a desativação de setores usados. */
export class Sectors implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    api = inject(Api);
    authValue = inject(Auth);
    httpValue = inject(HttpClient);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    sectors: {
        id: number;
        code: string;
        name: string;
        description: string;
    }[] = [];
    currentEditId: number | null = null;
    nameValue = '';
    descriptionValue = '';
    costCenter = '';
    errorValue = '';
    success = '';
    working = false;
    @ViewChild('sectorDialog')
    sectorDialog!: TemplateRef<unknown>;
    private dialog = inject(MatDialog);
    private dialogRefValue?: MatDialogRef<unknown>;
    /** Informa ao template se já existe um modal de setor aberto. */
    get openDialog() {
        return !!this.dialogRefValue;
    }
    /** Abre o template como MatDialog e impede fechamento durante gravação; ao fechar limpa o estado local. */
    private openSectorDialog() {
        this.dialogRefValue = this.dialog.open(this.sectorDialog, {
            width: '680px',
            maxWidth: 'calc(100vw - 32px)',
            panelClass: 'sector-dialog-panel',
            backdropClass: 'sector-dialog-backdrop',
            autoFocus: '#sector-name',
            ariaLabelledBy: 'sector-dialog-title',
            closePredicate: () => !this.working
        });
        this.dialogRefValue.afterClosed().subscribe(() => {
            this.cancelEdit();
            this.dialogRefValue = undefined;
            this.cdr.markForCheck();
        });
    }
    /** Carrega os setores ao entrar na tela. */
    ngOnInit() {
        this.loadData();
    }
    /** GET /api/sectors: atualiza a lista de setores ativos e as mensagens da interface. */
    loadData() {
        this.api.sectors().subscribe({
            next: sectors => {
                this.sectors = sectors;
                this.errorValue = '';
                this.cdr.markForCheck();
            },
            error: () => {
                this.errorValue = 'Não foi possível carregar setores.';
                this.cdr.markForCheck();
            }
        });
    }
    // Abre o modal com um formulário vazio para cadastro.
    /** Abre cadastro vazio somente para administrador e evita modais duplicados. */
    openSectorForm() {
        if (this.working || this.dialogRefValue || this.authValue.userValue()?.role !== 'ADMINISTRADOR')
            return;
        this.cancelEdit();
        this.success = '';
        this.openSectorDialog();
    }
    // Fecha o formulário e limpa a edição
    /** Pede o fechamento do modal quando não há requisição de gravação em andamento. */
    closeSectorForm() {
        if (this.working)
            return;
        this.dialogRefValue?.close();
    }
    // Editar setor
    /** Copia nome e descrição do setor para o modal de edição. */
    edit(sectorValue: {
        id: number;
        cost_center?: string;
        name: string;
        description: string;
    }) {
        if (this.working || this.dialogRefValue || this.authValue.userValue()?.role !== 'ADMINISTRADOR')
            return;
        this.currentEditId = sectorValue.id;
        this.nameValue = sectorValue.name;
        this.costCenter = sectorValue.cost_center || '';
        this.descriptionValue = sectorValue.description || '';
        this.errorValue = '';
        this.success = '';
        this.openSectorDialog();
    }
    /** Reinicia os campos de edição sem enviar mudanças ao banco. */
    cancelEdit() {
        this.currentEditId = null;
        this.nameValue = '';
        this.descriptionValue = '';
        this.costCenter = '';
        this.errorValue = '';
    }
    // Cadastrar ou atualizar setor
    /** POST cria e PATCH altera o setor; o modal fecha somente quando o Django confirma a gravação. */
    save() {
        if (this.authValue.userValue()?.role !== 'ADMINISTRADOR' ||
            this.working ||
            this.nameValue.trim().length < 2)
            return;
        this.errorValue = '';
        this.success = '';
        this.working = true;
        const editing = this.currentEditId !== null;
        const name = this.nameValue.trim();
        const request = editing
            ? this.httpValue.patch(`/api/sectors/${this.currentEditId}`, {
                name: this.nameValue.trim(),
                description: this.descriptionValue,
                costCenter: this.costCenter.trim()
            })
            : this.httpValue.post('/api/sectors', {
                name: this.nameValue.trim(),
                description: this.descriptionValue,
                costCenter: this.costCenter.trim()
            });
        request.subscribe({
            next: () => {
                this.working = false;
                this.dialogRefValue?.close();
                if (editing) this.success = 'Alterações salvas.';
                else this.registrationFeedback.created('Setor cadastrado com sucesso', name);
                this.loadData();
                this.cdr.markForCheck();
            },
            error: e => {
                this.working = false;
                this.errorValue = e.error?.error ||
                    'Não foi possível salvar o setor.';
                this.cdr.markForCheck();
            }
        });
    }
    // Excluir setor
    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE solicita desativação do setor; a API recusa setores ainda vinculados a linhas ou máquinas. */
    deactivate(sectorValue: {
        id: number;
        name: string;
    }) {
        if (this.authValue.userValue()?.role !== 'ADMINISTRADOR')
            return;
        if (this.working ||
            !window.confirm(`Deseja excluir o setor "${sectorValue.name}"? ` +
                'Esta operação não apagará o histórico. ' +
                'Setores vinculados a linhas não poderão ser excluídos.'))
            return;
        this.errorValue = '';
        this.success = '';
        this.working = true;
        this.httpValue.delete(`/api/sectors/${sectorValue.id}`)
            .subscribe({
            next: () => {
                this.working = false;
                if (this.currentEditId === sectorValue.id) {
                    this.cancelEdit();
                    this.dialogRefValue?.close();
                }
                this.success =
                    'Setor excluído da listagem.';
                this.loadData();
                this.cdr.markForCheck();
            },
            error: e => {
                this.working = false;
                this.errorValue = e.error?.error ||
                    'Não foi possível excluir o setor.';
                this.cdr.markForCheck();
            }
        });
    }
}
