/** Guard funcional de autenticação: exige usuário logado, redireciona para /login se ausente. */
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Authentication } from '../services/authentication.service';

export const authGuard: CanActivateFn = (route, state) => {
    const authentication = inject(Authentication);
    const router = inject(Router);
    const user = authentication.user();
    if (!user) {
        return router.parseUrl('/login');
    }
    return true;
};
