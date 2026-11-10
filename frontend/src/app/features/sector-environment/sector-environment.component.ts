/** Módulo ambiente-setor: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
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
    templateUrl: './sector-environment.component.html',
    styleUrl: './sector-environment.component.scss',
})
/** Reúne as máquinas e linhas do setor selecionado para apresentar seu ambiente. */
export class SectorEnvironment implements OnInit {
    api = inject(Api);
    httpClient = inject(HttpClient);
    route = inject(ActivatedRoute);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    idSector = 0;
    sector:
        | {
              id: number;
              name: string;
              description?: string;
          }
        | undefined;
    lines: Line[] = [];
    equipment: EquipmentData[] = [];
    error = '';
    /** Lê o ID do setor da URL e consulta setores, linhas e máquinas; atualiza a visão do ambiente após as respostas. */
    ngOnInit() {
        this.route.paramMap
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe((parameters) => {
                this.idSector = Number(parameters.get('id'));
                this.sector = undefined;
                this.error = '';
                if (!Number.isInteger(this.idSector) || this.idSector <= 0) {
                    this.error = 'Setor inválido.';
                    return;
                }
                this.api
                    .sectors()
                    .pipe(finalize(() => this.changeDetector.markForCheck()))
                    .subscribe({
                        next: (sectors) => {
                            this.sector = sectors.find(
                                (s) => Number(s.id) === this.idSector
                            );
                            if (!this.sector) {
                                this.error = 'Setor não encontrado ou inativo.';
                            }
                            this.changeDetector.detectChanges();
                        },
                        error: () => {
                            this.error = 'Não foi possível carregar o setor.';
                            this.changeDetector.detectChanges();
                        },
                    });
                this.api
                    .lines()
                    .pipe(finalize(() => this.changeDetector.markForCheck()))
                    .subscribe({
                        next: (lines) => (this.lines = lines),
                        error: () => {
                            this.error = 'Não foi possível carregar as linhas.';
                        },
                    });
                this.httpClient
                    .get<EquipmentData[]>(
                        '/api/equipment?sectorId=' + this.idSector
                    )
                    .pipe(finalize(() => this.changeDetector.markForCheck()))
                    .subscribe({
                        next: (items) => (this.equipment = items),
                        error: () => {
                            this.error =
                                'Não foi possível carregar o repositório.';
                        },
                    });
            });
    }
    /** Filtra em memória apenas as linhas do setor selecionado, sem nova chamada HTTP. */
    linesSector() {
        return this.lines.filter((l) => l.sector_id === this.idSector);
    }
    /** Converte para metros o comprimento em milímetros retornado pela API. */
    dimensionsLines(l: Line): number {
        return Number(l.length_mm || 0) / 1000;
    }
    /** Conta máquinas do setor que ainda não estão alocadas em uma linha. */
    quantityAvailable() {
        return this.equipment.filter((e) => !e.line_id).length;
    }
}
