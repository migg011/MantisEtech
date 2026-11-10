/** Módulo totem: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    OnDestroy,
    OnInit,
    TemplateRef,
    ViewChild,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import {
    MatDialog,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
    EMPTY,
    Subject,
    catchError,
    finalize,
    takeUntil,
    timer,
    switchMap,
} from 'rxjs';
import {
    Authentication,
    Api,
    Line,
    Equipment as EquipmentData,
} from '../../services';
import { WorkOrder } from '../../core/models/work-order.model';
import { OccurrenceDialog } from '../occurrence-dialog/occurrence-dialog.component';
@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        RouterLink,
        MatButtonModule,
        MatIconModule,
        MatDialogModule,
    ],
    templateUrl: './totem.component.html',
    styleUrl: './totem.component.scss',
})
export class Totem implements OnInit, OnDestroy {
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    private httpClient = inject(HttpClient);
    private route = inject(ActivatedRoute);
    private resetLoading = new Subject<void>();
    private photos: Record<number, string> = {};
    private imagesWithFailure = new Set<number>();
    api = inject(Api);
    authentication = inject(Authentication);
    dialogs = inject(MatDialog);
    ordersLine: WorkOrder[] = [];
    equipmentSelected: EquipmentData | null = null;
    private ratiosPhotos: Record<number, number> = {};
    private photosAdjusted: Record<number, string> = {};
    photosUnavailable = new Set<number>();
    /** Mostra somente as OS do equipamento clicado, inclusive seu histórico disponível. */
    get ordersEquipment() {
        return this.ordersLine.filter(
            (order) => order.equipment_id === this.equipmentSelected?.id
        );
    }
    /** Escala do desenho, não dimensional: conveyors iguais e máquinas principais na mesma altura. */
    heightVisual(machine: EquipmentData): number {
        return machine.type_name.toUpperCase().includes('CONVEYOR') ? 0.62 : 1;
    }
    ratioVisual(machine: EquipmentData): number {
        const photo = this.ratiosPhotos[machine.id];
        if (photo) return photo * this.heightVisual(machine);
        const length = Number(machine.length_mm);
        if (length > 0 && Number.isFinite(length))
            return Math.max(0.3, Math.min(5, length / 1500));
        const type = machine.type_name.toUpperCase();
        return type.includes('REFLOW')
            ? 2.9
            : type.includes('CONVEYOR')
              ? 0.35
              : type.includes('PICK')
                ? 0.65
                : 1;
    }
    get widthMinimumLine(): number {
        // Mantém as imagens reconhecíveis; em telas pequenas a linha pode ser percorrida lateralmente.
        return Math.max(
            640,
            this.equipment.reduce(
                (total, machine) => total + this.ratioVisual(machine),
                0
            ) * 80
        );
    }
    get ratioTotal(): number {
        return Math.max(
            1,
            this.equipment.reduce(
                (total, machine) => total + this.ratioVisual(machine),
                0
            )
        );
    }
    get heightMaximumLine(): number {
        return Math.max(
            1,
            ...this.equipment.map((machine) => this.heightVisual(machine))
        );
    }
    registerPhotoDimensions(machine: EquipmentData, event: Event) {
        const image = event.target as HTMLImageElement;
        // Ignora load atrasado de uma imagem que já foi substituída pela foto cadastrada.
        const expected = this.imageEquipment(machine);
        if (
            !expected ||
            image.currentSrc !== new URL(expected, document.baseURI).href
        )
            return;
        if (!image.naturalHeight) return;
        this.ratiosPhotos[machine.id] =
            image.naturalWidth / image.naturalHeight;
        if (this.photosAdjusted[machine.id]) return;
        // Retira apenas a moldura vazia na exibição; o arquivo cadastrado permanece intacto.
        // Fotos com margens diferentes não devem reservar vãos entre os equipamentos.
        try {
            const sample = document.createElement('canvas');
            const scale = Math.min(
                1,
                512 / Math.max(image.naturalWidth, image.naturalHeight)
            );
            sample.width = Math.max(1, Math.round(image.naturalWidth * scale));
            sample.height = Math.max(
                1,
                Math.round(image.naturalHeight * scale)
            );
            const context = sample.getContext('2d', {
                willReadFrequently: true,
            });
            if (!context) return;
            context.drawImage(image, 0, 0, sample.width, sample.height);
            const pixels = context.getImageData(
                0,
                0,
                sample.width,
                sample.height
            ).data;
            let left = sample.width,
                right = -1,
                top = sample.height,
                base = -1;
            for (let y = 0; y < sample.height; y++)
                for (let x = 0; x < sample.width; x++) {
                    const p = (y * sample.width + x) * 4;
                    if (
                        pixels[p + 3] > 32 &&
                        Math.min(pixels[p], pixels[p + 1], pixels[p + 2]) < 235
                    ) {
                        left = Math.min(left, x);
                        right = Math.max(right, x);
                        top = Math.min(top, y);
                        base = Math.max(base, y);
                    }
                }
            if (right < left || base < top) return;
            // Dois pixels de segurança preservam contornos claros e pés da máquina.
            const x = Math.max(0, left - 2) / scale,
                y = Math.max(0, top - 2) / scale;
            const width = Math.min(
                image.naturalWidth - x,
                (right - left + 5) / scale
            );
            const height = Math.min(
                image.naturalHeight - y,
                (base - top + 5) / scale
            );
            const crop = document.createElement('canvas');
            const reduction = Math.min(1, 1000 / Math.max(width, height));
            crop.width = Math.max(1, Math.round(width * reduction));
            crop.height = Math.max(1, Math.round(height * reduction));
            const drawing = crop.getContext('2d');
            if (!drawing) return;
            drawing.drawImage(
                image,
                x,
                y,
                width,
                height,
                0,
                0,
                crop.width,
                crop.height
            );
            this.photosAdjusted[machine.id] = crop.toDataURL(
                'image/webp',
                0.92
            );
            this.ratiosPhotos[machine.id] = crop.width / crop.height;
            this.changeDetector.markForCheck();
        } catch {
            // Se o navegador não permitir analisar a imagem, mantém a foto original.
        }
    }
    @ViewChild('detailsEquipment', { static: true })
    detailsEquipment!: TemplateRef<unknown>;
    private detailsDialog?: MatDialogRef<unknown>;
    /** Abre os detalhes sobre a linha, para o clique ter resposta visível sem exigir rolagem. */
    selectEquipment(machine: EquipmentData) {
        this.equipmentSelected = machine;
        this.detailsDialog = this.dialogs.open(this.detailsEquipment, {
            width: '1100px',
            maxWidth: '95vw',
            maxHeight: '90vh',
            autoFocus: false,
            ariaLabel:
                'Ordens de serviço de ' + (machine.name || machine.type_name),
            panelClass: 'mantis-form-dialog',
        });
        this.detailsDialog
            .afterClosed()
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                this.equipmentSelected = null;
                this.changeDetector.markForCheck();
            });
    }
    closeDetails() {
        this.detailsDialog?.close();
    }
    now = Date.now();
    adjustmentClock = 0;
    errorOrders = '';
    /** Calcula os minutos de parada de uma OS ativa e mantém o total fixo após o fechamento. */
    minutes(order: WorkOrder) {
        if (order.finished_at) return order.downtime_minutes;
        return Math.max(
            0,
            (this.now + this.adjustmentClock - Date.parse(order.created_at)) /
                60000
        );
    }
    lines: Line[] = [];
    selected: number | null = null;
    equipment: EquipmentData[] = [];
    loading = true;
    error = '';
    updatedIn: Date | null = null;
    /** Resolve a linha selecionada para exibir nome, setor e descrição. */
    get line() {
        return this.lines.find((line) => line.id === this.selected);
    }
    /** Conta as OS não concluídas recebidas para a linha selecionada. */
    get ordersOpen() {
        return this.ordersLine.filter((order) => order.status !== 'CONCLUIDA')
            .length;
    }
    /** Conta máquinas distintas com OS aberta para não duplicar o mesmo equipamento. */
    get machinesAffected() {
        return new Set(
            this.ordersLine
                .filter((order) => order.status !== 'CONCLUIDA')
                .map((order) => order.equipment_id)
        ).size;
    }
    /** Soma o comprimento das máquinas da linha e converte milímetros para metros. */
    get lengthMeters() {
        return (
            this.equipment.reduce(
                (sum, machine) => sum + Number(machine.length_mm || 0),
                0
            ) / 1000
        );
    }
    /** Traduz o perfil autenticado para apresentação na interface. */
    get roleName() {
        return {
            ADMINISTRADOR: 'Administrador',
            TECNICO: 'Técnico',
            OPERADOR: 'Operador',
        }[this.authentication.user()?.role || 'OPERADOR'];
    }
    /** Inicia o relógio da tela, consulta as linhas e seleciona a linha atribuída ao operador quando necessário. */
    ngOnInit() {
        timer(0, 1000)
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                this.now = Date.now();
                this.changeDetector.markForCheck();
            });
        this.api
            .lines()
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => this.changeDetector.markForCheck())
            )
            .subscribe({
                next: (lines) => {
                    this.lines = lines;
                    const lineRequested = Number(
                        this.route.snapshot.queryParamMap.get('lineId')
                    );
                    this.selected =
                        this.authentication.user()?.role === 'OPERADOR'
                            ? this.authentication.user()!.lineId
                            : (lines.find((line) => line.id === lineRequested)
                                  ?.id ??
                              lines[0]?.id ??
                              null);
                    this.load();
                },
                error: () => {
                    this.loading = false;
                    this.error =
                        'Não foi possível carregar as linhas. Tente novamente.';
                },
            });
    }
    // Cancela a consulta anterior para uma troca de linha não exibir máquinas ou fotos desatualizadas.
    /** Cancela a consulta da linha anterior, carrega máquinas/fotos e inicia atualização periódica das OS da linha atual. */
    load() {
        this.resetLoading.next();
        this.releasePhotos();
        this.equipment = [];
        this.equipmentSelected = null;
        this.ratiosPhotos = {};
        this.photosAdjusted = {};
        this.photosUnavailable.clear();
        this.ordersLine = [];
        this.errorOrders = '';
        this.error = '';
        this.updatedIn = null;
        if (!this.selected) {
            this.loading = false;
            return;
        }
        this.loading = true;
        timer(0, 15000)
            .pipe(
                switchMap(() =>
                    this.httpClient
                        .get<WorkOrder[]>(`/api/orders?lineId=${this.selected}`)
                        .pipe(
                            catchError(() => {
                                this.errorOrders =
                                    'Não foi possível atualizar os atendimentos. Nova tentativa em 15 segundos.';
                                this.changeDetector.markForCheck();
                                return EMPTY;
                            })
                        )
                ),
                takeUntil(this.resetLoading),
                takeUntilDestroyed(this.destructionRef)
            )
            .subscribe((orders) => {
                this.ordersLine = orders;
                this.errorOrders = '';
                if (orders[0])
                    this.adjustmentClock =
                        Date.parse(orders[0].server_now) - Date.now();
                this.changeDetector.markForCheck();
            });
        this.api
            .equipment(this.selected)
            .pipe(
                takeUntil(this.resetLoading),
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (machines) => {
                    this.equipment = [...machines].sort(
                        (a, b) => (a.position ?? 99999) - (b.position ?? 99999)
                    );
                    this.updatedIn = new Date();
                    for (const machine of this.equipment)
                        this.loadPhoto(machine);
                },
                error: () => {
                    this.error =
                        'Não foi possível carregar os equipamentos desta linha. Tente novamente.';
                },
            });
    }
    // Fotos cadastradas são baixadas com o token, sem expor a credencial na URL da imagem.
    /** Baixa a foto por HTTP autenticado e cria uma URL de Blob para o elemento img. */
    private loadPhoto(machine: EquipmentData) {
        if (!machine.has_photo) return;
        this.httpClient
            .get(`/api/equipment/${machine.id}/attachments/PHOTO/download`, {
                responseType: 'blob',
            })
            .pipe(
                takeUntil(this.resetLoading),
                takeUntilDestroyed(this.destructionRef),
                catchError(() => {
                    this.photosUnavailable.add(machine.id);
                    return EMPTY;
                }),
                finalize(() => this.changeDetector.markForCheck())
            )
            .subscribe((contentFile) => {
                this.photos[machine.id] = URL.createObjectURL(contentFile);
                delete this.photosAdjusted[machine.id];
                delete this.ratiosPhotos[machine.id];
            });
    }
    /** Prioriza a foto cadastrada e usa uma imagem local por tipo quando não há foto disponível. */
    imageEquipment(machine: EquipmentData): string | null {
        if (this.photosAdjusted[machine.id])
            return this.photosAdjusted[machine.id];
        if (this.photos[machine.id]) return this.photos[machine.id];
        // Havendo foto própria, não exibe outra máquina do catálogo enquanto o download ocorre.
        if (machine.has_photo) return null;
        if (this.imagesWithFailure.has(machine.id)) return null;
        const type = machine.type_name.toUpperCase();
        const images: Record<string, string> = {
            PRINTER: 'printer',
            SPI: 'spi',
            'PICK & PLACE': 'pick-place',
            AOI: 'aoi',
            REFLOW: 'reflow',
            'REFLOW OVEN': 'reflow',
            CONVEYOR: 'conveyor',
            BUFFER: 'conveyor',
            'MAGAZINE LOADER': 'loader',
            'VACUUM LOADER': 'loader',
        };
        return images[type] ? `/assets/equipment/${images[type]}.png` : null;
    }
    /** Libera a imagem com erro e registra a falha para não repetir a mesma tentativa visual. */
    registerFailureImage(machine: EquipmentData) {
        delete this.photosAdjusted[machine.id];
        delete this.ratiosPhotos[machine.id];
        if (this.photos[machine.id]) {
            this.photosUnavailable.add(machine.id);
            URL.revokeObjectURL(this.photos[machine.id]);
            delete this.photos[machine.id];
        } else this.imagesWithFailure.add(machine.id);
    }
    /** Deriva a cor da máquina a partir das OS em espera ou em atendimento recebidas. */
    status(machine: EquipmentData): 'attention' | 'maintenance' | 'clear' {
        if (
            this.ordersLine.some(
                (order) =>
                    order.equipment_id === machine.id &&
                    order.status === 'EM_ANDAMENTO'
            )
        )
            return 'maintenance';
        return this.ordersLine.some(
            (order) =>
                order.equipment_id === machine.id && order.status === 'ABERTA'
        )
            ? 'attention'
            : 'clear';
    }
    /** Traduz o estado visual para OS aberta, em atendimento ou sem OS aberta. */
    labelStatus(machine: EquipmentData) {
        return {
            attention: 'OS aberta',
            maintenance: 'Em atendimento',
            clear: 'Sem OS aberta',
        }[this.status(machine)];
    }
    /** Clique na máquina abre ReportDialog; ao fechar, recarrega a linha para refletir a ocorrência registrada. */
    open(machine: EquipmentData) {
        this.closeDetails();
        this.dialogs
            .open(OccurrenceDialog, {
                width: '680px',
                maxWidth: 'calc(100vw - 32px)',
                panelClass: 'mantis-form-dialog',
                backdropClass: 'sector-dialog-backdrop',
                data: machine,
            })
            .afterClosed()
            .pipe(takeUntilDestroyed(this.destructionRef))
            .subscribe(() => {
                this.load();
            });
    }
    /** Usa o ID da máquina para reutilizar os elementos visuais durante atualizações. */
    identifyMachine(_: number, machine: EquipmentData) {
        return machine.id;
    }
    /** Revoga URLs temporárias de Blob e limpa o controle de imagens. */
    private releasePhotos() {
        Object.values(this.photos).forEach((address) =>
            URL.revokeObjectURL(address)
        );
        this.photos = {};
        this.imagesWithFailure.clear();
    }
    /** Encerra consultas pendentes e libera imagens ao sair da tela. */
    ngOnDestroy() {
        this.closeDetails();
        this.resetLoading.next();
        this.resetLoading.complete();
        this.releasePhotos();
    }
}
