/** Módulo setores: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    Component,
    inject,
    OnInit,
    ChangeDetectorRef,
    TemplateRef,
    ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import {
    MatDialog,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import { Authentication, Api } from '../../services';
@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        RouterLink,
        MatButtonModule,
        MatIconModule,
        MatDialogModule,
    ],
    templateUrl: './sectors.component.html',
    styleUrl: './sectors.component.scss',
})
/** Lista setores e controla cadastros; o Django valida permissões e bloqueia a desativação de setores usados. */
export class Sectors implements OnInit {
    api = inject(Api);
    authentication = inject(Authentication);
    httpClient = inject(HttpClient);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    sectors: {
        id: number;
        code: string;
        name: string;
        description: string;
    }[] = [];
    editingId: number | null = null;
    name = '';
    description = '';
    error = '';
    successMessage = '';
    processing = false;
    @ViewChild('sectorDialog')
    sectorDialog!: TemplateRef<unknown>;
    private dialogs = inject(MatDialog);
    private dialogReference?: MatDialogRef<unknown>;
    /** Informa ao template se já existe um modal de setor aberto. */
    get openDialog() {
        return !!this.dialogReference;
    }
    /** Abre o template como MatDialog e impede fechamento durante gravação; ao fechar limpa o estado local. */
    private openSectorDialog() {
        this.dialogReference = this.dialogs.open(this.sectorDialog, {
            width: '680px',
            maxWidth: 'calc(100vw - 32px)',
            panelClass: 'sector-dialog-panel',
            backdropClass: 'sector-dialog-backdrop',
            autoFocus: '#sector-name',
            ariaLabelledBy: 'sector-dialog-title',
            closePredicate: () => !this.processing,
        });
        this.dialogReference.afterClosed().subscribe(() => {
            this.cancelEditing();
            this.dialogReference = undefined;
            this.changeDetector.markForCheck();
        });
    }
    /** Carrega os setores ao entrar na tela. */
    ngOnInit() {
        this.loadData();
    }
    /** GET /api/sectors: atualiza a lista de setores ativos e as mensagens da interface. */
    loadData() {
        this.api.sectors().subscribe({
            next: (sectors) => {
                this.sectors = sectors;
                this.error = '';
                this.changeDetector.markForCheck();
            },
            error: () => {
                this.error = 'Não foi possível carregar setores.';
                this.changeDetector.markForCheck();
            },
        });
    }
    // Abre o modal com um formulário vazio para cadastro.
    /** Abre cadastro vazio somente para administrador e evita modais duplicados. */
    openFormSector() {
        if (
            this.processing ||
            this.dialogReference ||
            this.authentication.user()?.role !== 'ADMINISTRADOR'
        )
            return;
        this.cancelEditing();
        this.successMessage = '';
        this.openSectorDialog();
    }
    // Fecha o formulário e limpa a edição
    /** Pede o fechamento do modal quando não há requisição de gravação em andamento. */
    closeFormSector() {
        if (this.processing) return;
        this.dialogReference?.close();
    }
    // Editar setor
    /** Copia nome e descrição do setor para o modal de edição. */
    edit(sector: { id: number; name: string; description: string }) {
        if (
            this.processing ||
            this.dialogReference ||
            this.authentication.user()?.role !== 'ADMINISTRADOR'
        )
            return;
        this.editingId = sector.id;
        this.name = sector.name;
        this.description = sector.description || '';
        this.error = '';
        this.successMessage = '';
        this.openSectorDialog();
    }
    /** Reinicia os campos de edição sem enviar mudanças ao banco. */
    cancelEditing() {
        this.editingId = null;
        this.name = '';
        this.description = '';
        this.error = '';
    }
    // Cadastrar ou atualizar setor
    /** POST cria e PATCH altera o setor; o modal fecha somente quando o Django confirma a gravação. */
    save() {
        if (
            this.authentication.user()?.role !== 'ADMINISTRADOR' ||
            this.processing ||
            this.name.trim().length < 2
        )
            return;
        this.error = '';
        this.successMessage = '';
        this.processing = true;
        const editing = this.editingId !== null;
        const requestHttp = editing
            ? this.httpClient.patch(`/api/sectors/${this.editingId}`, {
                  name: this.name.trim(),
                  description: this.description,
              })
            : this.httpClient.post('/api/sectors', {
                  name: this.name.trim(),
                  description: this.description,
              });
        requestHttp.subscribe({
            next: () => {
                this.processing = false;
                this.dialogReference?.close();
                this.successMessage = editing
                    ? 'Setor atualizado com sucesso.'
                    : 'Setor cadastrado com sucesso.';
                this.loadData();
                this.changeDetector.markForCheck();
            },
            error: (e) => {
                this.processing = false;
                this.error =
                    e.error?.error || 'Não foi possível salvar o setor.';
                this.changeDetector.markForCheck();
            },
        });
    }
    // Excluir setor
    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE solicita desativação do setor; a API recusa setores ainda vinculados a linhas ou máquinas. */
    deactivate(sector: { id: number; name: string }) {
        if (this.authentication.user()?.role !== 'ADMINISTRADOR') return;
        if (
            this.processing ||
            !window.confirm(
                `Deseja excluir o setor "${sector.name}"? ` +
                    'Esta operação não apagará o histórico. ' +
                    'Setores vinculados a linhas não poderão ser excluídos.'
            )
        )
            return;
        this.error = '';
        this.successMessage = '';
        this.processing = true;
        this.httpClient.delete(`/api/sectors/${sector.id}`).subscribe({
            next: () => {
                this.processing = false;
                if (this.editingId === sector.id) {
                    this.cancelEditing();
                    this.dialogReference?.close();
                }
                this.successMessage = 'Setor excluído da listagem.';
                this.loadData();
                this.changeDetector.markForCheck();
            },
            error: (e) => {
                this.processing = false;
                this.error =
                    e.error?.error || 'Não foi possível excluir o setor.';
                this.changeDetector.markForCheck();
            },
        });
    }
}
