import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Mostra as categorias que podem ser usadas no cadastro de peças. */
import {Component, ChangeDetectorRef, DestroyRef, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {HttpClient} from '@angular/common/http';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {firstValueFrom} from 'rxjs';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {FormModal} from '../../shared/form-modal.component';
interface MaterialCategory {id:number;name:string;description:string;active:boolean;part_count:number}
@Component({standalone:true,imports:[CommonModule,FormsModule,RouterLink,MatButtonModule,MatIconModule,FormModal],templateUrl:'./material-categories.component.html',styleUrl:'./material-categories.component.scss'})
export class MaterialCategories implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    private http=inject(HttpClient);
    private detector=inject(ChangeDetectorRef);
    private destroyRef=inject(DestroyRef);
    categoriesValue:MaterialCategory[]=[];
    search='';
    loading=false;
    saving=false;
    formOpen=false;
    editId:number|null=null;
    nameValue='';
    descriptionValue='';
    errorValue='';
    success='';
    get filteredCategories(){const q=this.search.trim().toLocaleLowerCase('pt-BR');return this.categoriesValue.filter(c=>!q||(c.name+' '+c.description).toLocaleLowerCase('pt-BR').includes(q));}
    ngOnInit(){this.load();}
    /** Carrega também as categorias inativas para permitir reativá-las. */
    load(){this.loading=true;this.http.get<MaterialCategory[]>('/api/part-categories',{params:{includeInactive:'true'}}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({next:r=>{this.categoriesValue=r;this.loading=false;this.detector.markForCheck();},error:()=>{this.errorValue='Não foi possível carregar as categorias.';this.loading=false;this.detector.markForCheck();}});}
    openValue(c?:MaterialCategory){this.editId=c?.id??null;this.nameValue=c?.name??'';this.descriptionValue=c?.description??'';this.errorValue='';this.success='';this.formOpen=true;}
    closeValue(){if(!this.saving)this.formOpen=false;}
    async save(){
        if(this.saving||!this.nameValue.trim())return;
        this.saving=true;this.errorValue='';
        try {
            const editId = this.editId;
            const dataValue = {name: this.nameValue, description: this.descriptionValue};
            await firstValueFrom(editId
                ? this.http.patch('/api/part-categories/' + editId, dataValue)
                : this.http.post('/api/part-categories', dataValue));
            this.formOpen = false;
            if (editId) this.success = 'Alterações salvas.';
            else this.registrationFeedback.created('Categoria cadastrada com sucesso', dataValue.name.trim());
            this.load();
        }
        catch(e:any){this.errorValue=e.error?.error||'Não foi possível salvar a categoria.';}
        finally{this.saving=false;this.detector.markForCheck();}
    }
    /** Ativa ou desativa a categoria e mantém seu vínculo com as peças. */
    async toggleActive(c:MaterialCategory){
        if(this.saving)return;
        this.saving=true;this.errorValue='';this.success='';
        try{await firstValueFrom(this.http.patch('/api/part-categories/'+c.id,{active:!c.active}));this.success=c.active?'Categoria desativada.':'Categoria reativada.';this.load();}
        catch(e:any){this.errorValue=e.error?.error||'Não foi possível alterar a categoria.';}
        finally{this.saving=false;this.detector.markForCheck();}
    }
}
