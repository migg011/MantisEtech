// Cenário isolado para conferir a interface sem alterar cadastros ou autenticação reais.
import { Component, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { WorkOrderDialog } from '../src/app/features/work-order-dialog/work-order-dialog.component';
import { PartPurchases } from '../src/app/features/part-purchases/part-purchases.component';
import { bootstrapApplication } from '@angular/platform-browser';
import {
    provideRouter,
    ActivatedRoute,
    convertToParamMap,
} from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { of, from, throwError } from 'rxjs';
import { Totem } from '../src/app/features/totem/totem.component';
import { Api, Authentication } from '../src/app/services';
import { EquipmentRegistration } from '../src/app/features/equipment/equipment.component';
import { SmtLines } from '../src/app/features/smt-lines/smt-lines.component';
import { SpareParts } from '../src/app/features/spare-parts/spare-parts.component';
let testPartPhoto = '';
const testParts = [
    {
        id: 1,
        code: 'SP-TESTE',
        description: 'Nozzle Holder NPM H16',
        part_number: 'N610113699AA',
        manufacturer: 'Panasonic',
        category: 'Holder',
        unit: 'UN',
        minimum_stock: 2,
        maximum_stock: 16,
        reorder_point: 1,
        storage_location: 'Armário de teste',
        preferred_supplier: 'Fornecedor de teste',
        average_cost: 53,
        last_cost: 66,
        average_cost_currency: 'USD',
        last_cost_currency: 'USD',
        equipment_ids: [],
        photo_filename: null as string | null,
    },
];
const testLines = [
    {
        id: 1,
        code: 'LIN-TESTE',
        name: 'Linha SMT — teste visual',
        description: 'Descrição original',
        sector_name: 'Demonstração',
        sector_id: 1,
    },
];
const types = [
    'MAGAZINE LOADER',
    'PRINTER',
    'CONVEYOR',
    'SPI',
    'CONVEYOR',
    'PICK & PLACE',
    'PICK & PLACE',
    'CONVEYOR',
    'AOI',
    'CONVEYOR',
    'REFLOW',
    'CONVEYOR',
    'AOI',
    'BUFFER',
];
const registration = location.hash.includes('cadastro');
const machines = types.map((type_name, i) => ({
    id: i + 1,
    sector_id: 1,
    equipment_type_id: 1,
    type_name,
    position: registration && i === 0 ? null : i + 1,
    line_id: registration && i === 0 ? null : 1,
    model: `Modelo ${i + 1}`,
    asset_number: `ATV-${i + 1}`,
    serial: `SERIE-${i + 1}`,
    has_photo: i === 1 || i === 2,
}));
const movements: Record<number, any[]> = {};
const orders = [
    {
        id: 42,
        equipment_id: 6,
        type_name: 'PICK & PLACE',
        model: 'Modelo 6',
        problem: 'Falha na alimentação de componentes',
        status: 'EM_ANDAMENTO',
        opened_by_name: 'Operador de teste',
        assigned_to_name: 'Técnico de teste',
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: null,
        server_now: new Date().toISOString(),
    },
    {
        id: 43,
        equipment_id: 13,
        type_name: 'AOI',
        problem: 'Inspeção pendente',
        status: 'ABERTA',
        opened_by_name: 'Operador de teste',
        created_at: new Date().toISOString(),
        server_now: new Date().toISOString(),
    },
];
@Component({
    standalone: true,
    template: '<button (click)="open()">Abrir OS de teste</button>',
})
class WorkOrderPreview {
    dialog = inject(MatDialog);
    open() {
        this.dialog.open(WorkOrderDialog, {
            data: orders[0],
            width: '1100px',
            maxWidth: '95vw',
            maxHeight: '95vh',
        });
    }
}
bootstrapApplication(
    location.hash.includes('os-teste')
        ? WorkOrderPreview
        : location.hash.includes('compras')
          ? PartPurchases
          : location.hash.includes('pecas')
            ? SpareParts
            : location.hash.includes('cadastro')
              ? EquipmentRegistration
              : location.hash.includes('linhas')
                ? SmtLines
                : Totem,
    {
        providers: [
            provideRouter([]),
            {
                provide: ActivatedRoute,
                useValue: {
                    paramMap: of(convertToParamMap({ id: '1' })),
                    queryParamMap: of(convertToParamMap({ sectorId: '1' })),
                    snapshot: {
                        paramMap: convertToParamMap({ id: '1' }),
                        queryParamMap: { get: () => '1' },
                    },
                },
            },
            {
                provide: Api,
                useValue: {
                    typesProblem: () =>
                        of([
                            {
                                id: 1,
                                name: 'Falha de teste',
                                priority: 'MEDIA',
                            },
                        ]),
                    types: () => of([{ id: 1, name: 'CONVEYOR' }]),
                    sectors: () =>
                        of([
                            { id: 1, name: 'Demonstração' },
                            { id: 2, name: 'Destino de teste' },
                        ]),
                    lines: () => of(testLines),
                    equipment: () => of(machines),
                },
            },
            {
                provide: Authentication,
                useValue: {
                    user: () => ({
                        name: 'Teste visual',
                        role: 'ADMINISTRADOR',
                    }),
                },
            },
            {
                provide: HttpClient,
                useValue: {
                    get: (url: string) => {
                        if (url === '/api/orders/42') return of(orders[0]);
                        if (url === '/api/orders/42/spare-parts')
                            return of(testParts);
                        if (url === '/api/orders/42/part-requisitions')
                            return of([]);
                        if (url === '/api/spare-purchase/parts')
                            return of(testParts);
                        if (url.startsWith('/api/spare-purchase/'))
                            return of([]);
                        if (url === '/api/spare-parts') return of(testParts);
                        if (
                            url.startsWith('/api/spare-parts/') &&
                            url.endsWith('/details')
                        )
                            return of({
                                ...testParts[0],
                                technical: {
                                    description_pt:
                                        'Suporte de bicos para cabeçote NPM H16',
                                    ncm: '84799090',
                                    fiscal_status: 'PENDENTE',
                                },
                            });
                        if (
                            url.startsWith('/api/spare-parts/') &&
                            url.endsWith('/photo')
                        )
                            return from(
                                fetch(testPartPhoto).then((r) => r.blob())
                            );
                        if (url.includes('/attachments/PHOTO/download'))
                            return url.includes('/3/')
                                ? throwError(() => new Error('Falha simulada'))
                                : from(
                                      fetch(
                                          '/assets/equipment/loader.png'
                                      ).then((r) => r.blob())
                                  );
                        if (url.endsWith('/attachments'))
                            return of([
                                {
                                    kind: 'PHOTO',
                                    filename: 'foto-persistida.png',
                                },
                            ]);
                        if (url.endsWith('/movements'))
                            return of(
                                movements[Number(url.split('/')[3])] || []
                            );
                        if (url.startsWith('/api/equipment'))
                            return of(
                                machines.filter((m) => m.sector_id === 1)
                            );
                        return of(orders);
                    },
                    patch: (url: string, data: any) => {
                        if (url.startsWith('/api/spare-parts/')) {
                            Object.assign(testParts[0], {
                                average_cost: data.averageCost,
                                last_cost: data.lastCost,
                                average_cost_currency: data.averageCostCurrency,
                                last_cost_currency: data.lastCostCurrency,
                            });
                            if (data.photo) {
                                testParts[0].photo_filename =
                                    data.photo.filename;
                                testPartPhoto = `data:${data.photo.mimeType};base64,${data.photo.base64}`;
                            }
                            return of(testParts[0]);
                        }
                        Object.assign(testLines[0], data);
                        return of(testLines[0]);
                    },
                    post: (url: string, data: any) => {
                        const id = Number(url.split('/')[3]);
                        const machine = machines.find((m) => m.id === id)!;
                        machine.sector_id = data.destinationSectorId;
                        movements[id] = [
                            {
                                action: 'TRANSFERENCIA',
                                from_sector_name: 'Demonstração',
                                to_sector_name: 'Destino de teste',
                                performed_by_name: 'Teste visual',
                                created_at: new Date().toISOString(),
                                reason: data.reason,
                            },
                        ];
                        return of(machine);
                    },
                },
            },
        ],
    }
).catch(console.error);
