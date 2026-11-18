/** Mostra a ficha da peça nas telas de cadastro, ordens e compras. */
import {Component, Input, Output, EventEmitter, OnChanges, OnDestroy, ChangeDetectorRef, inject} from '@angular/core';
import {CommonModule} from '@angular/common';
import {HttpClient} from '@angular/common/http';
import {Subscription} from 'rxjs';
import {PartStock} from './part-stock.component';
import {FormModal} from './form-modal.component';

@Component({selector:'app-ficha-peca', standalone:true, imports:[CommonModule,PartStock], templateUrl:'./part-sheet.component.html', styleUrl:'./part-sheet.component.scss'})
export class PartSheet implements OnChanges, OnDestroy {
    @Input({required:true}) partId!:number;
    @Output() stockBusy=new EventEmitter<boolean>();
    updatingStock=false;
    lockStock(valueValue:boolean){this.updatingStock=valueValue;this.stockBusy.emit(valueValue);}
    private http=inject(HttpClient);
    private detector=inject(ChangeDetectorRef);
    private lookups=new Subscription();
    partValue:any=null;
    photoValue=''; errorValue=''; photoError=''; loading=false;
    tab='DADOS';
    ngOnChanges() {
        this.lookups.unsubscribe(); this.lookups=new Subscription();
        if(this.photoValue) URL.revokeObjectURL(this.photoValue);
        this.partValue=null; this.photoValue=this.errorValue=this.photoError=''; this.tab='DADOS';
        if(!this.partId) return;
        this.loading=true;
        this.lookups.add(this.http.get<any>(`/api/spare-parts/${this.partId}/details`).subscribe({
            next:p=>{this.partValue=p;this.loading=false;
                if(p.photo_filename) this.lookups.add(this.http.get(`/api/spare-parts/${p.id}/photo`,{responseType:'blob'}).subscribe({next:blob=>{this.photoValue=URL.createObjectURL(blob);this.detector.markForCheck();},error:()=>{this.photoError='Foto indisponível no momento.';this.detector.markForCheck();}}));
                this.detector.markForCheck();},
            error:()=>{this.loading=false;this.errorValue='Não foi possível consultar a ficha da peça.';this.detector.markForCheck();}
        }));
    }
    custo(valueValue:any,moeda:string) {
        if(valueValue===null || valueValue===undefined || valueValue==='') return 'Não informado';
        const number=Number(valueValue);
        return moeda ? new Intl.NumberFormat('pt-BR',{style:'currency',currency:moeda}).format(number) : number.toLocaleString('pt-BR',{minimumFractionDigits:2})+' (moeda não informada)';
    }
    ngOnDestroy(){this.lookups.unsubscribe();if(this.photoValue)URL.revokeObjectURL(this.photoValue);}
}

@Component({selector:'app-consulta-peca',standalone:true,imports:[CommonModule,FormModal,PartSheet],
 template:`<button type="button" class="consultar-peca" (click)="isOpen=true">{{labelText}}</button><app-modal-formulario *ngIf="isOpen" titulo="Ficha da peça" subtitulo="Identificação, foto e informações da peça cadastrada." icone="inventory_2" [wide]="true" [busy]="updatingStock" (closedValue)="isOpen=false"><app-ficha-peca [partId]="partId" (stockBusy)="updatingStock=$event" /></app-modal-formulario>`,
 styles:[`.consultar-peca{border:0;background:transparent;color:#c8102e;font:inherit;font-weight:600;text-align:left;padding:6px 0;text-decoration:underline;text-underline-offset:3px;cursor:pointer;overflow-wrap:anywhere}`]})
export class PartLookup {
    @Input({required:true}) partId!:number;
    @Input() labelText='Ver ficha';
    isOpen=false;
    updatingStock=false;
}
