import {RegistrationFeedback} from '../../shared/registration-feedback';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal, TemplateRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { DatePipe } from '@angular/common';
import { finalize } from 'rxjs';

type Platform = 'NXT' | 'NPM';
type TapeType = '' | 'EMBOSS' | 'PAPER' | 'BOTH';
type MaintenanceKind = 'PREVENTIVE' | 'REPAIR';

interface FeederLine {
    id: number;
    name: string;
}

interface Feeder {
    id: number;
    line_name: string | null;
    platform: Platform;
    part_number: string;
    width: string;
    model_number: string;
    serial_number: string;
    tape_type: TapeType;
    manufacturing_code: string;
}

interface MaintenanceEntry {
    id: number;
    kind: MaintenanceKind;
    date: string;
    description: string;
}

interface SectorFeeders {
    sector_name: string;
    lines: FeederLine[];
    feeders: Feeder[];
}

@Component({
    standalone: true,
    imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatDialogModule, MatIconModule],
    templateUrl: './feeders.component.html',
    styleUrl: './feeders-modal.component.scss',
    styles: [`
        .feeder-form { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; }
        .feeder-form label { display: grid; gap: 6px; flex: 1 1 145px; }
        .feeder-form input:not([type="radio"]), .feeder-form select, .feeder-form textarea {
            width: 100%; box-sizing: border-box; padding: 10px;
            border: 1px solid #cbd5e1; border-radius: 8px; font: inherit;
        }
        .feeder-form .description { flex: 3 1 260px; }
        .card, .table-wrap { margin-top: 16px; }
        .feeder-specs { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 12px; }
        .feeder-specs dt { font-weight: 600; }
        .feeder-specs dd { margin: 0; overflow-wrap: anywhere; }
        .notes { white-space: pre-wrap; overflow-wrap: anywhere; }
    `],
})
export class Feeders implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    private http = inject(HttpClient);
    private dialog = inject(MatDialog);
    private registrationDialog?: MatDialogRef<unknown>;
    readonly sectorId = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
    private url = '/api/sectors/' + this.sectorId + '/feeders';

    readonly platforms = { NXT: 'NXT Fuji', NPM: 'NPM Panasonic' };
    readonly tapes = { '': '', EMBOSS: 'Emboss', PAPER: 'Paper', BOTH: 'Emboss e Paper' };
    readonly data = signal<SectorFeeders | null>(null);
    readonly maintenanceLabels = { PREVENTIVE: 'Preventiva', REPAIR: 'Conserto' };
    readonly maintenanceKinds: MaintenanceKind[] = ['PREVENTIVE', 'REPAIR'];
    readonly selected = signal<Feeder | null>(null);
    readonly history = signal<MaintenanceEntry[] | null>(null);
    readonly savingFeeder = signal(false);
    readonly savingMaintenance = signal(false);
    readonly error = signal('');
    readonly registrationError = signal('');
    readonly historyError = signal('');
    lineId: number | null = null;
    platform: Platform | null = null;
    partNumber = '';
    width = '';
    modelNumber = '';
    serialNumber = '';
    tapeType: TapeType = '';
    manufacturingCode = '';
    maintenanceDate = '';
    maintenanceKind: MaintenanceKind | null = null;
    description = '';

    ngOnInit() {
        this.http.get<SectorFeeders>(this.url).subscribe({
            next: data => {
                this.data.set(data);
                this.lineId = data.lines.length === 1 ? data.lines[0].id : null;
            },
            error: error => this.error.set(this.message(error, 'Não foi possível abrir o módulo de feeders.')),
        });
    }

    openRegistration(template: TemplateRef<unknown>) {
        if (this.registrationDialog) return;
        this.resetRegistration();
        this.registrationDialog = this.dialog.open(template, {
            width: '680px',
            maxWidth: 'calc(100vw - 32px)',
            panelClass: 'sector-dialog-panel',
            backdropClass: 'sector-dialog-backdrop',
            ariaLabelledBy: 'feeder-dialog-title',
            closePredicate: () => !this.savingFeeder(),
        });
        this.registrationDialog.afterClosed().subscribe(() => {
            this.registrationDialog = undefined;
            this.resetRegistration();
        });
    }

    closeRegistration() {
        this.registrationDialog?.close();
    }

    private resetRegistration() {
        const lines = this.data()?.lines ?? [];
        this.lineId = lines.length === 1 ? lines[0].id : null;
        this.platform = null;
        this.partNumber = '';
        this.width = '';
        this.modelNumber = '';
        this.serialNumber = '';
        this.tapeType = '';
        this.manufacturingCode = '';
        this.registrationError.set('');
    }

    addFeeder() {
        if (!this.platform || !this.partNumber.trim() || !this.width.trim() || this.savingFeeder()) return;

        this.registrationError.set('');
        this.savingFeeder.set(true);
        this.http.post<Feeder>(this.url, {
            line_id: this.lineId,
            platform: this.platform,
            part_number: this.partNumber,
            width: this.width,
            ...(this.platform === 'NPM' ? {
                model_number: this.modelNumber,
                serial_number: this.serialNumber,
                tape_type: this.tapeType,
                manufacturing_code: this.manufacturingCode,
            } : {}),
        }).pipe(finalize(() => this.savingFeeder.set(false))).subscribe({
            next: feeder => {
                this.data.update(data => data && { ...data, feeders: [...data.feeders, feeder] });
                this.savingFeeder.set(false);
                this.closeRegistration();
                this.registrationFeedback.created('Feeder cadastrado com sucesso', feeder.part_number);
            },
            error: error => this.registrationError.set(this.message(error, 'Não foi possível cadastrar o feeder.')),
        });
    }

    openHistory(feeder: Feeder) {
        this.selected.set(feeder);
        this.history.set(null);
        this.historyError.set('');
        this.maintenanceDate = '';
        this.maintenanceKind = null;
        this.description = '';
        this.http.get<MaintenanceEntry[]>(this.maintenanceUrl(feeder)).subscribe({
            next: history => {
                if (this.selected() === feeder) this.history.set(history);
            },
            error: error => {
                if (this.selected() === feeder) {
                    this.historyError.set(this.message(error, 'Não foi possível carregar o histórico de manutenções.'));
                }
            },
        });
    }

    addMaintenance(feeder: Feeder) {
        if (!this.maintenanceKind || !this.maintenanceDate || !this.description.trim() || this.savingMaintenance()) return;

        this.historyError.set('');
        this.savingMaintenance.set(true);
        this.http.post<MaintenanceEntry>(this.maintenanceUrl(feeder), {
            kind: this.maintenanceKind,
            date: this.maintenanceDate,
            description: this.description,
        }).pipe(finalize(() => this.savingMaintenance.set(false))).subscribe({
            next: entry => {
                const entries = [entry, ...(this.history() ?? [])];
                this.history.set(entries.sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id));
                this.maintenanceDate = '';
                this.maintenanceKind = null;
                this.description = '';
            },
            error: error => this.historyError.set(this.message(error, 'Não foi possível registrar a manutenção.')),
        });
    }

    private maintenanceUrl(feeder: Feeder) {
        return this.url + '/' + feeder.id + '/maintenance';
    }

    private message(error: HttpErrorResponse, fallback: string) {
        return typeof error.error?.error === 'string' ? error.error.error : fallback;
    }
}
