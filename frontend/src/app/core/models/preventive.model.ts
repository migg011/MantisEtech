/** Contratos JSON das preventivas: interfaces existem na compilação do Angular, não criam tabelas. Datas da API são textos ISO; a tela formata apenas sua apresentação. */
/** Códigos enviados à API e rótulos usados nos seletores e caixas do cadastro. O backend mantém sua própria validação desses códigos. */
export const PREVENTIVE_PERIODICITIES = [
    { value: 'QUINZENAL', label: 'Quinzenal' },
    { value: 'MENSAL', label: 'Mensal' },
    { value: 'BIMESTRAL', label: 'Bimestral' },
    { value: 'TRIMESTRAL', label: 'Trimestral' },
    { value: 'SEMESTRAL', label: 'Semestral' },
    { value: 'ANUAL', label: 'Anual' },
];

/** Resumo da agenda de uma periodicidade marcada em uma máquina. */
export interface PreventiveSchedule {
    id: number;
    frequency: string;
    next_due: string;
    last_performed: string | null;
}

/** Agenda com identificação da máquina e situação calculada no servidor para os alertas. */
export interface EquipmentPreventive extends PreventiveSchedule {
    equipment_id: number;
    equipment_type_id: number;
    equipment_name: string;
    type_name: string;
    asset_number: string | null;
    serial: string | null;
    sector_name: string | null;
    line_name: string | null;
    days_remaining: number;
    status: 'VENCIDA' | 'HOJE' | 'EM_DIA';
}

/** Registro de execução concluída; order_id pode faltar em históricos anteriores às OS numeradas. */
export interface PreventiveExecution {
    order_id?: number | null;
    order_number?: string | null;
    id: number;
    equipment_id: number;
    equipment_name: string;
    frequency: string;
    performed_date: string;
    previous_due: string;
    next_due: string;
    technician_name: string;
    notes: string;
}

/** Dados resumidos de uma OS para a tabela e as ações da tela. */
export interface PreventiveOrder {
    id: number;
    number: string;
    schedule_id: number;
    equipment_id: number;
    equipment_name: string;
    frequency: string;
    status: 'ABERTA' | 'CONCLUIDA' | 'CANCELADA';
    expected_due: string;
    planned_date: string;
    planned_time: string | null;
    recurrence_basis: 'PLANEJADA' | 'EXECUCAO';
    assigned_to_id: number;
    assigned_name: string;
    executor_name: string;
    performed_date: string | null;
    revision: number;
}

/** OS completa: cópia da máquina na emissão, atividades, resultados e dados preenchidos. */
export interface PreventiveOrderDetails extends PreventiveOrder {
    performed_time: string | null;
    equipment_snapshot: Record<string, string>;
    items: string[];
    results: { status: string; notes: string }[];
    parts: { description: string; partNumber: string; quantity: number }[];
    notes: string;
    safety_instructions: string;
    cancellation_reason: string;
}
