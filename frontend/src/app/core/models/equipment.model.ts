/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
import { PreventiveSchedule } from './preventive.model';

export interface Equipment {
    sector_name?: string | null;
    width_mm?: number | string | null;
    height_mm?: number | string | null;
    weight_kg?: number | string | null;
    // Medidas técnicas vêm do mesmo cadastro; valores Decimal do Django podem chegar como texto JSON.
    voltage_v?: number | string | null;
    frequency_hz?: number | string | null;
    current_a?: number | string | null;
    power_w?: number | string | null;
    pneumatic_pressure_bar?: number | string | null;
    description?: string | null;
    process_description?: string | null;
    model_number?: string | null;
    name?: string;
    preventive_schedules?: PreventiveSchedule[];
    id: number;
    equipment_type_id: number;
    type_name: string;
    model: string;
    manufacturer: string;
    asset_number: string;
    serial: string;
    line_id: number | null;
    position: number | null;
    length_mm?: number | string | null;
    line_name?: string | null;
    manufacturing_date_text?: string | null;
    manufacturing_date?: string | null;
    has_photo?: boolean;
    open_order_count?: number;
    in_progress_order_count?: number;
}
