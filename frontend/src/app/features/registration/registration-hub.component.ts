/** Define os cards e rotas da Central de Cadastros; os registros permanecem nos módulos e no banco. */
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { Auth } from '../../services';
@Component({
    selector: 'app-central-cadastros',
    standalone: true,
    imports: [CommonModule, RouterLink, MatIconModule],
    templateUrl: './registration-hub.component.html',
    styleUrl: './registration-hub.component.scss'
})
/** Centraliza os módulos existentes; cartões sem rota ainda estão em desenvolvimento. */
export class RegistrationHub {
    authValue = inject(Auth);
    /** Consulta o perfil local para mostrar os cards administrativos; a API confere a autorização novamente. */
    isAdmin() {
        return this.authValue.userValue()?.role === 'ADMINISTRADOR';
    }
    readonly maintenance = inject(ActivatedRoute).snapshot.data['maintenance'] === true;
    readonly maintenanceItems = [
        {
            title: 'Tipos de equipamento',
            description: 'Cadastre novos tipos para usar no cadastro de equipamentos.',
            icon: 'precision_manufacturing',
            color: '#2563eb',
            route: '/cadastro/manutencao/tipos',
            adminOnly: true
        },
        {
            title: 'Problemas de manutenção',
            description: 'Problemas pré-cadastrados para abertura de OS, com prioridade e tipo de equipamento.',
            icon: 'report_problem',
            color: '#7c3aed',
            route: '/cadastro/problemas',
            adminOnly: false
        },
        {
            title: 'Pendências de linha',
            description: 'Pendências das ordens de serviço, organizadas linha por linha e com histórico de resolução.',
            icon: 'pending_actions',
            color: '#b45309',
            route: '/cadastro/pendencias',
            adminOnly: false
        },
        {
            title: 'Categorias de materiais',
            description: 'Cadastre e organize categorias para peças e materiais, como NPM, NXT, Limpeza e EPI.',
            icon: 'category',
            color: '#0f766e',
            route: '/cadastro/categorias',
            adminOnly: true
        },
    ];
    readonly items = [
        {
            title: 'Setores',
            description: 'Gerencie setores, repositórios de equipamentos e linhas SMT.',
            icon: 'domain',
            color: '#16a34a',
            route: '/setores',
            adminOnly: false
        },
        {
            title: 'Usuários',
            description: 'Cadastro de usuários e controle de perfis.',
            icon: 'people',
            color: '#0891b2',
            route: '/usuarios',
            adminOnly: true
        },
        {
            title: 'Spare Parts',
            description: 'Cadastro de peças de reposição e base para controle de estoque.',
            icon: 'inventory_2',
            color: '#c8102e',
            route: '/cadastro/spare-parts',
            adminOnly: false
        },
        {
            title: 'Registro de atividades',
            description: 'Consulte as ações registradas, quem as executou e quando.',
            icon: 'history',
            color: '#475569',
            route: '/cadastro/atividades',
            adminOnly: true
        },
        {
            title: 'Entrada de nota fiscal',
            description: 'Registre as peças recebidas e cadastre os itens novos da nota.',
            icon: 'receipt_long',
            color: '#c8102e',
            route: '/cadastro/entrada-nota-fiscal',
            adminOnly: true
        },
        // NOVO MÓDULO DE SOLICITAÇÕES DE COMPRA
        {
            title: 'Solicitações de Compra',
            description: 'Solicitação de peças para compras nacionais e importações, com validação documental e aprovação do gestor.',
            icon: 'shopping_cart',
            color: '#2563eb',
            route: '/cadastro/compras',
            adminOnly: false
        },
        {
            title: 'Check List de Preventiva',
            description: 'OS preventivas, roteiros por equipamento, impressão, execução item por item e alertas para todas as periodicidades, incluindo bimestral.',
            icon: 'fact_check',
            color: '#ca8a04',
            route: '/cadastro/preventivas',
            adminOnly: false
        },
        {
            title: 'Manutenção',
            description: 'Tipos de equipamento, problemas de manutenção, pendências de linha e categorias de materiais.',
            icon: 'build',
            color: '#c8102e',
            route: '/cadastro/manutencao',
            adminOnly: false
        },
        {
            title: 'Simulador de linha',
            description: 'Defina as medidas da área e posicione os equipamentos em uma planta em escala.',
            icon: 'architecture',
            color: '#2563eb',
            route: '/cadastro/simulador-linha',
            adminOnly: false
        }
    ];
}
