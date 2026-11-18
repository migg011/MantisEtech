/** Mostra os vencimentos e as OS abertas dos equipamentos cadastrados. */
import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { PREVENTIVE_FREQUENCIES, PreventiveSchedule, PreventiveOrder } from '../../core/models/preventive.model';

interface PlanEvent {
    id:string; reference:string; sector:string; machine:string;
    frequency:string; date:string; time:string; technician:string;
    schedule?:PreventiveSchedule; order?:PreventiveOrder;
}

@Component({
    selector:'app-calendario-preventivo', standalone:true, imports:[CommonModule,FormsModule,MatIconModule],
    templateUrl:'./preventive-calendar.component.html', styleUrl:'./preventive-calendar.component.scss'
})
export class PreventiveCalendar implements OnInit {
    @Input() schedulesValue:PreventiveSchedule[] = [];
    @Input() ordersValue:PreventiveOrder[] = [];
    @Input() dataError = '';
    @Output() execute = new EventEmitter<PreventiveSchedule>();
    private readonly today = new Date();
    year = this.today.getFullYear();
    month = this.today.getMonth();
    selectedDate = '';
    search = '';
    sectorValue = '';
    frequencyValue = '';
    selectedEvent:PlanEvent|null = null;
    diasSemana = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
    frequencies = PREVENTIVE_FREQUENCIES;

    ngOnInit() { this.chooseDay(`${this.monthPrefix}-${String(this.today.getDate()).padStart(2,'0')}`); }

    get calendarEvents():PlanEvent[] {
        const openOrders = this.ordersValue.filter(orderValue => orderValue.status === 'ABERTA');
        const events:PlanEvent[] = this.schedulesValue.filter(scheduleValue => !openOrders.some(orderValue => orderValue.schedule_id === scheduleValue.id)).map(scheduleValue => ({
            id:`schedule-${scheduleValue.id}`, reference:'Vencimento', sector:scheduleValue.sector_name || 'Sem setor', machine:scheduleValue.equipment_name,
            frequency:scheduleValue.frequency, date:scheduleValue.next_due, time:scheduleValue.planned_time?.slice(0,5) || '', technician:'A definir', schedule: scheduleValue
        }));
        for (const orderValue of openOrders) {
            const scheduleValue = this.schedulesValue.find(row => row.id === orderValue.schedule_id);
            events.push({id:`order-${orderValue.id}`, reference:orderValue.number, sector:scheduleValue?.sector_name || 'Sem setor', machine:orderValue.equipment_name,
                frequency:orderValue.frequency, date:orderValue.planned_date, time:orderValue.planned_time?.slice(0,5) || '', technician:orderValue.assigned_name,
                schedule: scheduleValue,order: orderValue});
        }
        return events;
    }
    get sectors() { return [...new Set(this.calendarEvents.map(event => event.sector))].sort(); }
    get filteredEvents() {
        const term = this.search.trim().toLocaleLowerCase('pt-BR');
        return this.calendarEvents.filter(event => (!this.sectorValue || event.sector === this.sectorValue) &&
            (!this.frequencyValue || event.frequency === this.frequencyValue) &&
            `${event.machine} ${event.technician} ${event.reference}`.toLocaleLowerCase('pt-BR').includes(term));
    }
    get monthPrefix() { return `${this.year}-${String(this.month+1).padStart(2,'0')}`; }
    get monthlyEvents() { return this.filteredEvents.filter(event => event.date.startsWith(this.monthPrefix)); }
    get dailyEvents() { return this.filteredEvents.filter(event => event.date === this.selectedDate).sort((a,b) => a.time.localeCompare(b.time) || a.machine.localeCompare(b.machine)); }
    /** Datas são chaves locais AAAA-MM-DD: não usamos toISOString, evitando deslocar dias pelo fuso horário. */
    get days() {
        const offset = (new Date(this.year,this.month,1).getDay()+6)%7;
        const quantityValue = new Date(this.year,this.month+1,0).getDate();
        const grouped = new Map<string,PlanEvent[]>();
        for (const event of this.monthlyEvents) { const bucket = grouped.get(event.date) || []; bucket.push(event); grouped.set(event.date,bucket); }
        return Array.from({length:Math.ceil((offset+quantityValue)/7)*7},(_,index) => {
            const dayValue = index-offset+1;
            const key = `${this.monthPrefix}-${String(dayValue).padStart(2,'0')}`;
            return {day:dayValue>0 && dayValue<=quantityValue ? dayValue : null,date:key,events:grouped.get(key) || []};
        });
    }
    labelText(valueValue:string) { return this.frequencies.find(item => item.value === valueValue)?.label || 'Periodicidade a definir'; }
    clearSelection() { this.selectedDate = `${this.monthPrefix}-01`; this.selectedEvent = null; }
    mudarMes(delta:number) {
        const date = new Date(this.year,this.month+delta,1);
        this.year = date.getFullYear(); this.month = date.getMonth(); this.clearSelection();
    }
    chooseDay(date:string) { this.selectedDate = date; this.selectedEvent = null; }
}
