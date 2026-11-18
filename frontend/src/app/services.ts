/** Reúne os serviços e tipos que as telas usam. */
export type { User } from './core/models/user.model';
export type { Line } from './core/models/line.model';
export type { Equipment } from './core/models/equipment.model';
export { Auth } from './core/services/auth.service';
export { Api } from './core/services/api.service';
export { authInterceptor } from './core/interceptors/auth.interceptor';
