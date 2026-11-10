/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
export interface ProblemType {
    id: number;
    name: string;
    equipment_type_id: number | null;
    type_name?: string | null;
    priority: string;
    active: boolean;
}
export const PRIORITY_LABELS: Record<string, string> = {
    BAIXA: 'Baixa',
    MEDIA: 'Média',
    ALTA: 'Alta',
    CRITICA: 'Crítica',
};
