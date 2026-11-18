import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { EMPTY, catchError, from, map, mergeMap } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Equipment } from '../../core/models/equipment.model';
import { Api } from '../../core/services/api.service';

interface Footprint {
    id: number;
    name: string;
    context: string;
    sectorId: number | null;
    sectorName: string;
    lineName: string | null;
    fallbackImage: string | null;
    layoutImage: string | null;
    length: number;
    width: number;
}

interface Placement {
    machine: Footprint;
    x: number;
    y: number;
    rotated: boolean;
}

interface Area { length: number; width: number; }

const dimensions = (placement: Placement): Area => placement.rotated
    ? { length: placement.machine.width, width: placement.machine.length }
    : { length: placement.machine.length, width: placement.machine.width };

function placementError(candidate: Placement, area: Area, placements: Placement[]): string {
    const size = dimensions(candidate);
    const {x, y} = candidate;
    if (x < 0 || y < 0 || x + size.length > area.length || y + size.width > area.width) {
        return 'O equipamento ultrapassa os limites da área.';
    }
    const overlaps = placements.some(item => {
        if (item.machine.id === candidate.machine.id) return false;
        const other = dimensions(item);
        return x < item.x + other.length && x + size.length > item.x
            && y < item.y + other.width && y + size.width > item.y;
    });
    return overlaps ? 'A posição coincide com outro equipamento.' : '';
}

const machineName = (machine: Equipment) => machine.name?.trim() || machine.model?.trim() || machine.type_name || 'Equipamento';

const equipmentImages: Record<string, string> = {
    'PRINTER': 'printer', 'SPI': 'spi', 'PICK & PLACE': 'pick-place', 'AOI': 'aoi',
    'REFLOW': 'reflow', 'REFLOW OVEN': 'reflow', 'CONVEYOR': 'conveyor', 'BUFFER': 'conveyor',
    'MAGAZINE LOADER': 'loader', 'VACUUM LOADER': 'loader',
};

const layoutImageDirectory = '/assets/equipment/line-simulator/';
const layoutModels: [RegExp, string][] = [
    [/\bVITRONICS\b/, 'vitronics'],
    [/\bJT\b|\bRS[ -]?800N\b/, 'reflow-jt'],
    [/\bDEK\b/, 'dek'],
    [/\bAXXON\b/, 'axxon'],
    [/\bSANCO\b/, 'sanco'],
    [/\bNXT\s*3?\s*[- ]?M6\b/, 'nxt-m6'],
    [/\bNPM[ -]?D3\b/, 'npm-d3'],
];
const layoutTypes: Record<string, string> = {
    CONVEYOR: 'conveyor', TRANSPORTADOR: 'conveyor', BUFFER: 'buffer',
    'MAGAZINE LOADER': 'magazine-loader', AOI: 'aoi', SPI: 'spi',
};

function layoutImageFor(machine: Equipment): string | null {
    const model = [machine.name, machine.model, machine.manufacturer, machine.type_name]
        .filter(Boolean).join(' ').toUpperCase();
    const match = layoutModels.find(([pattern]) => pattern.test(model));
    const asset = match?.[1] || layoutTypes[machine.type_name.trim().toUpperCase()];
    return asset ? layoutImageDirectory + asset + '.png' : null;
}

@Component({
    standalone: true,
    imports: [FormsModule, RouterLink],
    templateUrl: './line-simulator.component.html',
    styleUrl: './line-simulator.component.scss',
})
export class LineSimulator implements OnInit {
    private readonly api = inject(Api);
    private readonly http = inject(HttpClient);
    private readonly photoUrls = new Map<number, string>();
    readonly photos = signal<Record<number, string>>({});
    private readonly destroyRef = inject(DestroyRef);
    private readonly formatter = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
    private drag?: {
        item: Placement;
        pointer: number;
        startX: number;
        startY: number;
        offsetX: number;
        offsetY: number;
        active: boolean;
    };
    private suppressClick = false;

