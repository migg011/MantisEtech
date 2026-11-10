/** Reexporta os componentes de tela utilizados no roteamento; não executa consultas. */
/**
 * Ponto de compatibilidade com as rotas atuais do MANTIS 2.0.
 * Cada tela tem seu próprio componente TS + HTML + SCSS.
 * Quando desejado, main.ts pode importar diretamente de funcionalidades/.
 */
export { Login } from './features/login/login.component';
export { MainLayout } from './features/layout/layout.component';
export { Dashboard } from './features/dashboard/dashboard.component';
export { Totem } from './features/totem/totem.component';
export { OccurrenceDialog } from './features/occurrence-dialog/occurrence-dialog.component';
export { Users } from './features/users/users.component';
export { WorkOrders } from './features/work-orders/work-orders.component';
export { WorkOrderDialog } from './features/work-order-dialog/work-order-dialog.component';
export { SectorEnvironment } from './features/sector-environment/sector-environment.component';
// Componentes separados nas etapas anteriores:
export { Sectors } from './features/sectors/sectors.component';
export { SmtLines } from './features/smt-lines/smt-lines.component';
export { EquipmentRegistration } from './features/equipment/equipment.component';
