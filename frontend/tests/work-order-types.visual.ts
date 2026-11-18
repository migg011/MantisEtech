// Prévia isolada de navegação e gravação. Não chama nem altera o banco real.
import {bootstrapApplication} from '@angular/platform-browser';
import {provideRouter,ActivatedRoute,convertToParamMap} from '@angular/router';
import {HttpClient} from '@angular/common/http';
import {of,throwError} from 'rxjs';
import {PreventiveChecklists} from '../src/app/features/preventive-checklists/preventive-checklists.component';
import {Api,Auth} from '../src/app/services';
const maquina:any={id:1,equipment_type_id:1,type_name:'PRINTER',name:'DEK — demonstração',model:'Horizon',asset_number:'ATV-002',serial:'SN-DEMO-002',manufacturer:'DEK',line_id:1,line_name:'SMT-01',sector_name:'Produção',position:2,preventive_schedules:[{id:1,frequency:'MENSAL',next_due:'2026-12-02',last_performed:null}]};
const agendas=()=>maquina.preventive_schedules.map((s:any)=>({...s,equipment_id:1,equipment_type_id:1,equipment_name:maquina.name,type_name:'PRINTER',status:'EM_DIA',days_remaining:30}));
bootstrapApplication(PreventiveChecklists,{providers:[provideRouter([]),{provide:ActivatedRoute,useValue:{snapshot:{queryParamMap:convertToParamMap({equipmentId:'1',tab:'TIPOS_OS'})}}},{provide:Api,useValue:{typesValue:()=>of([{id:1,name:'PRINTER'}]),machinesValue:()=>of([maquina])}},{provide:Auth,useValue:{user:()=>({id:1,name:'Usuário de teste',role:'ADMINISTRADOR'})}},{provide:HttpClient,useValue:{get:(url:string)=>{
 if(url==='/api/preventive-schedules')return of({today:'2026-11-02',schedules:agendas(),unconfigured_count:0});
 if(url==='/api/preventive-orders/technicians')return of([{id:1,name:'Técnico de teste'}]);
 if(url==='/api/preventive-orders'||url==='/api/preventive-executions'||url.endsWith('/attachments')||url.endsWith('/movements'))return of([]);
 if(url==='/api/preventive-checklists')return of({items:['Inspecionar sensores','Conferir lubrificação'],source:'EQUIPAMENTO'});
 return throwError(()=>new Error('Consulta não simulada'));
},patch:(url:string,dados:any)=>{if(url==='/api/equipment/1'){maquina.preventive_schedules=dados.preventiveSchedules.map((s:any,i:number)=>({id:i+1,frequency:s.frequency,next_due:s.nextDue||'2026-12-02',last_performed:null}));return of({...maquina});}return throwError(()=>new Error('Gravação não simulada'));}}}]}).catch(console.error);
