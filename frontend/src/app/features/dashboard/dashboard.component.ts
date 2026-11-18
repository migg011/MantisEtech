/** Carrega os números do painel e prepara o gráfico. */
import {Component,inject,OnInit,OnDestroy,ChangeDetectorRef,LOCALE_ID} from '@angular/core';
import {CommonModule,registerLocaleData} from '@angular/common';
import portugues from '@angular/common/locales/pt';
registerLocaleData(portugues);
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {HttpClient} from '@angular/common/http';
import {MatIconModule} from '@angular/material/icon';
import {Subscription} from 'rxjs';
import {Api,Line} from '../../services';
interface DashboardMetrics {equipment_total:number;equipment_active:number;equipment_fault:number;open_orders:number;availability_pct:number|null;mttr_hours:number|null;mttr_sample:number;mtbf_hours:number|null;}
interface DashboardSummary {generated_at:string;days:number;start_date:string;end_date:string;summary:DashboardMetrics;distribution:{corrective:number;preventive:number;predictive:number|null};evolution:{date:string;opened:number;closed:number}[];latest_orders:{id:number;number:string;equipment:string;kind:string;status:string;created_at:string}[];}
@Component({standalone:true,providers:[{provide:LOCALE_ID,useValue:'pt-BR'}],imports:[CommonModule,FormsModule,RouterLink,MatIconModule],templateUrl:'./dashboard.component.html',styleUrl:'./dashboard.component.scss'})
export class Dashboard implements OnInit,OnDestroy {
 private http=inject(HttpClient);private api=inject(Api);private cd=inject(ChangeDetectorRef);
 private lookup?:Subscription;private lineLookup?:Subscription;
 linesValue:Line[]=[];lineIdValue='';days=30;dataValue:DashboardSummary|null=null;loading=false;errorValue='';lineError='';
 openedPath='';closedPath='';openedPoints:{x:number;y:number}[]=[];closedPoints:{x:number;y:number}[]=[];
 labels:{x:number;text:string}[]=[];marks:{y:number;value:number}[]=[];
 ngOnInit(){this.lineLookup=this.api.linesValue().subscribe({next:x=>{this.linesValue=x;this.cd.markForCheck();},error:()=>{this.lineError='Filtro de linhas indisponível.';this.cd.markForCheck();}});this.load();}
 load(){
  this.lookup?.unsubscribe();this.loading=true;this.errorValue='';this.dataValue=null;
  const params:Record<string,string>={days:String(this.days)};if(this.lineIdValue)params['lineId']=this.lineIdValue;
  this.lookup=this.http.get<DashboardSummary>('/api/dashboard',{params}).subscribe({next:d=>{this.dataValue=d;this.prepareChart(d);this.loading=false;this.cd.markForCheck();},error:()=>{this.errorValue='Não foi possível atualizar os indicadores. Tente novamente.';this.loading=false;this.cd.markForCheck();}});
 }
 get periodTotal(){return this.dataValue ? this.dataValue.distribution.corrective+this.dataValue.distribution.preventive : 0;}
 percentage(valueValue:number){return this.periodTotal ? Math.round(100*valueValue/this.periodTotal) : 0;}
 get typeRing(){const p=this.dataValue ? this.percentage(this.dataValue.distribution.preventive):0;return this.periodTotal ? `conic-gradient(#2664ca 0% ${p}%,#ed3b48 ${p}% 100%)` : '#e9edf4';}
 get availabilityRing(){return `conic-gradient(#12a45a 0% ${this.dataValue?.summary.availability_pct ?? 0}%,#e8f2ed 0%)`;}
 statusValue(status:string){return ({ABERTA:'Aberta',EM_ANDAMENTO:'Em andamento',CONCLUIDA:'Concluída',CANCELADA:'Cancelada'} as Record<string,string>)[status]||status;}
 prepareChart(d:DashboardSummary){
  const n=d.evolution.length;const largest=Math.max(1,...d.evolution.flatMap(x=>[x.opened,x.closed]));const ceiling=Math.ceil(largest/4)*4;
  const x=(i:number)=>36+i*568/Math.max(1,n-1),y=(v:number)=>174-v/ceiling*144;
  this.marks=Array.from({length:5},(_,i)=>({y:y(i*ceiling/4),value:i*ceiling/4}));
  this.openedPath=d.evolution.map((p,i)=>`${x(i)},${y(p.opened)}`).join(' ');
  this.closedPath=d.evolution.map((p,i)=>`${x(i)},${y(p.closed)}`).join(' ');
  this.openedPoints=n<=7?d.evolution.map((p,i)=>({x:x(i),y:y(p.opened)})):[];
  this.closedPoints=n<=7?d.evolution.map((p,i)=>({x:x(i),y:y(p.closed)})):[];
  const indices=[...new Set(Array.from({length:Math.min(7,n)},(_,i)=>Math.round(i*(n-1)/Math.max(1,Math.min(7,n)-1))))];
  this.labels=indices.map(i=>({x:x(i),text:d.evolution[i].date.slice(8,10)+'/'+d.evolution[i].date.slice(5,7)}));
 }
 ngOnDestroy(){this.lookup?.unsubscribe();this.lineLookup?.unsubscribe();}
}
