/** Relaciona URLs a telas e protege a navegação pelo perfil. A segurança definitiva é conferida também em cada endpoint Django. */
import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { Authentication } from './services';
import {
    Login,
    MainLayout,
    Dashboard,
    Totem,
    SmtLines,
    EquipmentRegistration,
    Sectors,
    SectorEnvironment,
    Users,
    WorkOrders,
} from './pages';
import { MaterialCategories } from './features/material-categories/material-categories.component';
import { RegistrationCenter } from './features/registration/registration-center.component';
import { SpareParts } from './features/spare-parts/spare-parts.component';
import { PartPurchases } from './features/part-purchases/part-purchases.component';
import { LinePendencies } from './features/line-pendencies/line-pendencies.component';
import { ProblemTypes } from './features/problem-types/problem-types.component';
import { Preventive } from './features/preventive/preventive.component';
import { authGuard, rolesGuard } from './core/guards';

// Organiza o acesso às telas. A autorização definitiva continua no Django, inclusive em chamadas diretas à API.
/** Protege rotas exigindo usuário autenticado. */
const protectRoute: CanActivateFn = authGuard;

const maintenanceRoles = {
    // Este grupo permite administrador e técnico; a gestão de usuários abaixo exige apenas administrador.
    roles: ['ADMINISTRADOR', 'TECNICO'],
};

export const routes: Routes = [
    {
        path: 'login',
        component: Login,
    },
    {
        path: 'status-linhas',
        component: WorkOrders,
        canActivate: [protectRoute],
        data: {
            exhibition: true,
        },
    },
    {
        path: '',
        component: MainLayout,
        canActivate: [protectRoute],
        children: [
            {
                path: '',
                pathMatch: 'full',
                redirectTo: 'dashboard',
            },
            {
                path: 'dashboard',
                component: Dashboard,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'totem',
                component: Totem,
            },
            // SETORES
            {
                path: 'setores',
                component: Sectors,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'setores/:id',
                component: SectorEnvironment,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'setores/:id/equipamentos',
                component: EquipmentRegistration,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'setores/:id/linhas',
                component: SmtLines,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            // REDIRECIONAMENTOS
            {
                path: 'linhas',
                pathMatch: 'full',
                redirectTo: 'setores',
            },
            {
                path: 'equipamentos',
                pathMatch: 'full',
                redirectTo: 'setores',
            },
            // USUÁRIOS
            {
                path: 'usuarios',
                component: Users,
                canActivate: [rolesGuard],
                data: {
                    roles: ['ADMINISTRADOR'],
                },
            },
            // ORDENS DE SERVIÇO
            {
                path: 'ordens',
                component: WorkOrders,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            // CENTRAL DE CADASTROS
            {
                path: 'cadastro',
                component: RegistrationCenter,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            // O gerenciamento de categorias fica na Central, protegido para administradores.
            {
                path: 'cadastro/categorias',
                component: MaterialCategories,
                canActivate: [rolesGuard],
                data: { roles: ['ADMINISTRADOR'] },
            },
            // CADASTRO DE PEÇAS
            {
                path: 'cadastro/preventivas',
                component: Preventive,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'cadastro/pendencias',
                component: LinePendencies,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'cadastro/problemas',
                component: ProblemTypes,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            {
                path: 'cadastro/spare-parts',
                component: SpareParts,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
            // SOLICITAÇÕES DE COMPRA
            {
                path: 'cadastro/compras',
                component: PartPurchases,
                canActivate: [rolesGuard],
                data: maintenanceRoles,
            },
        ],
    },
    {
        path: '**',
        redirectTo: '',
    },
];