    readonly catalog = signal<Footprint[]>([]);
    readonly incomplete = signal<string[]>([]);
    readonly loading = signal(true);
    readonly loadError = signal(false);
    readonly area = signal<Area>({ length: 12000, width: 6000 });
    readonly placements = signal<Placement[]>([]);
    readonly selectedId = signal<number | null>(null);
    readonly selected = computed(() => this.placements().find(item => item.machine.id === this.selectedId()));
    readonly sectors = signal<{id: number; name: string}[]>([]);
    readonly sectorFilter = signal<number | null>(null);
    readonly destination = signal<number | null>(null);
    readonly search = signal('');
    readonly transfers = computed(() => {
        const destination = this.destination();
        return destination === null ? [] : this.placements().filter(item => item.machine.sectorId !== null && item.machine.sectorId !== destination);
    });
    readonly occupied = computed(() => {
        const items = this.placements();
        const area = items.reduce((total, item) => total + item.machine.length * item.machine.width, 0);
        if (!items.length) return { length: 0, width: 0, area };
        return {
            length: Math.max(...items.map(item => item.x + dimensions(item).length)) - Math.min(...items.map(item => item.x)),
            width: Math.max(...items.map(item => item.y + dimensions(item).width)) - Math.min(...items.map(item => item.y)),
            area,
        };
    });
    readonly available = computed(() => {
        const placed = new Set(this.placements().map(item => item.machine.id));
        const sector = this.sectorFilter();
        const query = this.search().trim().toLocaleLowerCase('pt-BR');
        return this.catalog().filter(machine => !placed.has(machine.id)
            && (sector === null || machine.sectorId === sector)
            && (machine.name + ' ' + machine.context).toLocaleLowerCase('pt-BR').includes(query));
    });
    readonly preview = signal<Placement | null>(null);
    readonly previewError = computed(() => {
        const candidate = this.preview();
        return candidate ? placementError(candidate, this.area(), this.placements()) : '';
    });
    readonly message = signal('');
    readonly isError = signal(false);
    readonly dimensions = dimensions;
    areaLength: number | null = 12;
    areaWidth: number | null = 6;

