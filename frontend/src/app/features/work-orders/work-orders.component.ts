/** Módulo ordens-servico: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule, DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, merge, switchMap, timer } from 'rxjs';
import { Auth, Line } from '../../services';
import { OrderDialog } from '../work-order-dialog/work-order-dialog.component';
import { WorkOrder } from '../../core/models/work-order.model';
interface LineBoard {
    lines: Line[];
    orders: WorkOrder[];
    server_now: string;
}
interface BoardRow {
    line: Line;
    order: WorkOrder | null;
}
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink, MatIconModule],
    templateUrl: './work-orders.component.html',
    styleUrl: './work-orders.component.scss'
})
export class Orders implements OnInit {
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    private httpValue = inject(HttpClient);
    private routeValue = inject(ActivatedRoute);
    private documentValue = inject(DOCUMENT);
    private reload = new Subject<void>();
    private dialog = inject(MatDialog);
    authValue = inject(Auth);
    exhibitionValue = !!this.routeValue.snapshot.data['exhibition'];
    linesValue: Line[] = [];
    ordersValue: WorkOrder[] = [];
    loading = true;
    errorValue = '';
    selectedLine: number | null = null;
    view: 'live' | 'history' = 'live';
    nowValue = Date.now();
    offset = 0;
    updatedAt: Date | null = null;
    page = 0;
    /** Calcula quantas linhas cabem na TV; fora do modo de exposição mantém oito registros por página. */
    get pageSize() {
        return this.exhibitionValue ? Math.max(2, Math.min(10, Math.floor(((this.documentValue.defaultView?.innerHeight || 1080) - 310) / 105))) : 8;
    }
    /** Permite abrir atendimento para técnico/administrador; o backend é a proteção definitiva. */
    get canAttend() {
        return this.authValue.userValue()?.role !== 'OPERADOR';
    }
    /** Separa as OS ainda não concluídas do histórico retornado pela API. */
    get activeOrders() {
        return this.ordersValue.filter(orderValue => orderValue.status !== 'CONCLUIDA');
    }
    /** Conta ocorrências ativas que ainda não possuem horário de início do técnico. */
    get waiting() {
        return this.activeOrders.filter(orderValue => !orderValue.started_at).length;
    }
    /** Conta as ocorrências ativas cujo atendimento já começou. */
    get attending() {
        return this.activeOrders.filter(orderValue => !!orderValue.started_at).length;
    }
    /** Conta linhas distintas com OS ativa, evitando duplicar a linha quando há várias ocorrências. */
    get linesWithOrders() {
        return new Set(this.activeOrders.map(orderValue => orderValue.line_id)).size;
    }
    /** Monta as linhas do painel: uma por OS ativa ou uma indicação sem OS; no histórico usa as concluídas. */
    get rowsValue(): BoardRow[] {
        const lines = this.linesValue.filter(lineValue => !this.selectedLine || lineValue.id === this.selectedLine);
        if (this.view === 'history')
            return this.ordersValue.filter(orderValue => orderValue.status === 'CONCLUIDA' && lines.some(lineValue => lineValue.id === orderValue.line_id))
                .map(orderValue => ({
                line: lines.find(lineValue => lineValue.id === orderValue.line_id)!, order: orderValue
            }));
        return lines.flatMap<BoardRow>(lineValue => {
            const orders = this.activeOrders.filter(orderValue => orderValue.line_id === lineValue.id);
            return orders.length ? orders.map(orderValue => ({
                line: lineValue, order: orderValue
            })) : [{
                    line: lineValue, order: null
                }];
        }).sort((a, b) => this.rank(a) - this.rank(b) || a.line.name.localeCompare(b.line.name));
    }
    /** Calcula o total de páginas conforme os registros filtrados e a capacidade da tela. */
    get pageCount() {
        return Math.max(1, Math.ceil(this.rowsValue.length / this.pageSize));
    }
    /** Recorta a página atual; o módulo mantém o índice válido mesmo se o total de registros diminuir. */
    get visibleRows() {
        const start = (this.page % this.pageCount) * this.pageSize;
        return this.rowsValue.slice(start, start + this.pageSize);
    }
    /** Prioriza espera pelo técnico, depois atendimento, e por último linhas sem OS aberta. */
    private rank(row: BoardRow) {
        return row.order ? (row.order.started_at ? 1 : 0) : 2;
    }
    /** Fornece uma chave estável para o Angular reutilizar a linha visual durante as atualizações. */
    rowKey(_: number, row: BoardRow) {
        return row.order ? 'os-' + row.order.id : 'line-' + row.line.id;
    }
    /** Calcula a parada em andamento com referência ao relógio do servidor; para concluídas usa o total registrado. */
    minutes(orderValue: WorkOrder) {
        return orderValue.finished_at ? orderValue.downtime_minutes : Math.max(0, (this.nowValue + this.offset - Date.parse(orderValue.created_at)) / 60000);
    }
    /** Inicia relógio e consultas a /api/line-status a cada 15 s; no modo TV alterna páginas e cancela assinaturas ao sair. */
    ngOnInit() {
        timer(0, 1000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            this.nowValue = Date.now();
            this.cdr.markForCheck();
        });
        timer(15000, 15000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            if (this.exhibitionValue)
                this.page = (this.page + 1) % this.pageCount;
            this.cdr.markForCheck();
        });
        merge(timer(0, 15000), this.reload).pipe(switchMap(() => this.httpValue.get<LineBoard>('/api/line-status').pipe(catchError(() => {
            this.loading = false;
            this.errorValue = 'Sem atualização da API. Os dados abaixo podem estar desatualizados. Reconectando automaticamente…';
            this.cdr.markForCheck();
            return EMPTY;
        }))), takeUntilDestroyed(this.destroyRef)).subscribe(dataValue => {
            this.linesValue = dataValue.lines;
            this.ordersValue = dataValue.orders;
            this.offset = Date.parse(dataValue.server_now) - Date.now();
            this.updatedAt = new Date(dataValue.server_now);
            this.loading = false;
            this.errorValue = '';
            this.cdr.markForCheck();
        });
        const id = Number(this.routeValue.snapshot.queryParamMap.get('orderId'));
        if (!this.exhibitionValue && Number.isInteger(id) && id > 0 && this.canAttend) {
            this.httpValue.get<WorkOrder>(`/api/orders/${id}`).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
                next: orderValue => this.edit(orderValue), error: () => {
                    this.errorValue = 'Não foi possível consultar a OS vinculada.';
                    this.cdr.markForCheck();
                }
            });
        }
    }
    /** Abre o modal da OS com seus dados e solicita nova consulta ao painel quando o modal é fechado. */
    edit(orderValue: WorkOrder) {
        if (this.exhibitionValue || !this.canAttend)
            return;
        this.dialog.open(OrderDialog, {
            data: orderValue, width: '980px', maxWidth: 'calc(100vw - 32px)', panelClass: 'mantis-form-dialog', backdropClass: 'sector-dialog-backdrop'
        })
            .afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.reload.next());
    }
    /** Pede ou encerra tela cheia pelo navegador; apresenta a alternativa F11 se o pedido for recusado. */
    async fullscreen() {
        try {
            if (this.documentValue.fullscreenElement)
                await this.documentValue.exitFullscreen();
            else
                await this.documentValue.documentElement.requestFullscreen();
        }
        catch {
            this.errorValue = 'Use F11 no navegador para exibir o painel em tela cheia.';
            this.cdr.markForCheck();
        }
    }
}
