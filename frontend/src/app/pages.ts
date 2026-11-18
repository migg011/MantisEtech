/** Reúne os componentes usados pelas rotas. */
/**
 * Ponto de compatibilidade com as rotas atuais do MANTIS 2.0.
 * Cada tela tem seu próprio componente TS + HTML + SCSS.
 * Quando desejado, main.ts pode importar diretamente de funcionalidades/.
 */
export { Login } from './features/login/login.component';
export { Shell } from './features/shell/shell.component';
export { Dashboard } from './features/dashboard/dashboard.component';
export { Kiosk } from './features/kiosk/kiosk.component';
export { ReportDialog } from './features/incident-dialog/incident-dialog.component';
export { Users } from './features/users/users.component';
export { Orders } from './features/work-orders/work-orders.component';
export { OrderDialog } from './features/work-order-dialog/work-order-dialog.component';
export { SectorHome } from './features/sector-home/sector-home.component';
// Componentes separados nas etapas anteriores:
export { Sectors } from './features/sectors/sectors.component';
export { Lines } from './features/smt-lines/smt-lines.component';
export { EquipmentRegistration } from './features/equipment/equipment.component';
