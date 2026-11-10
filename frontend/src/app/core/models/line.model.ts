/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
export interface Line {
    id: number;
    code: string;
    name: string;
    description?: string;
    sector_id?: number | null;
    sector_name?: string;
    equipment_count?: number;
    length_mm?: string;
}
