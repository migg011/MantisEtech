import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { RegistrationCenter } from '../src/app/features/registration/registration-center.component';
import { MaterialCategories } from '../src/app/features/material-categories/material-categories.component';
// Usa os componentes reais com dados simulados; não acessa o banco do usuário.
import { bootstrapApplication } from '@angular/platform-browser';
import { HttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SpareParts } from '../src/app/features/spare-parts/spare-parts.component';
import { Authentication } from '../src/app/services';
let categories: any[] = [
    {
        id: 1,
        name: 'NPM',
        description: 'Peças para a família NPM',
        active: true,
    },
    {
        id: 2,
        name: 'NXT',
        description: 'Peças para a família NXT',
        active: true,
    },
    {
        id: 3,
        name: 'Limpeza',
        description: 'Materiais de limpeza',
        active: true,
    },
];
let parts: any[] = [
    {
        id: 1,
        code: 'SP-1',
        part_number: 'N610113699AA',
        description: 'Nozzle Holder NPM H16',
        manufacturer: 'Panasonic',
        category_ids: [1],
        unit: 'UN',
        stock_quantity: 4,
        minimum_stock: 2,
        maximum_stock: 16,
        reorder_point: 1,
        equipment_ids: [],
        average_cost: 53,
        average_cost_currency: 'USD',
        last_cost: 66,
        last_cost_currency: 'USD',
        storage_location: 'Armário NON ALPHA',
        photo_filename: null,
    },
    {
        id: 2,
        code: 'SP-2',
        part_number: 'MAT-002',
        description: 'Álcool para limpeza',
        manufacturer: 'Fornecedor de teste',
        category_ids: [3],
        unit: 'L',
        stock_quantity: 0,
        minimum_stock: 1,
        maximum_stock: 10,
        reorder_point: 1,
        equipment_ids: [],
        average_cost: null,
        last_cost: null,
        photo_filename: null,
    },
];
const enriched = (p: any) => ({
    ...p,
    categories: categories.filter((c) => p.category_ids.includes(c.id)),
});
const fail = () => throwError(() => new Error('Operação não simulada'));
@Component({
    standalone: true,
    imports: [RouterOutlet],
    template: '<router-outlet />',
})
class PreviaCentral {}
bootstrapApplication(PreviaCentral, {
    providers: [
        provideRouter([
            { path: 'cadastro', component: RegistrationCenter },
            { path: 'cadastro/categorias', component: MaterialCategories },
            { path: 'cadastro/spare-parts', component: SpareParts },
            { path: '**', redirectTo: 'cadastro' },
        ]),
        {
            provide: Authentication,
            useValue: { user: () => ({ id: 1, role: 'ADMINISTRADOR' }) },
        },
        {
            provide: HttpClient,
            useValue: {
                get: (url: string, options: any = {}) => {
                    if (url === '/api/part-categories')
                        return of(
                            categories.map((c) => ({
                                ...c,
                                part_count: parts.filter((p) =>
                                    p.category_ids.includes(c.id)
                                ).length,
                            }))
                        );
                    if (url === '/api/spare-parts') {
                        const id = Number(options.params?.categoryId);
                        const q = (options.params?.q || '').toLowerCase();
                        return of(
                            parts
                                .filter(
                                    (p) =>
                                        (!id || p.category_ids.includes(id)) &&
                                        JSON.stringify(p)
                                            .toLowerCase()
                                            .includes(q)
                                )
                                .map(enriched)
                        );
                    }
                    if (url.endsWith('/details'))
                        return of(
                            enriched(
                                parts.find(
                                    (p) => p.id === Number(url.split('/')[3])
                                )
                            )
                        );
                    return fail();
                },
                post: (url: string, d: any) => {
                    if (url === '/api/part-categories') {
                        const c = {
                            id: categories.length + 1,
                            active: true,
                            ...d,
                        };
                        categories.push(c);
                        return of(c);
                    }
                    if (url === '/api/spare-parts') {
                        const p = {
                            id: parts.length + 1,
                            code: 'SP-MOCK',
                            part_number: d.partNumber,
                            description: d.description,
                            manufacturer: d.manufacturer,
                            category_ids: d.categoryIds,
                            unit: d.unit,
                            stock_quantity: null,
                            equipment_ids: [],
                            photo_filename: null,
                        };
                        parts.push(p);
                        return of(enriched(p));
                    }
                    return fail();
                },
                patch: (url: string, d: any) => {
                    if (url.startsWith('/api/part-categories/')) {
                        const c = categories.find(
                            (c) => c.id === Number(url.split('/').pop())
                        );
                        Object.assign(c, d);
                        return of(c);
                    }
                    if (url.startsWith('/api/spare-parts/')) {
                        const p = parts.find(
                            (p) => p.id === Number(url.split('/').pop())
                        );
                        Object.assign(p, {
                            description: d.description,
                            part_number: d.partNumber,
                            category_ids: d.categoryIds,
                        });
                        return of(enriched(p));
                    }
                    return fail();
                },
            },
        },
    ],
}).catch(console.error);
