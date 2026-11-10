/** Módulo ordens-servico: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    OnInit,
    inject,
} from '@angular/core';
import { CommonModule, DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, merge, switchMap, timer } from 'rxjs';
import { Authentication, Line } from '../../services';
import { WorkOrderDialog } from '../work-order-dialog/work-order-dialog.component';
import { WorkOrder } from '../../core/models/work-order.model';
interface LineDashboard {
    lines: Line[];
    orders: WorkOrder[];
    server_now: string;
}
interface DashboardRecord {
    line: Line;
    order: WorkOrder | null;
}
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink, MatIconModule],
    templateUrl: './work-orders.component.html',
    styleUrl: './work-orders.component.scss',
})
export class WorkOrders implements OnInit {
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    private httpClient = inject(HttpClient);
    private route = inject(ActivatedRoute);
    private document = inject(DOCUMENT);
    private reload = new Subject<void>();
    private dialogs = inject(MatDialog);
    authentication = inject(Authentication);
    displayMode = !!this.route.snapshot.data['exhibition'];
    lines: Line[] = [];
    orders: WorkOrder[] = [];
    loading = true;
    error = '';
    lineSelected: number | null = null;
    view: 'live' | 'history' = 'live';
    now = Date.now();
    offset = 0;
    updatedIn: Date | null = null;
    page = 0;
    /** Calcula quantas linhas cabem na TV; fora do modo de exposição mantém oito registros por página. */
    get sizePage() {
        return this.displayMode
            ? Math.max(
                  2,
                  Math.min(
                      10,
                      Math.floor(
                          ((this.document.defaultView?.innerHeight || 1080) -
                              310) /
                              105
                      )
                  )
              )
            : 8;
    }
    /** Permite abrir atendimento para técnico/administrador; o backend é a proteção definitiva. */
    get canService() {
        return this.authentication.user()?.role !== 'OPERADOR';
    }
    /** Separa as OS ainda não concluídas do histórico retornado pela API. */
    get ordersActive() {
        return this.orders.filter((order) => order.status !== 'CONCLUIDA');
    }
    /** Conta ocorrências ativas que ainda não possuem horário de início do técnico. */
    get waiting() {
        return this.ordersActive.filter((order) => !order.started_at).length;
    }
    /** Conta as ocorrências ativas cujo atendimento já começou. */
    get inProgress() {
        return this.ordersActive.filter((order) => !!order.started_at).length;
    }
    /** Conta linhas distintas com OS ativa, evitando duplicar a linha quando há várias ocorrências. */
    get linesWithOrders() {
        return new Set(this.ordersActive.map((order) => order.line_id)).size;
    }
    /** Monta as linhas do painel: uma por OS ativa ou uma indicação sem OS; no histórico usa as concluídas. */
    get records(): DashboardRecord[] {
        const lines = this.lines.filter(
            (line) => !this.lineSelected || line.id === this.lineSelected
        );
        if (this.view === 'history')
            return this.orders
                .filter(
                    (order) =>
                        order.status === 'CONCLUIDA' &&
                        lines.some((line) => line.id === order.line_id)
                )
                .map((order) => ({
                    line: lines.find((line) => line.id === order.line_id)!,
                    order: order,
                }));
        return lines
            .flatMap<DashboardRecord>((line) => {
                const orders = this.ordersActive.filter(
                    (order) => order.line_id === line.id
                );
                return orders.length
                    ? orders.map((order) => ({
                          line: line,
                          order: order,
                      }))
                    : [
                          {
                              line: line,
                              order: null,
                          },
                      ];
            })
            .sort(
                (a, b) =>
                    this.classification(a) - this.classification(b) ||
                    a.line.name.localeCompare(b.line.name)
            );
    }
    /** Calcula o total de páginas conforme os registros filtrados e a capacidade da tela. */
    get quantityPages() {
        return Math.max(1, Math.ceil(this.records.length / this.sizePage));
    }
    /** Recorta a página atual; o módulo mantém o índice válido mesmo se o total de registros diminuir. */
    get recordsVisible() {
        const start = (this.page % this.quantityPages) * this.sizePage;
        return this.records.slice(start, start + this.sizePage);
    }
    /** Prioriza espera pelo técnico, depois atendimento, e por último linhas sem OS aberta. */
    private classification(row: DashboardRecord) {
        return row.order ? (row.order.started_at ? 1 : 0) : 2;
    }
    /** Fornece uma chave estável para o Angular reutilizar a linha visual durante as atualizações. */
    keyRecord(_: number, row: DashboardRecord) {
        return row.order ? 'os-' + row.order.id : 'line-' + row.line.id;
    }
    /** Calcula a parada em andamento com referência ao relógio do servidor; para concluídas usa o total registrado. */
    minutes(order: WorkOrder) {
        return order.finished_at
            ? order.downtime_minutes
            : Math.max(
                  0,
                  (this.now + this.offset - Date.parse(order.created_at)) /
                      60000
              );
    }
    /** Inicia relógio e consultas a /api/line-status a cada 15 s; no modo TV alterna páginas e cancela assinaturas ao sair. */
    ngOnInit() {
        timer(0, 1000)
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                this.now = Date.now();
                this.changeDetector.markForCheck();
            });
        timer(15000, 15000)
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                if (this.displayMode)
                    this.page = (this.page + 1) % this.quantityPages;
                this.changeDetector.markForCheck();
            });
        merge(timer(0, 15000), this.reload)
            .pipe(
                switchMap(() =>
                    this.httpClient.get<LineDashboard>('/api/line-status').pipe(
                        catchError(() => {
                            this.loading = false;
                            this.error =
                                'Sem atualização da API. Os dados abaixo podem estar desatualizados. Reconectando automaticamente…';
                            this.changeDetector.markForCheck();
                            return EMPTY;
                        })
                    )
                ),
                takeUntilDestroyed(this.destructionRef)
            )
            .subscribe((data) => {
                this.lines = data.lines;
                this.orders = data.orders;
                this.offset = Date.parse(data.server_now) - Date.now();
                this.updatedIn = new Date(data.server_now);
                this.loading = false;
                this.error = '';
                this.changeDetector.markForCheck();
            });
        const id = Number(this.route.snapshot.queryParamMap.get('orderId'));
        if (
            !this.displayMode &&
            Number.isInteger(id) &&
            id > 0 &&
            this.canService
        ) {
            this.httpClient
                .get<WorkOrder>(`/api/orders/${id}`)
                .pipe(takeUntilDestroyed(this.destructionRef))
                .subscribe({
                    next: (order) => this.edit(order),
                    error: () => {
                        this.error =
                            'Não foi possível consultar a OS vinculada.';
                        this.changeDetector.markForCheck();
                    },
                });
        }
    }
    /** Abre o modal da OS com seus dados e solicita nova consulta ao painel quando o modal é fechado. */
    edit(order: WorkOrder) {
        if (this.displayMode || !this.canService) return;
        this.dialogs
            .open(WorkOrderDialog, {
                data: order,
                width: '980px',
                maxWidth: 'calc(100vw - 32px)',
                panelClass: 'mantis-form-dialog',
                backdropClass: 'sector-dialog-backdrop',
            })
            .afterClosed()
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => this.reload.next());
    }
    /** Pede ou encerra tela cheia pelo navegador; apresenta a alternativa F11 se o pedido for recusado. */
    async fullscreen() {
        try {
            if (this.document.fullscreenElement)
                await this.document.exitFullscreen();
            else await this.document.documentElement.requestFullscreen();
        } catch {
            this.error =
                'Use F11 no navegador para exibir o painel em tela cheia.';
            this.changeDetector.markForCheck();
        }
    }
}
