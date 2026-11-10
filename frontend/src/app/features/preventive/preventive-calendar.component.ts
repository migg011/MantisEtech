/** Calendário: separa a proposta de 2026 das agendas reais; nenhum clique no modelo emite uma OS. */
import {
    ChangeDetectorRef,
    Component,
    DestroyRef,
    EventEmitter,
    Input,
    OnInit,
    Output,
    inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatIconModule } from '@angular/material/icon';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import {
    PREVENTIVE_PERIODICITIES,
    EquipmentPreventive,
    PreventiveOrder,
} from '../../core/models/preventive.model';

interface ScheduleEvent {
    id: string;
    source_row?: number;
    reference: string;
    sector: string;
    machine: string;
    model?: string;
    frequency: string | null;
    date: string;
    time: string;
    source_date?: string;
    technician: string;
    items: string[];
    warnings: string[];
    schedule?: EquipmentPreventive;
    order?: PreventiveOrder;
}
interface CalendarModel {
    source_file: string;
    events: ScheduleEvent[];
    planning_year: number;
    summary: {
        events: number;
        missing_frequency: number;
        warning_events: number;
    };
    excluded_rows: { row: number; reference: string; reason: string }[];
}

@Component({
    selector: 'app-calendario-preventivo',
    standalone: true,
    imports: [CommonModule, FormsModule, MatIconModule],
    templateUrl: './preventive-calendar.component.html',
    styleUrl: './preventive-calendar.component.scss',
})
export class PreventiveCalendar implements OnInit {
    @Input() schedules: EquipmentPreventive[] = [];
    @Input() orders: PreventiveOrder[] = [];
    @Input() errorData = '';
    @Output() execute = new EventEmitter<EquipmentPreventive>();
    private httpClient = inject(HttpClient);
    private changeDetector = inject(ChangeDetectorRef);
    private destructionRef = inject(DestroyRef);
    calendarModel: CalendarModel | null = null;
    loading = false;
    error = '';
    mode = 'MODELO';
    year = 2026;
    month = 0;
    dateSelected = '';
    search = '';
    sector = '';
    periodicity = '';
    eventSelected: ScheduleEvent | null = null;
    daysWeek = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    months = [
        'Janeiro',
        'Fevereiro',
        'Março',
        'Abril',
        'Maio',
        'Junho',
        'Julho',
        'Agosto',
        'Setembro',
        'Outubro',
        'Novembro',
        'Dezembro',
    ];
    periodicities = PREVENTIVE_PERIODICITIES;

