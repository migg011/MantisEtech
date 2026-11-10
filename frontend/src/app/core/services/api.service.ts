/** Serviço de consultas HTTP compartilhadas. Retorna Observables; o componente faz subscribe para executar a requisição e usar a resposta. */
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Line } from '../models/line.model';
import { Equipment } from '../models/equipment.model';
import { ProblemType } from '../models/problem-type.model';
import { WorkOrder } from '../models/work-order.model';
@Injectable({
    providedIn: 'root',
})
/** Consultas compartilhadas: o proxy encaminha /api ao Django e devolve JSON tipado às telas. */
export class Api {
    httpClient = inject(HttpClient);
    /** GET /api/lines: retorna as linhas visíveis ao usuário; a assinatura ocorre no componente. */
    lines() {
        return this.httpClient.get<Line[]>('/api/lines');
    }
    /** GET /api/sectors: consulta setores ativos para listas e seletores. */
    sectors() {
        return this.httpClient.get<
            {
                id: number;
                code: string;
                name: string;
                description: string;
            }[]
        >('/api/sectors');
    }
    /** GET /api/equipment: envia lineId quando informado; o Django aplica também a restrição do operador. */
    equipment(lineId?: number) {
        // O filtro seleciona a linha na tela; o Django aplica também a restrição do operador.
        return this.httpClient.get<Equipment[]>(
            '/api/equipment',
            lineId
                ? {
                      params: {
                          lineId: lineId,
                      },
                  }
                : {}
        );
    }
    /** GET /api/equipment-types: carrega o catálogo de tipos usado nos formulários de máquinas. */
    types() {
        // As opções vêm do catálogo persistido no banco, evitando duplicar os tipos no frontend.
        return this.httpClient.get<
            {
                id: number;
                name: string;
            }[]
        >('/api/equipment-types');
    }
    /** GET /api/orders: consulta até 200 OS; o painel ao vivo usa /api/line-status para obter todas as ativas. */
    orders() {
        return this.httpClient.get<WorkOrder[]>('/api/orders');
    }
    /** GET /api/problem-types: filtra pelo tipo da máquina e permite incluir inativos para manutenção do catálogo. */
    problemTypes(equipmentTypeId?: number, includeInactive = false) {
        const parameters: Record<string, string | number | boolean> = {};
        if (equipmentTypeId) parameters['equipmentTypeId'] = equipmentTypeId;
        if (includeInactive) parameters['includeInactive'] = true;
        return this.httpClient.get<ProblemType[]>('/api/problem-types', {
            params: parameters,
        });
    }
    /** GET /api/users: devolve as contas; somente administrador é autorizado pelo Django. */
    users() {
        return this.httpClient.get<any[]>('/api/users');
    }
}
