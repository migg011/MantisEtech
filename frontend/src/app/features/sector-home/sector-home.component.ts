/** Módulo ambiente-setor: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
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
const UI = [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatIconModule, MatSelectModule, MatToolbarModule, MatDialogModule, MatCardModule, RouterLink];
@Component({
    standalone: true,
    imports: UI,
    templateUrl: './sector-home.component.html',
    styleUrl: './sector-home.component.scss'
})
/** Reúne as máquinas e linhas do setor selecionado para apresentar seu ambiente. */
export class SectorHome implements OnInit {
    api = inject(Api);
    authValue = inject(Auth);
    httpValue = inject(HttpClient);
    routeValue = inject(ActivatedRoute);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    sectorIdValue = 0;
    sectorValue: {
        id: number;
        name: string;
        description?: string;
    } | undefined;
    linesValue: Line[] = [];
    machinesValue: EquipmentData[] = [];
    errorValue = '';
    /** Lê o ID do setor da URL e consulta setores, linhas e máquinas; atualiza a visão do ambiente após as respostas. */
    ngOnInit() {
        this.routeValue.paramMap.pipe(finalize(() => this.cdr.markForCheck())).subscribe(paramsValue => {
            this.sectorIdValue = Number(paramsValue.get('id'));
            this.sectorValue = undefined;
            this.errorValue = '';
            if (!Number.isInteger(this.sectorIdValue) || this.sectorIdValue <= 0) {
                this.errorValue = 'Setor inválido.';
                return;
            }
            this.api.sectors().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: sectors => {
                    this.sectorValue = sectors.find(s => Number(s.id) === this.sectorIdValue);
                    if (!this.sectorValue) {
                        this.errorValue = 'Setor não encontrado ou inativo.';
                    }
                    this.cdr.detectChanges();
                },
                error: () => {
                    this.errorValue = 'Não foi possível carregar o setor.';
                    this.cdr.detectChanges();
                }
            });
            this.api.linesValue().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: lines => this.linesValue = lines,
                error: () => {
                    this.errorValue = 'Não foi possível carregar as linhas.';
                }
            });
            this.httpValue.get<EquipmentData[]>('/api/equipment?sectorId=' + this.sectorIdValue).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
                next: items => this.machinesValue = items,
                error: () => {
                    this.errorValue = 'Não foi possível carregar o repositório.';
                }
            });
        });
    }
    /** Filtra em memória apenas as linhas do setor selecionado, sem nova chamada HTTP. */
    sectorLines() {
        return this.linesValue.filter(l => l.sector_id === this.sectorIdValue);
    }
    /** Converte para metros o comprimento em milímetros retornado pela API. */
    lineDimensions(l: Line): number {
        return Number(l.length_mm || 0) / 1000;
    }
    /** Conta máquinas do setor que ainda não estão alocadas em uma linha. */
    quantidadeDisponivel() {
        return this.machinesValue.filter(e => !e.line_id).length;
    }
}
