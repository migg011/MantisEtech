/** Painel operacional: contagens completas e séries vêm de uma única consulta agregada. */
import {
    Component,
    inject,
    OnInit,
    OnDestroy,
    ChangeDetectorRef,
    LOCALE_ID,
} from '@angular/core';
import { CommonModule, registerLocaleData } from '@angular/common';
import portuguese from '@angular/common/locales/pt';
registerLocaleData(portuguese);
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { MatIconModule } from '@angular/material/icon';
import { Subscription } from 'rxjs';
import { Api, Line } from '../../services';
interface Indicators {
    equipment_total: number;
    equipment_active: number;
    equipment_fault: number;
    open_orders: number;
    availability_pct: number | null;
    mttr_hours: number | null;
    mttr_sample: number;
    mtbf_hours: number | null;
}
interface DashboardSummary {
    generated_at: string;
    days: number;
    start_date: string;
    end_date: string;
    summary: Indicators;
    distribution: {
        corrective: number;
        preventive: number;
        predictive: number | null;
    };
    evolution: { date: string; opened: number; closed: number }[];
    latest_orders: {
        id: number;
        number: string;
        equipment: string;
        kind: string;
        status: string;
        created_at: string;
    }[];
}
@Component({
    standalone: true,
    providers: [{ provide: LOCALE_ID, useValue: 'pt-BR' }],
    imports: [CommonModule, FormsModule, RouterLink, MatIconModule],
    templateUrl: './dashboard.component.html',
    styleUrl: './dashboard.component.scss',
})
export class Dashboard implements OnInit, OnDestroy {
    private http = inject(HttpClient);
    private api = inject(Api);
    private cd = inject(ChangeDetectorRef);
    private requestSubscription?: Subscription;
    private linesSubscription?: Subscription;
    lines: Line[] = [];
    lineId = '';
    days = 30;
    data: DashboardSummary | null = null;
    loading = false;
    errorMessage = '';
    linesError = '';
    openedPath = '';
    closedPath = '';
    openedPoints: { x: number; y: number }[] = [];
    closedPoints: { x: number; y: number }[] = [];
    labels: { x: number; text: string }[] = [];
    ticks: { y: number; value: number }[] = [];
    ngOnInit() {
        this.linesSubscription = this.api.lines().subscribe({
            next: (lines) => {
                this.lines = lines;
                this.cd.markForCheck();
            },
            error: () => {
                this.linesError = 'Filtro de linhas indisponível.';
                this.cd.markForCheck();
            },
        });
        this.load();
    }
    load() {
        this.requestSubscription?.unsubscribe();
        this.loading = true;
        this.errorMessage = '';
        this.data = null;
        const params: Record<string, string> = { days: String(this.days) };
        if (this.lineId) params['lineId'] = this.lineId;
        this.requestSubscription = this.http
            .get<DashboardSummary>('/api/dashboard', { params })
            .subscribe({
                next: (data) => {
                    this.data = data;
                    this.prepareChart(data);
                    this.loading = false;
                    this.cd.markForCheck();
                },
                error: () => {
                    this.errorMessage =
                        'Não foi possível atualizar os indicadores. Tente novamente.';
                    this.loading = false;
                    this.cd.markForCheck();
                },
            });
    }
    get periodTotal() {
        return this.data
            ? this.data.distribution.corrective +
                  this.data.distribution.preventive
            : 0;
    }
    percentage(value: number) {
        return this.periodTotal
            ? Math.round((100 * value) / this.periodTotal)
            : 0;
    }
    get typeRing() {
        const p = this.data
            ? this.percentage(this.data.distribution.preventive)
            : 0;
        return this.periodTotal
            ? `conic-gradient(#2664ca 0% ${p}%,#ed3b48 ${p}% 100%)`
            : '#e9edf4';
    }
    get availabilityRing() {
        return `conic-gradient(#12a45a 0% ${this.data?.summary.availability_pct ?? 0}%,#e8f2ed 0%)`;
    }
    statusLabel(status: string) {
        return (
            (
                {
                    ABERTA: 'Aberta',
                    EM_ANDAMENTO: 'Em andamento',
                    CONCLUIDA: 'Concluída',
                    CANCELADA: 'Cancelada',
                } as Record<string, string>
            )[status] || status
        );
    }
    prepareChart(data: DashboardSummary) {
        const count = data.evolution.length;
        const maxValue = Math.max(
            1,
            ...data.evolution.flatMap((point) => [point.opened, point.closed])
        );
        const ceiling = Math.ceil(maxValue / 4) * 4;
        const x = (i: number) => 36 + (i * 568) / Math.max(1, count - 1),
            y = (v: number) => 174 - (v / ceiling) * 144;
        this.ticks = Array.from({ length: 5 }, (_, i) => ({
            y: y((i * ceiling) / 4),
            value: (i * ceiling) / 4,
        }));
        this.openedPath = data.evolution
            .map((point, i) => `${x(i)},${y(point.opened)}`)
            .join(' ');
        this.closedPath = data.evolution
            .map((point, i) => `${x(i)},${y(point.closed)}`)
            .join(' ');
        this.openedPoints =
            count <= 7
                ? data.evolution.map((point, i) => ({
                      x: x(i),
                      y: y(point.opened),
                  }))
                : [];
        this.closedPoints =
            count <= 7
                ? data.evolution.map((point, i) => ({
                      x: x(i),
                      y: y(point.closed),
                  }))
                : [];
        const indexes = [
            ...new Set(
                Array.from({ length: Math.min(7, count) }, (_, i) =>
                    Math.round(
                        (i * (count - 1)) / Math.max(1, Math.min(7, count) - 1)
                    )
                )
            ),
        ];
        this.labels = indexes.map((i) => ({
            x: x(i),
            text:
                data.evolution[i].date.slice(8, 10) +
                '/' +
                data.evolution[i].date.slice(5, 7),
        }));
    }
    ngOnDestroy() {
        this.requestSubscription?.unsubscribe();
        this.linesSubscription?.unsubscribe();
    }
}
