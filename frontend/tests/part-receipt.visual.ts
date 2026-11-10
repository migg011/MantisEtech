// Prévia isolada: nenhuma quantidade é gravada no banco real.
import { Component } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { HttpClient } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { PartQuery } from '../src/app/shared/part-sheet.component';
import { Authentication } from '../src/app/services';
const initial = location.hash.includes('inicial');
const part: any = {
    id: 1,
    part_number: 'N610113699AA',
    description: 'Nozzle Holder NPM H16',
    manufacturer: 'Panasonic',
    category: 'Holder',
    unit: 'UN',
    storage_location: 'Armário NON ALPHA',
    preferred_supplier: 'Fornecedor de teste',
    minimum_stock: 2,
    maximum_stock: 16,
    reorder_point: 1,
    stock_quantity: initial ? null : 4,
    photo_filename: null,
    average_cost: 53,
    average_cost_currency: 'USD',
    last_cost: 66,
    last_cost_currency: 'USD',
};
let history: any[] = initial
    ? []
    : [
          {
              id: 1,
              kind: 'INICIAL',
              quantity: 4,
              delta: 4,
              resulting_quantity: 4,
              movement_date: null,
              created_at: new Date().toISOString(),
              performed_by_name: 'Usuário de teste',
              note: 'Primeira contagem',
              supplier: '',
              document_reference: '',
          },
      ];
const commands = new Map<string, any>();
@Component({
    standalone: true,
    imports: [PartQuery],
    template:
        '<main style="padding:30px"><h1>Spare Parts — prévia isolada</h1><app-consulta-peca [idPeca]="1" rotulo="Abrir ficha da peça" /></main>',
})
class PreviaEntrada {}
bootstrapApplication(PreviaEntrada, {
    providers: [
        {
            provide: Authentication,
            useValue: { user: () => ({ id: 1, role: 'ADMINISTRADOR' }) },
        },
        {
            provide: HttpClient,
            useValue: {
                get: (url: string) => {
                    if (url.endsWith('/details')) return of({ ...part });
                    if (url.endsWith('/stock-movements'))
                        return of([...history]);
                    return throwError(() => new Error('Consulta não simulada'));
                },
                post: (url: string, d: any) => {
                    if (!url.endsWith('/stock-movements'))
                        return throwError(
                            () => new Error('Operação não simulada')
                        );
                    if (commands.has(d.requestKey))
                        return of(commands.get(d.requestKey));
                    const previous = part.stock_quantity;
                    const amount = Number(d.quantity);
                    const next =
                        d.kind === 'ENTRADA'
                            ? Number(previous) + amount
                            : d.kind === 'SAIDA'
                              ? Number(previous) - amount
                              : amount;
                    part.stock_quantity = next;
                    const m = {
                        id: history.length + 1,
                        kind: d.kind,
                        quantity: amount,
                        delta: next - Number(previous ?? 0),
                        resulting_quantity: next,
                        movement_date: d.movementDate,
                        created_at: new Date().toISOString(),
                        performed_by_name: 'Usuário de teste',
                        note: d.note || 'Entrada de peças',
                        supplier: d.supplier,
                        document_reference: d.documentReference,
                    };
                    history = [m, ...history];
                    const response = { movement: m };
                    commands.set(d.requestKey, response);
                    return of(response);
                },
            },
        },
    ],
}).catch(console.error);
