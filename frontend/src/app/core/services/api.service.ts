/** Serviço de consultas HTTP compartilhadas. Retorna Observables; o componente faz subscribe para executar a requisição e usar a resposta. */
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Line } from '../models/line.model';
import { Equipment } from '../models/equipment.model';
import { ProblemType } from '../models/problem-type.model';
import { WorkOrder } from '../models/work-order.model';
@Injectable({
    providedIn: 'root'
})
/** Consultas compartilhadas: o proxy encaminha /api ao Django e devolve JSON tipado às telas. */
export class Api {
    httpValue = inject(HttpClient);
    /** GET /api/lines: retorna as linhas visíveis ao usuário; a assinatura ocorre no componente. */
    linesValue() {
        return this.httpValue.get<Line[]>('/api/lines');
    }
    /** GET /api/sectors: consulta setores ativos para listas e seletores. */
    sectors() {
        return this.httpValue.get<{
            id: number;
            code: string;
            name: string;
            description: string;
        }[]>('/api/sectors');
    }
    /** GET /api/equipment: envia lineId quando informado; o Django aplica também a restrição do operador. */
    machinesValue(lineIdValue?: number) {
        // O filtro seleciona a linha na tela; o Django aplica também a restrição do operador.
        return this.httpValue.get<Equipment[]>('/api/equipment', lineIdValue ? {
            params: {
                lineId: lineIdValue
            }
        } : {});
    }
    /** GET /api/equipment-types: carrega o catálogo de tipos usado nos formulários de máquinas. */
    typesValue() {
        // As opções vêm do catálogo persistido no banco, evitando duplicar os tipos no frontend.
        return this.httpValue.get<{
            id: number;
            name: string;
        }[]>('/api/equipment-types');
    }
    /** GET /api/orders: consulta até 200 OS; o painel ao vivo usa /api/line-status para obter todas as ativas. */
    ordersValue() {
        return this.httpValue.get<WorkOrder[]>('/api/orders');
    }
    /** GET /api/problem-types: filtra pelo tipo da máquina e permite incluir inativos para manutenção do catálogo. */
    problemTypes(equipmentTypeIdValue?: number, includeInactiveValue = false) {
        const paramsValue: Record<string, string | number | boolean> = {};
        if (equipmentTypeIdValue)
            paramsValue['equipmentTypeId'] = equipmentTypeIdValue;
        if (includeInactiveValue)
            paramsValue['includeInactive'] = true;
        return this.httpValue.get<ProblemType[]>('/api/problem-types', {
            params: paramsValue
        });
    }
    /** GET /api/users: devolve as contas; somente administrador é autorizado pelo Django. */
    usersValue() {
        return this.httpValue.get<any[]>('/api/users');
    }
}
