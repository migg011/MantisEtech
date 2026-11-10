// Prévia isolada com dados simulados. Não altera autenticação nem o banco real.
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { Dashboard } from '../src/app/features/dashboard/dashboard.component';
const now = '2026-11-02T16:00:00Z';
const emitidas = [1, 2, 1, 1, 1, 3, 2];
const encerradas = [0, 1, 1, 1, 0, 2, 3];
const base = {
    generated_at: now,
    days: 7,
    start_date: '2026-10-27',
    end_date: '2026-11-02',
    summary: {
        equipment_total: 12,
        equipment_active: 11,
        equipment_fault: 1,
        open_orders: 3,
        availability_pct: 91.7,
        mttr_hours: 2.4,
        mttr_sample: 5,
        mtbf_hours: null,
    },
    distribution: { corrective: 8, preventive: 3, predictive: null },
    evolution: emitidas.map((opened, i) => ({
        date: new Date(Date.UTC(2026, 9, 27 + i)).toISOString().slice(0, 10),
        opened,
        closed: encerradas[i],
    })),
    latest_orders: [
        ['OS-000012', 'SPI-001', 'CORRETIVA', 'EM_ANDAMENTO'],
        ['PREV-000008', 'AOI-001', 'PREVENTIVA', 'CONCLUIDA'],
        ['OS-000011', 'NPM-6', 'CORRETIVA', 'CONCLUIDA'],
        ['PREV-000007', 'Reflow Oven', 'PREVENTIVA', 'CONCLUIDA'],
        ['OS-000010', 'Conveyor', 'CORRETIVA', 'CONCLUIDA'],
    ].map(([number, equipment, kind, status], i) => ({
        id: 12 - i,
        number,
        equipment,
        kind,
        status,
        created_at: now,
    })),
};
bootstrapApplication(Dashboard, {
    providers: [
        provideRouter([]),
        {
            provide: HttpClient,
            useValue: {
                get: (url: string, opts: any) => {
                    if (url === '/api/lines')
                        return of([
                            { id: 1, name: 'Linha SMT 01' },
                            { id: 2, name: 'Linha sem equipamentos' },
                        ]);
                    if (url === '/api/dashboard') {
                        if (location.hash.includes('erro'))
                            return throwError(
                                () => new Error('Falha simulada')
                            );
                        if (opts?.params?.lineId === '2')
                            return of({
                                ...base,
                                summary: {
                                    ...base.summary,
                                    equipment_total: 0,
                                    equipment_active: 0,
                                    equipment_fault: 0,
                                    open_orders: 0,
                                    availability_pct: null,
                                    mttr_hours: null,
                                    mttr_sample: 0,
                                },
                                distribution: {
                                    corrective: 0,
                                    preventive: 0,
                                    predictive: null,
                                },
                                latest_orders: [],
                                evolution: base.evolution.map((p) => ({
                                    ...p,
                                    opened: 0,
                                    closed: 0,
                                })),
                            });
                        return of(base);
                    }
                    return throwError(() => new Error('Rota não simulada'));
                },
            },
        },
    ],
}).catch(console.error);
