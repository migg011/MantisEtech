import {RegistrationFeedback} from './registration-feedback';
/** Mostra o saldo e registra movimentações da peça. */
import {Component,Input,Output,EventEmitter,OnChanges,OnDestroy,inject,ChangeDetectorRef,LOCALE_ID} from '@angular/core';
import {CommonModule,registerLocaleData} from '@angular/common';
import portugues from '@angular/common/locales/pt';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {Subscription,finalize} from 'rxjs';
import {Auth} from '../services';
registerLocaleData(portugues);
@Component({selector:'app-estoque-peca',standalone:true,providers:[{provide:LOCALE_ID,useValue:'pt-BR'}],imports:[CommonModule,FormsModule],templateUrl:'./part-stock.component.html',styleUrl:'./part-stock.component.scss'})
export class PartStock implements OnChanges,OnDestroy {
 @Input({required:true}) partId!:number;
 @Output() busyChange=new EventEmitter<boolean>();
 private readonly feedback = inject(RegistrationFeedback);
 private http=inject(HttpClient);private auth=inject(Auth);private cd=inject(ChangeDetectorRef);
 private lookups=new Subscription();partValue:any=null;movements:any[]=[];errorValue='';busy=false;loadingHistory=false;historyError='';
 sectors: {id: number; name: string; cost_center: string}[] = [];
 sectorId: number | null = null;
 location = '';
 kind='ENTRADA';quantityValue:number|null=null;noteValue='';keyValue='';supplier='';documentValue='';
 today=this.currentDate();movementDate=this.today;
 private currentDate(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
 isAdmin(){return this.auth.userValue()?.role==='ADMINISTRADOR';}
 get entry(){return this.kind==='ENTRADA'||this.kind==='INICIAL';}
 get operationTitle(){return ({INICIAL:'Primeiro registro do estoque',ENTRADA:'Entrada de peças',SAIDA:'Saída para manutenção',AJUSTE:'Ajustar quantidade contada'} as Record<string,string>)[this.kind];}
 get expectedBalance(){if(this.quantityValue===null||!Number.isFinite(Number(this.quantityValue)))return null;const q=Number(this.quantityValue),s=Number(this.partValue?.stock_quantity??0);return this.kind==='ENTRADA'?s+q:this.kind==='SAIDA'?s-q:q;}
 get wholeUnits(){return this.partValue?.unit?.trim().toUpperCase()==='UN';}
 get fractionalUnitQuantity(){return this.wholeUnits && this.quantityValue!==null && !Number.isInteger(this.quantityValue);}
 get canSave(){return !!this.partValue && this.isAdmin() && this.sectorId !== null && !this.busy && !this.fractionalUnitQuantity && this.quantityValue!==null && Number.isFinite(Number(this.quantityValue)) && this.quantityValue>=0 && (this.kind==='INICIAL'||this.kind==='AJUSTE'||this.quantityValue>0) && this.expectedBalance!==null && this.expectedBalance>=0 && this.expectedBalance<100000000000 && this.movementDate.length===10 && this.movementDate<=this.today && this.movementDate>='1900-01-01' && this.noteValue.length<=500;}
 ngOnChanges(){this.lookups.unsubscribe();this.lookups=new Subscription();this.partValue=null;this.movements=[];this.quantityValue=null;this.noteValue=this.keyValue=this.supplier=this.documentValue=this.errorValue='';this.today=this.currentDate();this.movementDate=this.today;
  if (this.sectorId !== null) this.load();
  else this.lookups.add(this.http.get<typeof this.sectors>('/api/sectors').subscribe({
   next: sectors => {
    this.sectors = sectors;
    if (sectors.length === 1) this.selectSector(sectors[0].id);
    this.cd.markForCheck();
   },
   error: () => { this.errorValue = 'Não foi possível consultar os setores.'; this.cd.markForCheck(); },
  }));
 }
 selectSector(id: number | null) {
  this.sectorId = id;
  this.ngOnChanges();
 }
 load(redefinirOperacao=true){
  const params = {sectorId: String(this.sectorId)};
  this.lookups.add(this.http.get<any>(`/api/spare-parts/${this.partId}/details`, {params}).subscribe({next:p=>{this.partValue=p;this.location=p.storage_location || '';if(redefinirOperacao)this.kind=p.stock_quantity===null?'INICIAL':'ENTRADA';this.cd.markForCheck();},error:()=>{this.errorValue='Não foi possível consultar o saldo.';this.cd.markForCheck();}}));
  this.loadingHistory=true;this.historyError='';
  this.lookups.add(this.http.get<any[]>(`/api/spare-parts/${this.partId}/stock-movements`, {params}).subscribe({next:m=>{this.movements=m;this.loadingHistory=false;this.cd.markForCheck();},error:()=>{this.historyError='Não foi possível carregar o histórico.';this.loadingHistory=false;this.cd.markForCheck();}}));
 }
 change(){this.keyValue='';}
 selectType(kind:string){if(this.busy)return;this.kind=kind;this.quantityValue=null;this.noteValue=this.supplier=this.documentValue='';this.change();this.errorValue='';}
 save(){
  if(!this.canSave)return;
  this.busy=true;this.busyChange.emit(true);this.errorValue='';
  // Se a rede falhar, repete o pedido com a mesma chave para evitar duplicação.
  this.keyValue ||= crypto.randomUUID();
  const savedType=this.kind;
  const dataValue={sectorId:this.sectorId,storageLocation:this.location,kind:this.kind,quantity:this.quantityValue,movementDate:this.movementDate,note:this.noteValue,supplier:this.entry?this.supplier:'',documentReference:this.entry?this.documentValue:'',requestKey:this.keyValue};
  this.lookups.add(this.http.post(`/api/spare-parts/${this.partId}/stock-movements`,dataValue).pipe(finalize(()=>{this.busy=false;this.busyChange.emit(false);this.cd.markForCheck();})).subscribe({next:()=>{this.quantityValue=null;this.noteValue=this.keyValue=this.supplier=this.documentValue='';this.movementDate=this.today;const title = savedType === 'ENTRADA' ? 'Entrada registrada com sucesso'
     : savedType === 'SAIDA' ? 'Saída registrada com sucesso' : 'Contagem salva com sucesso';
   const part = this.partValue;
   this.feedback.show(title, [part.part_number || part.code, part.description].filter(Boolean).join(' · '), 'Voltar ao estoque');
   this.load();},error:e=>{this.errorValue=e.error?.error||'Não foi possível registrar. Você pode tentar novamente.';}}));
 }
 ngOnDestroy(){this.lookups.unsubscribe();}
}
