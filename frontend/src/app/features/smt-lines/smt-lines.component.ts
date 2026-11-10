/** Módulo linhas-smt: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import {
    Component,
    inject,
    OnInit,
    signal,
    ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
    Router,
    RouterLink,
    RouterOutlet,
    ActivatedRoute,
} from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import {
    MatDialog,
    MatDialogModule,
    MatDialogRef,
    MAT_DIALOG_DATA,
} from '@angular/material/dialog';
import { MatCardModule } from '@angular/material/card';
import {
    Authentication,
    Api,
    Line,
    Equipment as EquipmentData,
} from '../../services';
const UI_MODULES = [
    FormModal,
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatSelectModule,
    MatToolbarModule,
    MatDialogModule,
    MatCardModule,
    RouterLink,
];
@Component({
    standalone: true,
    imports: UI_MODULES,
    templateUrl: './smt-lines.component.html',
    styleUrl: './smt-lines.component.scss',
})
/** Controla linhas e montagem; a API confere setor, disponibilidade e posição e registra o histórico. */
export class SmtLines implements OnInit {
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    api = inject(Api);
    route = inject(ActivatedRoute);
    httpClient = inject(HttpClient);
    lines: Line[] = [];
    sectors: {
        id: number;
        name: string;
    }[] = [];
    idSector: number | null = null;
    idLineAssembly: number | null = null;
    idEquipmentAssembly: number | null = null;
    positionAssembly = 1;
    equipmentAvailable: EquipmentData[] = [];
    equipmentAllocated: EquipmentData[] = [];
    errorAssembly = '';
    successMessageAssembly = '';
    processing = false;
    /** Converte o comprimento agregado da linha de milímetros para metros. */
    dimensionsLines(l: Line) {
        return Number(l.length_mm || 0) / 1000;
    }
    name = '';
    description = '';
    error = '';
    /** Identifica o setor na navegação e carrega linhas, setores e equipamentos da montagem. */
    ngOnInit() {
        this.route.queryParamMap
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe((parameters) => {
                this.idSector =
                    Number(
                        this.route.snapshot.paramMap.get('id') ||
                            parameters.get('sectorId')
                    ) || null;
                this.idLineAssembly = null;
                this.api
                    .sectors()
                    .pipe(finalize(() => this.changeDetector.markForCheck()))
                    .subscribe((x) => (this.sectors = x));
                this.loadData();
                this.loadAssembly();
            });
    }
    /** Obtém o nome legível do setor pelo ID selecionado. */
    nameSector(): string {
        if (!this.idSector) {
            return 'Nenhum setor selecionado';
        }
        const sector = this.sectors.find(
            (s) => Number(s.id) === Number(this.idSector)
        );
        return sector?.name || 'Setor não encontrado';
    }
    /** Exibe somente as linhas pertencentes ao setor atual. */
    linesSector() {
        return this.lines.filter((l) => l.sector_id === this.idSector);
    }
    /** GET /api/lines: recarrega as linhas e seus totais de equipamentos/comprimento. */
    loadData() {
        this.api
            .lines()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe((x) => (this.lines = x));
    }
    // Busca máquinas livres no setor e máquinas já posicionadas na linha escolhida.
    /** Consulta máquinas disponíveis no setor e as alocadas na linha; sugere a próxima posição livre após a última. */
    loadAssembly() {
        this.idEquipmentAssembly = null;
        if (!this.idSector) {
            this.equipmentAvailable = [];
            this.equipmentAllocated = [];
            return;
        }
        this.httpClient
            .get<EquipmentData[]>(
                '/api/equipment?available=true&sectorId=' + this.idSector
            )
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.equipmentAvailable = x),
                error: () =>
                    (this.errorAssembly = 'Falha ao carregar repositório'),
            });
        if (this.idLineAssembly)
            this.api
                .equipment(this.idLineAssembly)
                .pipe(finalize(() => this.changeDetector.markForCheck()))
                .subscribe({
                    next: (x) => {
                        this.equipmentAllocated = x;
                        this.positionAssembly =
                            Math.max(
                                0,
                                ...x.map((e) => Number(e.position) || 0)
                            ) + 1;
                    },
                    error: () =>
                        (this.errorAssembly = 'Falha ao carregar linha'),
                });
        else this.equipmentAllocated = [];
    }
    /** Soma o comprimento das máquinas carregadas na montagem e converte para metros. */
    metersAllocated() {
        return (
            this.equipmentAllocated.reduce(
                (sum, e) => sum + Number(e.length_mm || 0),
                0
            ) / 1000
        );
    }
    // Envia equipamento e posição para validação e gravação transacional da montagem.
    /** POST /api/lines/:id/equipment: envia máquina e posição; o serviço Django valida e grava montagem e histórico em transação. */
    allocate() {
        if (
            !this.idLineAssembly ||
            !this.idEquipmentAssembly ||
            !Number.isInteger(Number(this.positionAssembly)) ||
            Number(this.positionAssembly) < 1
        )
            return;
        this.errorAssembly = '';
        this.successMessageAssembly = '';
        this.processing = true;
        this.httpClient
            .post(`/api/lines/${this.idLineAssembly}/equipment`, {
                equipmentId: this.idEquipmentAssembly,
                position: Number(this.positionAssembly),
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.processing = false;
                    this.successMessageAssembly =
                        'Equipamento alocado com sucesso.';
                    this.loadAssembly();
                    this.loadData();
                },
                error: (e) => {
                    this.processing = false;
                    this.errorAssembly =
                        e.error?.error || 'Erro ao alocar equipamento';
                },
            });
    }
    // Devolve a máquina ao repositório sem excluir seu cadastro ou suas ordens.
    /** DELETE da alocação devolve a máquina ao repositório; não exclui a máquina nem suas OS. */
    release(e: EquipmentData) {
        if (
            !this.idLineAssembly ||
            !confirm('Devolver este equipamento ao repositório?')
        )
            return;
        this.errorAssembly = '';
        this.successMessageAssembly = '';
        this.processing = true;
        this.httpClient
            .delete(`/api/lines/${this.idLineAssembly}/equipment/${e.id}`)
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.processing = false;
                    this.successMessageAssembly =
                        'Equipamento devolvido ao repositório.';
                    this.loadAssembly();
                    this.loadData();
                },
                error: (err) => {
                    this.processing = false;
                    this.errorAssembly =
                        err.error?.error || 'Erro ao remover equipamento';
                },
            });
    }
    // Solicita retirada de todas as máquinas; a API preserva cadastros e registra o histórico.
    /** POST /api/lines/:id/dismantle: pede a retirada de todas as máquinas e recarrega a composição. */
    dismantle() {
        if (
            !this.idLineAssembly ||
            !confirm(
                'Desmontar esta linha e devolver TODAS as máquinas ao repositório? Os cadastros e as OS serão preservados.'
            )
        )
            return;
        this.errorAssembly = '';
        this.successMessageAssembly = '';
        this.processing = true;
        this.httpClient
            .post<{
                released: number;
            }>(`/api/lines/${this.idLineAssembly}/dismantle`, {})
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (r) => {
                    this.processing = false;
                    this.successMessageAssembly = `Linha desmontada. ${r.released} equipamento(s) devolvido(s).`;
                    this.loadAssembly();
                    this.loadData();
                },
                error: (e) => {
                    this.processing = false;
                    this.errorAssembly =
                        e.error?.error || 'Erro ao desmontar linha';
                },
            });
    }
    formOpen = false;
    registering = false;
    idLineEditing: number | null = null;
    messageLine = '';
    /** Reutiliza o formulário para editar apenas os dados de identificação da linha. */
    editLine(line: Line) {
        if (this.registering) return;
        this.idLineEditing = line.id;
        this.name = line.name;
        this.description = line.description || '';
        this.error = this.messageLine = '';
        this.formOpen = true;
    }
    /** Limpa nome, descrição e erro antes de abrir o cadastro de linha. */
    openFormLine() {
        if (this.registering) return;
        this.idLineEditing = null;
        this.messageLine = '';
        this.name = this.description = this.error = '';
        this.formOpen = true;
    }
    /** POST cria a linha; PATCH edita nome/descrição mantendo o mesmo ID e a montagem. */
    register() {
        if (this.registering || !this.idSector || this.name.trim().length < 2)
            return;
        this.registering = true;
        this.error = '';
        const editing = this.idLineEditing !== null;
        const data = {
            name: this.name.trim(),
            description: this.description,
        };
        const requisition = editing
            ? this.httpClient.patch(`/api/lines/${this.idLineEditing}`, data)
            : this.httpClient.post('/api/lines', {
                  ...data,
                  sectorId: this.idSector,
              });
        requisition
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: () => {
                    this.registering = false;
                    this.formOpen = false;
                    this.name = this.description = '';
                    this.error = '';
                    this.idLineEditing = null;
                    this.messageLine = editing
                        ? 'Nome e descrição da linha atualizados.'
                        : 'Linha cadastrada.';
                    this.loadData();
                },
                error: (e) => {
                    this.registering = false;
                    this.error = e.error?.error || 'Erro ao salvar';
                },
            });
    }
}
