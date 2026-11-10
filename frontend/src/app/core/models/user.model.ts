/** Contrato de dados JSON: tipa a resposta para o Angular; não cria tabelas nem valida requisições no servidor. */
export interface User {
    id: number;
    name: string;
    registration: string;
    role: 'ADMINISTRADOR' | 'TECNICO' | 'OPERADOR';
    lineId: number | null;
}