    ngOnInit() {
        this.loadModel();
    }
    /** Apenas consulta a referência preparada no servidor. A origem de 2025 permanece preservada e autenticada. */
    loadModel() {
        this.loading = true;
        this.error = '';
        this.httpClient
            .get<CalendarModel>('/api/preventive-calendar-template')
            .pipe(
                takeUntilDestroyed(this.destructionRef),
                finalize(() => {
                    this.loading = false;
                    this.changeDetector.markForCheck();
                })
            )
            .subscribe({
                next: (data) => {
                    this.calendarModel = data;
                    const first = [...data.events].sort((a, b) =>
                        a.date.localeCompare(b.date)
                    )[0];
                    if (first && !this.dateSelected) {
                        this.month = Number(first.date.slice(5, 7)) - 1;
                        this.dateSelected = first.date;
                    }
                },
                error: () =>
                    (this.error =
                        'Não foi possível carregar o modelo de 2026. Verifique a API e tente novamente.'),
            });
    }
    /** O calendário real mostra os próximos vencimentos e as OS abertas, sem inventar ciclos futuros ou duplicar uma agenda com OS. */
    get events(): ScheduleEvent[] {
        if (this.mode === 'MODELO')
            return this.year === 2026 ? this.calendarModel?.events || [] : [];
        const openOrders = this.orders.filter(
            (order) => order.status === 'ABERTA'
        );
        const events: ScheduleEvent[] = this.schedules
            .filter(
                (schedule) =>
                    !openOrders.some(
                        (order) => order.schedule_id === schedule.id
                    )
            )
            .map((schedule) => ({
                id: `schedule-${schedule.id}`,
                reference: 'Vencimento',
                sector: schedule.sector_name || 'Sem setor',
                machine: schedule.equipment_name,
                frequency: schedule.frequency,
                date: schedule.next_due,
                time: '',
                technician: 'A definir',
                items: [],
                warnings: [],
                schedule: schedule,
            }));
        for (const order of openOrders) {
            const schedule = this.schedules.find(
                (row) => row.id === order.schedule_id
            );
            events.push({
                id: `order-${order.id}`,
                reference: order.number,
                sector: schedule?.sector_name || 'Sem setor',
                machine: order.equipment_name,
                frequency: order.frequency,
                date: order.planned_date,
                time: order.planned_time?.slice(0, 5) || '',
                technician: order.assigned_name,
                items: [],
                warnings: [],
                schedule: schedule,
                order: order,
            });
        }
        return events;
    }
    get sectors() {
        return [...new Set(this.events.map((event) => event.sector))].sort();
    }
    get eventsFiltered() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.events.filter(
            (event) =>
                (!this.sector || event.sector === this.sector) &&
                (!this.periodicity ||
                    (event.frequency || 'NAO_INFORMADA') ===
                        this.periodicity) &&
                `${event.machine} ${event.model || ''} ${event.technician} ${event.reference}`
                    .toLocaleLowerCase('pt-BR')
                    .includes(term)
        );
    }
    get prefixMonth() {
        return `${this.year}-${String(this.month + 1).padStart(2, '0')}`;
    }
    get eventsMonth() {
        return this.eventsFiltered.filter((event) =>
            event.date.startsWith(this.prefixMonth)
        );
    }
    get eventsDay() {
        return this.eventsFiltered
            .filter((event) => event.date === this.dateSelected)
            .sort(
                (a, b) =>
                    a.time.localeCompare(b.time) ||
                    a.machine.localeCompare(b.machine)
            );
    }
    /** Datas são chaves locais AAAA-MM-DD: não usamos toISOString, evitando deslocar dias pelo fuso horário. */
    get days() {
        const offset = (new Date(this.year, this.month, 1).getDay() + 6) % 7;
        const quantity = new Date(this.year, this.month + 1, 0).getDate();
        const grouped = new Map<string, ScheduleEvent[]>();
        for (const event of this.eventsMonth) {
            const bucket = grouped.get(event.date) || [];
            bucket.push(event);
            grouped.set(event.date, bucket);
        }
        return Array.from(
            { length: Math.ceil((offset + quantity) / 7) * 7 },
            (_, index) => {
                const day = index - offset + 1;
                const key = `${this.prefixMonth}-${String(day).padStart(2, '0')}`;
                return {
                    day: day > 0 && day <= quantity ? day : null,
                    date: key,
                    events: grouped.get(key) || [],
                };
            }
        );
    }
    label(value: string | null) {
        return (
            this.periodicities.find((item) => item.value === value)?.label ||
            'Periodicidade a definir'
        );
    }
    /** 2027 começa vazio no modelo; ao mudar de ano consultamos apenas as agendas reais já cadastradas. */
    changeYear() {
        if (this.year !== 2026 && this.mode !== 'REAL') {
            this.mode = 'REAL';
            this.sector = '';
        }
        this.clearSelection();
    }
    changeMode() {
        if (this.mode === 'MODELO') this.year = 2026;
        this.sector = '';
        this.clearSelection();
    }
    clearSelection() {
        this.dateSelected = `${this.prefixMonth}-01`;
        this.eventSelected = null;
    }
    changeMonth(delta: number) {
        const date = new Date(this.year, this.month + delta, 1);
        this.year = date.getFullYear();
        this.month = date.getMonth();
        this.changeYear();
    }
    chooseDay(date: string) {
        this.dateSelected = date;
        this.eventSelected = null;
    }
}
