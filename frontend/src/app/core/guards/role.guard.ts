/** Guard funcional de autorização por perfil: exige que o usuário possua um dos perfis permitidos. */
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Authentication } from '../services/authentication.service';

export const rolesGuard: CanActivateFn = (route, state) => {
    const authentication = inject(Authentication);
    const router = inject(Router);
    const user = authentication.user();
    if (!user) {
        return router.parseUrl('/login');
    }
    const allowedRoles = route.data['roles'] as string[] | undefined;
    if (allowedRoles && !allowedRoles.includes(user.role)) {
        return router.parseUrl(
            user.role === 'OPERADOR' ? '/totem' : '/dashboard'
        );
    }
    return true;
};