    ngOnInit() {
        this.destroyRef.onDestroy(() => this.photoUrls.forEach(url => URL.revokeObjectURL(url)));
        this.api.sectors().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: sectors => this.sectors.set(sectors),
            error: () => this.feedback('Não foi possível carregar os setores de destino.', true),
        });
        this.loadEquipment();
    }

    loadEquipment() {
        this.loading.set(true);
        this.loadError.set(false);
        this.api.machinesValue().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
            next: machines => {
                const catalog: Footprint[] = [];
                const incomplete: string[] = [];
                for (const machine of machines) {
                    const length = Math.round(Number(machine.length_mm));
                    const width = Math.round(Number(machine.width_mm));
                    const name = machineName(machine);
                    if (!Number.isFinite(length) || !Number.isFinite(width) || length <= 0 || width <= 0) {
                        incomplete.push(name);
                        continue;
                    }
                    const asset = equipmentImages[machine.type_name.toUpperCase()];
                    catalog.push({
                        id: machine.id, name, length, width,
                        sectorId: machine.sector_id ?? null,
                        sectorName: machine.sector_name || 'Sem setor',
                        lineName: machine.line_name || null,
                        layoutImage: layoutImageFor(machine),
                        fallbackImage: asset ? '/assets/equipment/' + asset + '.png' : null,
                        context: [machine.asset_number || machine.serial || '#' + machine.id, machine.sector_name, machine.line_name]
                            .filter(Boolean).join(' · '),
                    });
                }
                this.catalog.set(catalog.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR')));
                this.incomplete.set(incomplete);
                const ids = new Set(catalog.filter(machine => !machine.layoutImage).map(machine => machine.id));
                this.loadPhotos(machines.filter(machine => machine.has_photo && ids.has(machine.id)));
                this.loading.set(false);
            },
            error: () => {
                this.loadError.set(true);
                this.loading.set(false);
            },
        });
    }

    private loadPhotos(machines: Equipment[]) {
        from(machines).pipe(
            mergeMap(machine => this.http.get('/api/equipment/' + machine.id + '/attachments/PHOTO/download', { responseType: 'blob' })
                .pipe(map(blob => ({ id: machine.id, blob })), catchError(() => EMPTY)), 4),
            takeUntilDestroyed(this.destroyRef),
        ).subscribe(({ id, blob }) => {
            const oldUrl = this.photoUrls.get(id);
            if (oldUrl) URL.revokeObjectURL(oldUrl);
            const url = URL.createObjectURL(blob);
            this.photoUrls.set(id, url);
            this.photos.update(photos => ({ ...photos, [id]: url }));
        });
    }

    imageFor(machine: Footprint) { return machine.layoutImage || this.photos()[machine.id] || machine.fallbackImage; }
    areaInSquareMeters(value: number) { return this.formatter.format(value / 1000000) + ' m²'; }
    freeArea() { return this.areaInSquareMeters(this.area().length * this.area().width - this.occupied().area); }

    meters(value: number) { return this.formatter.format(value / 1000); }
    areaLabel() {
        const {length, width} = this.area();
        return this.meters(length) + ' × ' + this.meters(width) + ' m · ' + this.formatter.format(length * width / 1000000) + ' m²';
    }
    sizeLabel(size: Area) { return this.meters(size.length) + ' × ' + this.meters(size.width) + ' m'; }
    percent(value: number, axis: keyof Area) { return 100 * value / this.area()[axis]; }

    applyArea() {
        const length = Math.round(Number(this.areaLength) * 1000);
        const width = Math.round(Number(this.areaWidth) * 1000);
        if (![length, width].every(value => Number.isFinite(value) && value >= 2000 && value <= 100000)) {
            this.feedback('Informe medidas entre 2 e 100 m.', true);
            return;
        }
        const area = { length, width };
        if (this.placements().some(item => placementError(item, area, this.placements()))) {
            this.feedback('A nova área deixaria equipamentos fora da planta. Reposicione-os antes de aplicar.', true);
            return;
        }
        this.area.set(area);
        this.feedback('Medidas atualizadas.');
    }

    add(machine: Footprint) {
        if (this.suppressClick || this.placements().some(item => item.machine.id === machine.id)) return;
        const items = this.placements();
        const xs = [0, ...items.map(item => item.x + dimensions(item).length)].sort((a, b) => a - b);
        const ys = [0, ...items.map(item => item.y + dimensions(item).width)].sort((a, b) => a - b);
        for (const y of ys) {
            for (const x of xs) {
                for (const rotated of [false, true]) {
                    const candidate = { machine, x, y, rotated };
                    if (!placementError(candidate, this.area(), items)) {
                        this.place(candidate, machine.name + ' adicionado à planta.');
                        return;
                    }
                }
            }
        }
        this.feedback('Não há espaço livre para ' + machine.name + ' na planta.', true);
    }

    select(id: number) {
        if (!this.suppressClick) this.selectedId.set(id);
    }

    rotate(item: Placement) {
        this.place({ ...item, rotated: !item.rotated }, 'Equipamento girado em 90°.');
    }

    remove(item: Placement) {
        this.placements.update(items => items.filter(other => other.machine.id !== item.machine.id));
        this.selectedId.set(null);
        this.feedback('Equipamento removido da planta.');
    }

    nudge(event: KeyboardEvent, item: Placement) {
        const direction = ({ ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] } as Record<string, number[]>)[event.key];
        if (!direction) return;
        event.preventDefault();
        const step = event.shiftKey ? 1000 : 100;
        this.place({ ...item, x: item.x + direction[0] * step, y: item.y + direction[1] * step }, item.machine.name + ' reposicionado.');
    }

    startDrag(event: PointerEvent, machine: Footprint, item?: Placement) {
        if (event.button !== 0 || this.drag) return;
        const source = event.currentTarget as HTMLElement;
        source.setPointerCapture(event.pointerId);
        const rect = source.getBoundingClientRect();
        this.drag = {
            item: item ?? { machine, x: 0, y: 0, rotated: false },
            pointer: event.pointerId, startX: event.clientX, startY: event.clientY,
            offsetX: item ? (event.clientX - rect.left) / rect.width : 0.5,
            offsetY: item ? (event.clientY - rect.top) / rect.height : 0.5,
            active: false,
        };
    }

    moveDrag(event: PointerEvent, floor: HTMLElement) {
        const drag = this.drag;
        if (!drag || drag.pointer !== event.pointerId) return;
        if (!drag.active && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 5) return;
        drag.active = true;
        this.preview.set(this.dropLocation(event, floor, drag));
    }

    finishDrag(event: PointerEvent, floor: HTMLElement) {
        const drag = this.drag;
        if (!drag || drag.pointer !== event.pointerId) return;
        this.clearDrag();
        if (!drag.active || event.type !== 'pointerup') return;
        this.suppressClick = true;
        setTimeout(() => { this.suppressClick = false; }, 0);
        const candidate = this.dropLocation(event, floor, drag);
        if (candidate) {
            const existing = this.placements().some(item => item.machine.id === candidate.machine.id);
            this.place(candidate, candidate.machine.name + (existing ? ' reposicionado.' : ' adicionado à planta.'));
        } else this.feedback('Solte o equipamento dentro da planta.', true);
    }

    onLostCapture(event: PointerEvent) {
        if (this.drag?.pointer === event.pointerId) this.clearDrag();
    }

    private clearDrag() {
        this.drag = undefined;
        this.preview.set(null);
    }

    private dropLocation(event: PointerEvent, floor: HTMLElement, drag: NonNullable<LineSimulator['drag']>): Placement | null {
        const rect = floor.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width;
        const y = (event.clientY - rect.top) / rect.height;
        if (x < 0 || y < 0 || x > 1 || y > 1) return null;
        const size = dimensions(drag.item);
        return {
            ...drag.item,
            x: Math.max(0, Math.min(this.area().length - size.length, Math.round(x * this.area().length - size.length * drag.offsetX))),
            y: Math.max(0, Math.min(this.area().width - size.width, Math.round(y * this.area().width - size.width * drag.offsetY))),
        };
    }

    private place(candidate: Placement, success: string) {
        const error = placementError(candidate, this.area(), this.placements());
        if (error) { this.feedback(error, true); return; }
        const id = candidate.machine.id;
        this.placements.update(items => items.some(item => item.machine.id === id)
            ? items.map(item => item.machine.id === id ? candidate : item)
            : [...items, candidate]);
        this.selectedId.set(id);
        this.feedback(success);
    }

    private feedback(message: string, error = false) {
        this.message.set(message);
        this.isError.set(error);
    }
}
