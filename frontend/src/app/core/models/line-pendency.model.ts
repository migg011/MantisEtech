/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
export interface LinePendency {
    id: number;
    work_order_id: number;
    line_id: number;
    line_name: string;
    equipment_model: string | null;
    equipment_serial: string | null;
    description: string;
    priority: string;
    status: 'PENDENTE' | 'RESOLVIDA';
    created_by_name: string;
    created_at: string;
    resolved_by_name: string | null;
    resolved_at: string | null;
    resolution: string;
}
