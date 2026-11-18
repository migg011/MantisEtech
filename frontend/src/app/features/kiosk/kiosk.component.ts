/** Módulo totem: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { ChangeDetectorRef, Component, DestroyRef, OnDestroy, OnInit, TemplateRef, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, finalize, takeUntil, timer, switchMap } from 'rxjs';
import { Auth, Api, Line, Equipment as EquipmentData } from '../../services';
import { WorkOrder } from '../../core/models/work-order.model';
import { ReportDialog } from '../incident-dialog/incident-dialog.component';

type KioskLine = Pick<Line, 'id' | 'name' | 'description' | 'sector_id' | 'sector_name'>;
@Component({
    standalone: true,
    imports: [CommonModule, FormsModule, RouterLink, MatButtonModule, MatIconModule, MatDialogModule],
    templateUrl: './kiosk.component.html',
    styleUrl: './kiosk.component.scss'
})
export class Kiosk implements OnInit, OnDestroy {
    private cdr = inject(ChangeDetectorRef);
    private destroyRef = inject(DestroyRef);
    private httpValue = inject(HttpClient);
    private routeValue = inject(ActivatedRoute);
    private resetLoad = new Subject<void>();
    private photos: Record<number, string> = {};
    private failedImages = new Set<number>();
    api = inject(Api);
    authValue = inject(Auth);
    dialog = inject(MatDialog);
    lineOrders: WorkOrder[] = [];
    selectedEquipment: EquipmentData | null = null;
    private photoRatios: Record<number, number> = {};
    private adjustedPhotos: Record<number, string> = {};
    unavailablePhotos = new Set<number>();
    /** Mostra somente as OS do equipamento clicado, inclusive seu histórico disponível. */
    get equipmentOrders() {
        return this.lineOrders.filter(orderValue => orderValue.equipment_id === this.selectedEquipment?.id);
    }
    /** Escala do desenho, não dimensional: conveyors iguais e máquinas principais na mesma altura. */
    displayHeight(machineValue: EquipmentData): number {
        return machineValue.type_name.toUpperCase().includes('CONVEYOR') ? .62 : 1;
    }
    /** Escala vertical calibrada pela passagem da placa nas fotos de referência. */
    transferHeightScale(machine: EquipmentData): number {
        if (!machine.has_photo) return 1;
        const type = machine.type_name.trim().toUpperCase();
        if (type === 'REFLOW' || type === 'REFLOW OVEN') return 1.27;
        if (type === 'BUFFER') return 1.23;
        return 1;
    }
    usesNarrowPhoto(machine: EquipmentData): boolean {
        const type = machine.type_name.trim().toUpperCase();
        return type === 'SPI' || type === 'AOI' || /^DEK\b/i.test(machine.name?.trim() ?? '');
    }
    displayRatio(machineValue: EquipmentData): number {
        const photoValue = this.photoRatios[machineValue.id];
        if (photoValue) return photoValue * this.displayHeight(machineValue);
        const length = Number(machineValue.length_mm);
        if (length > 0 && Number.isFinite(length)) return Math.max(.3, Math.min(5, length / 1500));
        const kind = machineValue.type_name.toUpperCase();
        return kind.includes('REFLOW') ? 2.9 : kind.includes('CONVEYOR') ? .35 : kind.includes('PICK') ? .65 : 1;
    }
    get minLineWidth(): number {
        // Mantém as imagens reconhecíveis; em telas pequenas a linha pode ser percorrida lateralmente.
        return Math.max(640, this.machinesValue.reduce((total, machineValue) => total + this.displayRatio(machineValue), 0) * 80);
    }
    get totalRatio(): number {
        return Math.max(1, this.machinesValue.reduce((total, machineValue) => total + this.displayRatio(machineValue), 0));
    }
    get maxLineHeight(): number {
        return Math.max(1, ...this.machinesValue.map(machine => this.displayHeight(machine) * this.transferHeightScale(machine)));
    }
    recordPhotoDimensions(machineValue: EquipmentData, event: Event) {
        const image = event.target as HTMLImageElement;
        // Ignora load atrasado de uma imagem que já foi substituída pela foto cadastrada.
        const expected = this.imageFor(machineValue);
        if (!expected || image.currentSrc !== new URL(expected, document.baseURI).href) return;
        if (!image.naturalHeight) return;
        this.photoRatios[machineValue.id] = image.naturalWidth / image.naturalHeight;
        if (this.adjustedPhotos[machineValue.id]) return;
        // Retira apenas a moldura vazia na exibição; o arquivo cadastrado permanece intacto.
        // Fotos com margens diferentes não devem reservar vãos entre os equipamentos.
        try {
            const sample = document.createElement('canvas');
            const scale = Math.min(1, 512 / Math.max(image.naturalWidth, image.naturalHeight));
            sample.width = Math.max(1, Math.round(image.naturalWidth * scale));
            sample.height = Math.max(1, Math.round(image.naturalHeight * scale));
            const context = sample.getContext('2d', {willReadFrequently: true});
            if (!context) return;
            context.drawImage(image, 0, 0, sample.width, sample.height);
            const pixels = context.getImageData(0, 0, sample.width, sample.height).data;
            let left = sample.width, direita = -1, topo = sample.height, base = -1;
            for (let y = 0; y < sample.height; y++) for (let x = 0; x < sample.width; x++) {
                const p = (y * sample.width + x) * 4;
                if (pixels[p + 3] > 32 && Math.min(pixels[p], pixels[p + 1], pixels[p + 2]) < 235) {
                    left = Math.min(left, x); direita = Math.max(direita, x);
                    topo = Math.min(topo, y); base = Math.max(base, y);
                }
            }
            if (direita < left || base < topo) return;
            // Dois pixels de segurança preservam contornos claros e pés da máquina.
            const x = Math.max(0, left - 2) / scale, y = Math.max(0, topo - 2) / scale;
            const width = Math.min(image.naturalWidth - x, (direita - left + 5) / scale);
            const height = Math.min(image.naturalHeight - y, (base - topo + 5) / scale);
            const range = document.createElement('canvas');
            const reduction = Math.min(1, 1000 / Math.max(width, height));
            range.width = Math.max(1, Math.round(width * reduction));
            range.height = Math.max(1, Math.round(height * reduction));
            const drawing = range.getContext('2d');
            if (!drawing) return;
            drawing.drawImage(image, x, y, width, height, 0, 0, range.width, range.height);
            this.adjustedPhotos[machineValue.id] = range.toDataURL('image/webp', .92);
            this.photoRatios[machineValue.id] = range.width / range.height;
            this.cdr.markForCheck();
        } catch {
            // Se o navegador não permitir analisar a imagem, mantém a foto original.
        }
    }
    @ViewChild('equipmentDetails') equipmentDetails!: TemplateRef<unknown>;
    private detailsDialog?: MatDialogRef<unknown>;
    /** Abre os detalhes sobre a linha, para o clique ter resposta visível sem exigir rolagem. */
    selectEquipment(machineValue: EquipmentData) {
        this.selectedEquipment = machineValue;
        this.detailsDialog = this.dialog.open(this.equipmentDetails, {
            width: '1100px', maxWidth: '95vw', maxHeight: '90vh', autoFocus: false,
            ariaLabel: 'Ordens de serviço de ' + (machineValue.name || machineValue.type_name),
            panelClass: 'mantis-form-dialog'
        });
        this.detailsDialog.afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            this.selectedEquipment = null;
            this.cdr.markForCheck();
        });
    }
    closeDetails() { this.detailsDialog?.close(); }
    nowValue = Date.now();
    clockOffset = 0;
    ordersError = '';
    /** Calcula os minutos de parada de uma OS ativa e mantém o total fixo após o fechamento. */
    minutes(orderValue: WorkOrder) {
        if (orderValue.finished_at)
            return orderValue.downtime_minutes;
        return Math.max(0, (this.nowValue + this.clockOffset - Date.parse(orderValue.created_at)) / 60000);
    }
    linesValue: KioskLine[] = [];
    selected: number | null = null;
    nextLineId: number | null = null;
    lineChanging = false;
    lineNotice = '';
    lineChangeError = '';
    machinesValue: EquipmentData[] = [];
    loading = true;
    errorValue = '';
    updatedAt: Date | null = null;
    get isOperator() {
        return this.authValue.userValue()?.role === 'OPERADOR';
    }
    /** Resolve a linha selecionada para exibir nome, setor e descrição. */
    get lineValue() {
        return this.linesValue.find(lineValue => lineValue.id === this.selected);
    }
    /** Conta as OS não concluídas recebidas para a linha selecionada. */
    get openOrdersValue() {
        return this.lineOrders.filter(orderValue => orderValue.status !== 'CONCLUIDA').length;
    }
    /** Conta máquinas distintas com OS aberta para não duplicar o mesmo equipamento. */
    get affectedMachines() {
        return new Set(this.lineOrders.filter(orderValue => orderValue.status !== 'CONCLUIDA').map(orderValue => orderValue.equipment_id)).size;
    }
    /** Soma o comprimento das máquinas da linha e converte milímetros para metros. */
    get lengthMeters() {
        return this.machinesValue.reduce((sum, machineValue) => sum + Number(machineValue.length_mm || 0), 0) / 1000;
    }
    /** Traduz o perfil autenticado para apresentação na interface. */
    get roleName() {
        return {
            ADMINISTRADOR: 'Administrador', TECNICO: 'Técnico', OPERADOR: 'Operador'
        }[this.authValue.userValue()?.role || 'OPERADOR'];
    }
    /** Restaura a linha autorizada pelo servidor ao recarregar o totem. */
    ngOnInit() {
        timer(0, 1000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            this.nowValue = Date.now();
            this.cdr.markForCheck();
        });
        if (this.isOperator) {
            this.loadOperatorLines();
            return;
        }
        this.api.linesValue().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.cdr.markForCheck())).subscribe({
            next: lines => {
                this.linesValue = lines;
                const requestedLine = Number(this.routeValue.snapshot.queryParamMap.get('lineId'));
                this.selected = lines.find(lineValue => lineValue.id === requestedLine)?.id ?? lines[0]?.id ?? null;
                this.load();
            },
            error: () => {
                this.loading = false;
                this.errorValue = 'Não foi possível carregar as linhas. Tente novamente.';
            }
        });
    }

    loadOperatorLines() {
        this.loading = true;
        this.lineChangeError = '';
        this.httpValue.get<{ lineId: number | null; lines: KioskLine[] }>('/api/operator-line')
            .pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.cdr.markForCheck())).subscribe({
                next: ({ lineId, lines }) => {
                    this.linesValue = lines;
                    this.selected = lineId;
                    this.load();
                },
                error: () => {
                    this.loading = false;
                    this.lineChangeError = 'Não foi possível consultar as linhas disponíveis.';
                },
            });
    }

    changeOperatorLine() {
        const leaving = this.selected !== null;
        if (this.lineChanging || (!leaving && this.nextLineId === null)) return;
        const closedLine = this.lineValue?.name;
        const endpoint = '/api/operator-line';
        const request = leaving
            ? this.httpValue.delete<{ lineId: number | null }>(endpoint)
            : this.httpValue.post<{ lineId: number | null }>(endpoint, { lineId: this.nextLineId });
        this.lineChanging = true;
        this.lineChangeError = '';
        request.pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.lineChanging = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: ({ lineId }) => {
                this.closeDetails();
                this.selected = lineId;
                this.nextLineId = null;
                this.lineNotice = leaving && closedLine ? `Acesso à ${closedLine} encerrado.` : '';
                this.load();
                if (leaving) this.loadOperatorLines();
            },
            error: error => {
                this.lineChangeError = error.error?.error || 'Não foi possível atualizar a linha de trabalho. Tente novamente.';
            },
        });
    }
    // Cancela a consulta anterior para uma troca de linha não exibir máquinas ou fotos desatualizadas.
    /** Cancela a consulta da linha anterior, carrega máquinas/fotos e inicia atualização periódica das OS da linha atual. */
    load() {
        this.resetLoad.next();
        this.releasePhotos();
        this.machinesValue = [];
        this.selectedEquipment = null;
        this.photoRatios = {};
        this.adjustedPhotos = {};
        this.unavailablePhotos.clear();
        this.lineOrders = [];
        this.ordersError = '';
        this.errorValue = '';
        this.updatedAt = null;
        if (!this.selected) {
            this.loading = false;
            return;
        }
        this.loading = true;
        timer(0, 15000).pipe(switchMap(() => this.httpValue.get<WorkOrder[]>(`/api/orders?lineId=${this.selected}`).pipe(catchError(() => {
            this.ordersError = 'Não foi possível atualizar os atendimentos. Nova tentativa em 15 segundos.';
            this.cdr.markForCheck();
            return EMPTY;
        }))), takeUntil(this.resetLoad), takeUntilDestroyed(this.destroyRef)).subscribe(orders => {
            this.lineOrders = orders;
            this.ordersError = '';
            if (orders[0])
                this.clockOffset = Date.parse(orders[0].server_now) - Date.now();
            this.cdr.markForCheck();
        });
        this.api.machinesValue(this.selected).pipe(takeUntil(this.resetLoad), takeUntilDestroyed(this.destroyRef), finalize(() => {
            this.loading = false;
            this.cdr.markForCheck();
        })).subscribe({
            next: machinesValueValue => {
                this.machinesValue = [...machinesValueValue].sort((a, b) => (a.position ?? 99999) - (b.position ?? 99999));
                this.updatedAt = new Date();
                for (const machineValue of this.machinesValue)
                    this.loadPhoto(machineValue);
            },
            error: () => {
                this.errorValue = 'Não foi possível carregar os equipamentos desta linha. Tente novamente.';
            }
        });
    }
    // Fotos cadastradas são baixadas com o token, sem expor a credencial na URL da imagem.
    /** Baixa a foto por HTTP autenticado e cria uma URL de Blob para o elemento img. */
    private loadPhoto(machineValue: EquipmentData) {
        if (!machineValue.has_photo)
            return;
        this.httpValue.get(`/api/equipment/${machineValue.id}/attachments/PHOTO/download`, {
            responseType: 'blob'
        }).pipe(takeUntil(this.resetLoad), takeUntilDestroyed(this.destroyRef), catchError(() => {
            this.unavailablePhotos.add(machineValue.id);
            return EMPTY;
        }), finalize(() => this.cdr.markForCheck())).subscribe(blobValue => {
            this.photos[machineValue.id] = URL.createObjectURL(blobValue);
            delete this.adjustedPhotos[machineValue.id];
            delete this.photoRatios[machineValue.id];
        });
    }
    /** Prioriza a foto cadastrada e usa uma imagem local por tipo quando não há foto disponível. */
    imageFor(machineValue: EquipmentData): string | null {
        if (this.adjustedPhotos[machineValue.id]) return this.adjustedPhotos[machineValue.id];
        if (this.photos[machineValue.id])
            return this.photos[machineValue.id];
        // Havendo foto própria, não exibe outra máquina do catálogo enquanto o download ocorre.
        if (machineValue.has_photo) return null;
        if (this.failedImages.has(machineValue.id))
            return null;
        const type = machineValue.type_name.toUpperCase();
        const images: Record<string, string> = {
            'PRINTER': 'printer', 'SPI': 'spi', 'PICK & PLACE': 'pick-place', 'AOI': 'aoi',
            'REFLOW': 'reflow', 'REFLOW OVEN': 'reflow', 'CONVEYOR': 'conveyor', 'BUFFER': 'conveyor',
            'MAGAZINE LOADER': 'loader', 'VACUUM LOADER': 'loader'
        };
        return images[type] ? `/assets/equipamento/${images[type]}.png` : null;
    }
    /** Libera a imagem com erro e registra a falha para não repetir a mesma tentativa visual. */
    imageFailed(machineValue: EquipmentData) {
        delete this.adjustedPhotos[machineValue.id];
        delete this.photoRatios[machineValue.id];
        if (this.photos[machineValue.id]) {
            this.unavailablePhotos.add(machineValue.id);
            URL.revokeObjectURL(this.photos[machineValue.id]);
            delete this.photos[machineValue.id];
        }
        else
            this.failedImages.add(machineValue.id);
    }
    /** Deriva a cor da máquina a partir das OS em espera ou em atendimento recebidas. */
    statusValue(machineValue: EquipmentData): 'attention' | 'maintenance' | 'clear' {
        if (this.lineOrders.some(orderValue => orderValue.equipment_id === machineValue.id && orderValue.status === 'EM_ANDAMENTO'))
            return 'maintenance';
        return this.lineOrders.some(orderValue => orderValue.equipment_id === machineValue.id && orderValue.status === 'ABERTA') ? 'attention' : 'clear';
    }
    /** Traduz o estado visual para OS aberta, em atendimento ou sem OS aberta. */
    statusLabel(machineValue: EquipmentData) {
        return {
            attention: 'OS aberta', maintenance: 'Em atendimento', clear: 'Sem OS aberta'
        }[this.statusValue(machineValue)];
    }
    /** Clique na máquina abre ReportDialog; ao fechar, recarrega a linha para refletir a ocorrência registrada. */
    openValue(machineValue: EquipmentData) {
        this.closeDetails();
        this.dialog.open(ReportDialog, {
            width: '680px', maxWidth: 'calc(100vw - 32px)',
            panelClass: 'mantis-form-dialog', backdropClass: 'sector-dialog-backdrop', data: machineValue
        }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
            this.load();
        });
    }
    /** Usa o ID da máquina para reutilizar os elementos visuais durante atualizações. */
    trackMachine(_: number, machineValue: EquipmentData) {
        return machineValue.id;
    }
    /** Revoga URLs temporárias de Blob e limpa o controle de imagens. */
    private releasePhotos() {
        Object.values(this.photos).forEach(urlValue => URL.revokeObjectURL(urlValue));
        this.photos = {};
        this.failedImages.clear();
    }
    /** Encerra consultas pendentes e libera imagens ao sair da tela. */
    ngOnDestroy() {
        this.closeDetails();
        this.resetLoad.next();
        this.resetLoad.complete();
        this.releasePhotos();
    }
}
