/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
export interface WorkOrder {
    line_id: number | null;
    created_at: string;
    started_at: string | null;
    finished_at: string | null;
    assigned_to: number | null;
    opened_by_name: string;
    assigned_to_name: string | null;
    downtime_minutes: number;
    server_now: string;
    id: number;
    equipment_id: number;
    model: string | null;
    serial: string | null;
    type_name: string;
    asset_number: string | null;
    line_name: string | null;
    problem: string;
    occurrence_description?: string;
    priority: string;
    status: string;
    root_cause: string | null;
    corrective_action: string | null;
    preventive_action: string | null;
}
export interface WorkOrderPart {
    id: number;
    code: string;
    description: string;
    part_number: string | null;
    manufacturer: string | null;
    unit: string;
    storage_location: string | null;
    preferred_supplier: string | null;
    compatible: boolean;
}
export interface WorkOrderPurchase {
    id: number;
    work_order_id: number | null;
    equipment_id: number | null;
    equipment_model: string | null;
    equipment_serial: string | null;
    requester_id: number;
    requester_name: string;
    manager_name: string;
    status: string;
    created_at: string;
}
export interface WorkOrderPartRequisition {
    id: number;
    spare_part_id: number;
    equipment_serial: string | null;
    description: string;
    part_number: string | null;
    quantity: string;
    requester_name: string;
    note: string;
    created_at: string;
}
