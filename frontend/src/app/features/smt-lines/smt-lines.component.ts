import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo linhas-smt: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import { Component, inject, OnInit, signal, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterOutlet, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatCardModule } from '@angular/material/card';
import { Auth, Api, Line, Equipment as EquipmentData } from '../../services';
const UI = [FormModal, CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatIconModule, MatSelectModule, MatToolbarModule, MatDialogModule, MatCardModule, RouterLink];
@Component({
    standalone: true,
    imports: UI,
    templateUrl: './smt-lines.component.html',
    styleUrl: './smt-lines.component.scss'
})
/** Controla linhas e montagem; a API confere setor, disponibilidade e posição e registra o histórico. */
export class Lines implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    api = inject(Api);
    routeValue = inject(ActivatedRoute);
    httpValue = inject(HttpClient);
    linesValue: Line[] = [];
    sectors: {
        id: number;
        name: string;
    }[] = [];
    sectorIdValue: number | null = null;
    assemblyLineId: number | null = null;
    assemblyEquipmentId: number | null = null;
    assemblyPosition = 1;
    availableEquipment: EquipmentData[] = [];
    assignedEquipment: EquipmentData[] = [];
    assemblyError = '';
    assemblySuccess = '';
    working = false;
    /** Converte o comprimento agregado da linha de milímetros para metros. */
    lineDimensions(l: Line) {
        return Number(l.length_mm || 0) / 1000;
    }
    nameValue = '';
    descriptionValue = '';
    errorValue = '';
    /** Identifica o setor na navegação e carrega linhas, setores e equipamentos da montagem. */
    ngOnInit() {
        this.routeValue.queryParamMap.pipe(finalize(() => this.cdr.markForCheck())).subscribe(paramsValue => {
            this.sectorIdValue = Number(this.routeValue.snapshot.paramMap.get('id') || paramsValue.get('sectorId')) || null;
            this.assemblyLineId = null;
            this.api.sectors().pipe(finalize(() => this.cdr.markForCheck())).subscribe(x => this.sectors = x);
            this.loadData();
            this.loadLayout();
        });
    }
    /** Obtém o nome legível do setor pelo ID selecionado. */
    sectorName(): string {
        if (!this.sectorIdValue) {
            return 'Nenhum setor selecionado';
        }
        const sectorValue = this.sectors.find(s => Number(s.id) === Number(this.sectorIdValue));
        return sectorValue?.name || 'Setor não encontrado';
    }
    /** Exibe somente as linhas pertencentes ao setor atual. */
    sectorLines() {
        return this.linesValue.filter(l => l.sector_id === this.sectorIdValue);
    }
    /** GET /api/lines: recarrega as linhas e seus totais de equipamentos/comprimento. */
    loadData() {
        this.api.linesValue().pipe(finalize(() => this.cdr.markForCheck())).subscribe(x => this.linesValue = x);
    }
    // Busca máquinas livres no setor e máquinas já posicionadas na linha escolhida.
    /** Consulta máquinas disponíveis no setor e as alocadas na linha; sugere a próxima posição livre após a última. */
    loadLayout() {
        this.assemblyEquipmentId = null;
        if (!this.sectorIdValue) {
            this.availableEquipment = [];
            this.assignedEquipment = [];
            return;
        }
        this.httpValue.get<EquipmentData[]>('/api/equipment?available=true&sectorId=' + this.sectorIdValue).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.availableEquipment = x,
            error: () => this.assemblyError = 'Falha ao carregar repositório'
        });
        if (this.assemblyLineId)
            this.api.machinesValue(this.assemblyLineId).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: x => {
                    this.assignedEquipment = x;
                    this.assemblyPosition = Math.max(0, ...x.map(e => Number(e.position) || 0)) + 1;
                }, error: () => this.assemblyError = 'Falha ao carregar linha'
            });
        else
            this.assignedEquipment = [];
    }
    /** Soma o comprimento das máquinas carregadas na montagem e converte para metros. */
    metrosAlocados() {
        return this.assignedEquipment.reduce((sum, e) => sum + Number(e.length_mm || 0), 0) / 1000;
    }
    // Envia equipamento e posição para validação e gravação transacional da montagem.
    /** POST /api/lines/:id/equipment: envia máquina e posição; o serviço Django valida e grava montagem e histórico em transação. */
    alocar() {
        if (!this.assemblyLineId || !this.assemblyEquipmentId || !Number.isInteger(Number(this.assemblyPosition)) || Number(this.assemblyPosition) < 1)
            return;
        this.assemblyError = '';
        this.assemblySuccess = '';
        this.working = true;
        this.httpValue.post(`/api/lines/${this.assemblyLineId}/equipment`, {
            equipmentId: this.assemblyEquipmentId,
            position: Number(this.assemblyPosition)
        }).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.working = false;
                this.assemblySuccess = 'Equipamento alocado com sucesso.';
                this.loadLayout();
                this.loadData();
            },
            error: e => {
                this.working = false;
                this.assemblyError = e.error?.error || 'Erro ao alocar equipamento';
            }
        });
    }
    // Devolve a máquina ao repositório sem excluir seu cadastro ou suas ordens.
    /** DELETE da alocação devolve a máquina ao repositório; não exclui a máquina nem suas OS. */
    liberar(e: EquipmentData) {
        if (!this.assemblyLineId || !confirm('Devolver este equipamento ao repositório?'))
            return;
        this.assemblyError = '';
        this.assemblySuccess = '';
        this.working = true;
        this.httpValue.delete(`/api/lines/${this.assemblyLineId}/equipment/${e.id}`).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.working = false;
                this.assemblySuccess = 'Equipamento devolvido ao repositório.';
                this.loadLayout();
                this.loadData();
            },
            error: err => {
                this.working = false;
                this.assemblyError = err.error?.error || 'Erro ao remover equipamento';
            }
        });
    }
    // Solicita retirada de todas as máquinas; a API preserva cadastros e registra o histórico.
    /** POST /api/lines/:id/dismantle: pede a retirada de todas as máquinas e recarrega a composição. */
    desmontar() {
        if (!this.assemblyLineId || !confirm('Desmontar esta linha e devolver TODAS as máquinas ao repositório? Os cadastros e as OS serão preservados.'))
            return;
        this.assemblyError = '';
        this.assemblySuccess = '';
        this.working = true;
        this.httpValue.post<{
            released: number;
        }>(`/api/lines/${this.assemblyLineId}/dismantle`, {}).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: r => {
                this.working = false;
                this.assemblySuccess = `Linha desmontada. ${r.released} equipamento(s) devolvido(s).`;
                this.loadLayout();
                this.loadData();
            },
            error: e => {
                this.working = false;
                this.assemblyError = e.error?.error || 'Erro ao desmontar linha';
            }
        });
    }
    showForm = false;
    registering = false;
    editingLineId: number | null = null;
    lineMessage = '';
    /** Reutiliza o formulário para editar apenas os dados de identificação da linha. */
    editLine(lineValue: Line) {
        if (this.registering) return;
        this.editingLineId = lineValue.id;
        this.nameValue = lineValue.name;
        this.descriptionValue = lineValue.description || '';
        this.errorValue = this.lineMessage = '';
        this.showForm = true;
    }
    /** Limpa nome, descrição e erro antes de abrir o cadastro de linha. */
    openLineForm() {
        if (this.registering) return;
        this.editingLineId = null;
        this.lineMessage = '';
        this.nameValue = this.descriptionValue = this.errorValue = '';
        this.showForm = true;
    }
    /** POST cria a linha; PATCH edita nome/descrição mantendo o mesmo ID e a montagem. */
    cadastrar() {
        if (this.registering || !this.sectorIdValue || this.nameValue.trim().length < 2)
            return;
        this.registering = true;
        this.errorValue = '';
        const editMode = this.editingLineId !== null;
        const dataValue = {
            name: this.nameValue.trim(),
            description: this.descriptionValue
        };
        const req = editMode ? this.httpValue.patch(`/api/lines/${this.editingLineId}`, dataValue) : this.httpValue.post('/api/lines', {...dataValue, sectorId: this.sectorIdValue});
        req.pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: () => {
                this.registering = false;
                this.showForm = false;
                this.nameValue = this.descriptionValue = '';
                this.errorValue = '';
                this.editingLineId = null;
                this.lineMessage = editMode ? 'Alterações salvas.' : '';
                if (!editMode) this.registrationFeedback.created('Linha cadastrada com sucesso', dataValue.name);
                this.loadData();
            }, error: e => {
                this.registering = false;
                this.errorValue = e.error?.error || 'Erro ao salvar';
            }
        });
    }
}
