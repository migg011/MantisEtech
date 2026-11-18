/** Relaciona URLs a telas e protege a navegação pelo perfil. A segurança definitiva é conferida também em cada endpoint Django. */
import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { Auth } from './services';
import { Feeders } from './features/feeders/feeders.component';
import { EquipmentTypes } from './features/registration/equipment-types.component';
import { Login, Shell, Dashboard, Kiosk, Lines, EquipmentRegistration, Sectors, SectorHome, Users, Orders } from './pages';
import { MaterialCategories } from './features/material-categories/material-categories.component';
import { RegistrationHub } from './features/registration/registration-hub.component';
import { SpareParts } from './features/spare-parts/spare-parts.component';
import { SparePurchase } from './features/part-purchases/part-purchases.component';
import { LinePendencies } from './features/line-issues/line-issues.component';
import { ProblemTypes } from './features/problem-types/problem-types.component';
import { PreventiveChecklists } from './features/preventive-checklists/preventive-checklists.component';
// Organiza o acesso às telas. A autorização definitiva continua no Django, inclusive em chamadas diretas à API.
/** Confere se o perfil do usuário pode abrir a tela. */
const guard: CanActivateFn = (routeValue) => {
    const authValue = inject(Auth);
    const router = inject(Router);
    const userValue = authValue.userValue();
    if (!userValue) {
        return router.parseUrl('/login');
    }
    const requiredValue = routeValue.data['roles'] as string[] | undefined;
    if (requiredValue && !requiredValue.includes(userValue.role)) {
        return router.parseUrl(userValue.role === 'OPERADOR' ? '/totem' : '/dashboard');
    }
    return true;
};
const adminRoles = {
    // Este grupo permite administrador e técnico; a gestão de usuários abaixo exige apenas administrador.
    roles: ['ADMINISTRADOR', 'TECNICO']
};
export const routes: Routes = [
    {
        path: 'login',
        component: Login
    },
    {
        path: 'status-linhas',
        component: Orders,
        canActivate: [guard],
        data: {
            ...adminRoles,
            exhibition: true
        }
    },
    {
        path: '',
        component: Shell,
        canActivate: [guard],
        children: [
            {
                path: '',
                pathMatch: 'full',
                redirectTo: 'dashboard'
            },
            {
                path: 'dashboard',
                component: Dashboard,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'totem',
                component: Kiosk
            },
            // SETORES
            {
                path: 'setores',
                component: Sectors,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'setores/:id',
                component: SectorHome,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'setores/:id/equipamentos',
                component: EquipmentRegistration,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'setores/:id/linhas',
                component: Lines,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'setores/:id/usuarios',
                component: Users,
                canActivate: [guard],
                data: { roles: ['ADMINISTRADOR'] }
            },
            {
                path: 'setores/:id/feeders',
                component: Feeders,
                canActivate: [guard],
                data: adminRoles
            },
            // REDIRECIONAMENTOS
            {
                path: 'linhas',
                pathMatch: 'full',
                redirectTo: 'setores'
            },
            {
                path: 'equipamentos',
                pathMatch: 'full',
                redirectTo: 'setores'
            },
            // USUÁRIOS
            {
                path: 'usuarios',
                component: Users,
                canActivate: [guard],
                data: {
                    roles: ['ADMINISTRADOR']
                }
            },
            // ORDENS DE SERVIÇO
            {
                path: 'ordens',
                component: Orders,
                canActivate: [guard],
                data: adminRoles
            },
            // CENTRAL DE CADASTROS
            {
                path: 'cadastro',
                component: RegistrationHub,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/simulador-linha',
                loadComponent: () => import('./features/line-simulator/line-simulator.component').then(module => module.LineSimulator),
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/manutencao',
                component: RegistrationHub,
                canActivate: [guard],
                data: {...adminRoles, maintenance: true}
            },
            {
                path: 'cadastro/manutencao/tipos',
                component: EquipmentTypes,
                canActivate: [guard],
                data: {roles: ['ADMINISTRADOR']}
            },
            // O gerenciamento de categorias fica na Central, protegido para administradores.
            {
                path: 'cadastro/atividades',
                loadComponent: () => import('./features/registration/activity-log.component').then(module => module.ActivityLogPage),
                canActivate: [guard],
                data: {roles: ['ADMINISTRADOR']}
            },
            {
                path: 'cadastro/categorias',
                component: MaterialCategories,
                canActivate: [guard],
                data: {roles: ['ADMINISTRADOR']}
            },
            // CADASTRO DE PEÇAS
            {
                path: 'cadastro/preventivas',
                component: PreventiveChecklists,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/pendencias',
                component: LinePendencies,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/problemas',
                component: ProblemTypes,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/spare-parts',
                component: SpareParts,
                canActivate: [guard],
                data: adminRoles
            },
            {
                path: 'cadastro/entrada-nota-fiscal',
                loadComponent: () => import('./features/spare-parts/stock-receipt.component').then(module => module.StockReceipt),
                canActivate: [guard],
                data: { roles: ['ADMINISTRADOR'] }
            },
            // SOLICITAÇÕES DE COMPRA
            {
                path: 'cadastro/compras',
                component: SparePurchase,
                canActivate: [guard],
                data: adminRoles
            }
        ]
    },
    {
        path: '**',
        redirectTo: ''
    }
];
