/** Define os cards e rotas da Central de Cadastros; os registros permanecem nos módulos e no banco. */
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { Authentication } from '../../services';
@Component({
    selector: 'app-central-cadastros',
    standalone: true,
    imports: [CommonModule, RouterLink, MatIconModule],
    templateUrl: './registration-center.component.html',
    styleUrl: './registration-center.component.scss',
})
/** Centraliza os módulos existentes; cartões sem rota ainda estão em desenvolvimento. */
export class RegistrationCenter {
    authentication = inject(Authentication);
    /** Consulta o perfil local para mostrar os cards administrativos; a API confere a autorização novamente. */
    administrator() {
        return this.authentication.user()?.role === 'ADMINISTRADOR';
    }
    items = [
        {
            title: 'Categorias de materiais',
            description:
                'Cadastre e organize categorias para peças e materiais, como NPM, NXT, Limpeza e EPI.',
            icon: 'category',
            color: '#0f766e',
            route: '/cadastro/categorias',
            adminOnly: true,
        },
        {
            title: 'Pendências de linha',
            description:
                'Pendências das ordens de serviço, organizadas linha por linha e com histórico de resolução.',
            icon: 'pending_actions',
            color: '#b45309',
            route: '/cadastro/pendencias',
            adminOnly: false,
        },
        {
            title: 'Setores',
            description:
                'Gerencie setores, repositórios de equipamentos e linhas SMT.',
            icon: 'domain',
            color: '#16a34a',
            route: '/setores',
            adminOnly: false,
        },
        {
            title: 'Problemas de manutenção',
            description:
                'Problemas pré-cadastrados para abertura de OS, com prioridade e tipo de equipamento.',
            icon: 'report_problem',
            color: '#7c3aed',
            route: '/cadastro/problemas',
            adminOnly: false,
        },
        {
            title: 'Usuários',
            description: 'Cadastro de usuários e controle de perfis.',
            icon: 'people',
            color: '#0891b2',
            route: '/usuarios',
            adminOnly: true,
        },
        {
            title: 'Spare Parts',
            description:
                'Cadastro de peças de reposição e base para controle de estoque.',
            icon: 'inventory_2',
            color: '#c8102e',
            route: '/cadastro/spare-parts',
            adminOnly: false,
        },
        // NOVO MÓDULO DE SOLICITAÇÕES DE COMPRA
        {
            title: 'Solicitações de Compra',
            description:
                'Solicitação de peças para compras nacionais e importações, com validação documental e aprovação do gestor.',
            icon: 'shopping_cart',
            color: '#2563eb',
            route: '/cadastro/compras',
            adminOnly: false,
        },
        {
            title: 'Check List de Preventiva',
            description:
                'OS preventivas, roteiros por equipamento, impressão, execução item por item e alertas para todas as periodicidades, incluindo bimestral.',
            icon: 'fact_check',
            color: '#ca8a04',
            route: '/cadastro/preventivas',
            adminOnly: false,
        },
        // Próxima etapa do produto: o card informa o desenvolvimento, sem simular uma integração ativa.
        {
            title: 'Integração com Inteligência Artificial',
            description:
                'Próxima evolução do MANTIS: assistência inteligente para análise de falhas, consulta técnica e apoio ao planejamento da manutenção.',
            icon: 'psychology',
            color: '#6366f1',
            route: '',
            adminOnly: false,
        },
    ];
}
