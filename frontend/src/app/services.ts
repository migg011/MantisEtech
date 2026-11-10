/** Reexporta serviços, tipos e guards para simplificar imports; as chamadas HTTP ficam em nucleo/servicos. */
export type { User } from './core/models/user.model';
export type { Line } from './core/models/line.model';
export type { Equipment } from './core/models/equipment.model';
export { Authentication } from './core/services/authentication.service';
export { Api } from './core/services/api.service';
export { authenticationInterceptor } from './core/interceptors/authentication.interceptor';
export { authGuard, rolesGuard } from './core/guards';
