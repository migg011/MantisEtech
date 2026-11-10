// Prévia isolada de navegação e gravação. Não chama nem altera o banco real.
import { bootstrapApplication } from '@angular/platform-browser';
import {
    provideRouter,
    ActivatedRoute,
    convertToParamMap,
} from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { Preventive } from '../src/app/features/preventive/preventive.component';
import { Api, Authentication } from '../src/app/services';
const machine: any = {
    id: 1,
    equipment_type_id: 1,
    type_name: 'PRINTER',
    name: 'DEK — demonstração',
    model: 'Horizon',
    asset_number: 'ATV-002',
    serial: 'SN-DEMO-002',
    manufacturer: 'DEK',
    line_id: 1,
    line_name: 'SMT-01',
    sector_name: 'Produção',
    position: 2,
    preventive_schedules: [
        {
            id: 1,
            frequency: 'MENSAL',
            next_due: '2026-12-02',
            last_performed: null,
        },
    ],
};
const schedules = () =>
    machine.preventive_schedules.map((s: any) => ({
        ...s,
        equipment_id: 1,
        equipment_type_id: 1,
        equipment_name: machine.name,
        type_name: 'PRINTER',
        status: 'EM_DIA',
        days_remaining: 30,
    }));
bootstrapApplication(Preventive, {
    providers: [
        provideRouter([]),
        {
            provide: ActivatedRoute,
            useValue: {
                snapshot: {
                    queryParamMap: convertToParamMap({
                        equipmentId: '1',
                        tab: 'TIPOS_OS',
                    }),
                },
            },
        },
        {
            provide: Api,
            useValue: {
                types: () => of([{ id: 1, name: 'PRINTER' }]),
                equipment: () => of([machine]),
            },
        },
        {
            provide: Authentication,
            useValue: {
                user: () => ({
                    id: 1,
                    name: 'Usuário de teste',
                    role: 'ADMINISTRADOR',
                }),
            },
        },
        {
            provide: HttpClient,
            useValue: {
                get: (url: string) => {
                    if (url === '/api/preventive-schedules')
                        return of({
                            today: '2026-11-02',
                            schedules: schedules(),
                            unconfigured_count: 0,
                        });
                    if (url === '/api/preventive-orders/technicians')
                        return of([{ id: 1, name: 'Técnico de teste' }]);
                    if (
                        url === '/api/preventive-orders' ||
                        url === '/api/preventive-executions' ||
                        url.endsWith('/attachments') ||
                        url.endsWith('/movements')
                    )
                        return of([]);
                    if (url === '/api/preventive-checklists')
                        return of({
                            items: [
                                'Inspecionar sensores',
                                'Conferir lubrificação',
                            ],
                            source: 'EQUIPAMENTO',
                        });
                    return throwError(() => new Error('Consulta não simulada'));
                },
                patch: (url: string, data: any) => {
                    if (url === '/api/equipment/1') {
                        machine.preventive_schedules =
                            data.preventiveSchedules.map(
                                (s: any, i: number) => ({
                                    id: i + 1,
                                    frequency: s.frequency,
                                    next_due: s.nextDue || '2026-12-02',
                                    last_performed: null,
                                })
                            );
                        return of({ ...machine });
                    }
                    return throwError(() => new Error('Gravação não simulada'));
                },
            },
        },
    ],
}).catch(console.error);
