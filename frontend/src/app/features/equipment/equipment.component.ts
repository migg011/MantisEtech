import {SUPPRESS_EDIT_DIALOG} from '../../core/interceptors/auth.interceptor';
import {RegistrationFeedback} from '../../shared/registration-feedback';
/** Módulo equipamentos: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { AttachmentKind, EquipmentAttachment, EquipmentDocuments } from '../../shared/equipment-documents.component';
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import { Component, inject, OnInit, signal, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterOutlet, ActivatedRoute } from '@angular/router';
import { HttpContext, HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatCardModule } from '@angular/material/card';
import { Auth, Api, Line, Equipment as EquipmentData } from '../../services';
import { PREVENTIVE_FREQUENCIES } from '../../core/models/preventive.model';
const UI = [FormModal, EquipmentDocuments, CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatIconModule, MatSelectModule, MatToolbarModule, MatDialogModule, MatCardModule, RouterLink];
type TechnicalReference = Record<string, string | number | null>;

@Component({
    standalone: true,
    imports: UI,
    templateUrl: './equipment.component.html',
    styleUrl: './equipment.component.scss'
})
/** Controla cadastro técnico e anexos; o Django valida dados, permissões e conteúdo dos arquivos. */
export class EquipmentRegistration implements OnInit {
    private readonly registrationFeedback = inject(RegistrationFeedback);
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    api = inject(Api);
    authValue = inject(Auth);
    routeValue = inject(ActivatedRoute);
    httpValue = inject(HttpClient);
    sectorIdValue: number | null = null;
    sectors: {
        id: number;
        name: string;
    }[] = [];
    /** Resolve o nome do setor selecionado a partir da lista carregada da API. */
    sectorName(): string {
        if (this.sectorIdValue === null) {
            return 'Nenhum setor selecionado';
        }
        const sectorValue = this.sectors.find(s => Number(s.id) === Number(this.sectorIdValue));
        return sectorValue?.name || 'Setor não encontrado';
    }
    /** Controla a exibição das ações administrativas de máquinas pelo perfil local. */
    isAdmin() {
        return this.authValue.userValue()?.role === 'ADMINISTRADOR';
    }
    typesValue: {
        id: number;
        name: string;
    }[] = [];
    machinesValue: EquipmentData[] = [];
    transferMachine: EquipmentData | null = null;
    destinationSector: number | null = null;
    transferReason = '';
    transferring = false;
    transferError = '';
    transferMessage = '';
    historyMachine: EquipmentData | null = null;
    history: {action: string; from_sector_name: string | null; to_sector_name: string | null; from_line: string | null; to_line: string | null; performed_by_name: string; created_at: string; reason: string}[] = [];
    loadingHistory = false;
    historyError = '';
    private historyLookup = 0;
    get destinationSectors() { return this.sectors.filter(sectorValue => sectorValue.id !== this.sectorIdValue); }
    openTransfer(machineValue: EquipmentData) {
        if (!this.isAdmin() || machineValue.line_id || this.transferring) return;
        this.transferMachine = machineValue;
        this.destinationSector = null;
        this.transferReason = this.transferError = this.transferMessage = '';
    }
    closeTransfer() { if (!this.transferring) this.transferMachine = null; }
    /** A API trava a máquina e confere o setor de origem novamente antes de gravar. */
    async transfer() {
        if (!this.transferMachine || !this.sectorIdValue || !this.destinationSector || this.transferring || this.transferReason.trim().length < 3) return;
        this.transferring = true;
        this.transferError = '';
        const machineValue = this.transferMachine;
        const destination = this.sectors.find(sectorValue => sectorValue.id === this.destinationSector)?.name || '';
        try {
            await firstValueFrom(this.httpValue.post(`/api/equipment/${machineValue.id}/transfer`, {
                originSectorId: this.sectorIdValue, destinationSectorId: this.destinationSector, reason: this.transferReason.trim()
            }));
            this.transferMachine = null;
            this.transferMessage = `${machineValue.name || machineValue.model || machineValue.type_name} transferido para ${destination}. Cadastro, anexos e histórico preservados.`;
            this.selectedEquipment = 0;
            this.loadData();
        } catch (errorValue: any) {
            this.transferError = errorValue.error?.error || 'Não foi possível transferir o equipamento.';
        } finally { this.transferring = false; this.cdr.markForCheck(); }
    }
    /** Histórico pertence ao equipamento, mesmo depois de mudar de repositório. */
    openHistory(machineValue: EquipmentData) {
        const lookup = ++this.historyLookup;
        this.historyMachine = machineValue;
        this.history = [];
        this.historyError = '';
        this.loadingHistory = true;
        this.httpValue.get<typeof this.history>(`/api/equipment/${machineValue.id}/movements`).subscribe({
            next: items => {
                if (lookup !== this.historyLookup) return;
                this.history = items; this.loadingHistory = false;
                this.cdr.markForCheck();
            },
            error: () => {
                if (lookup !== this.historyLookup) return;
                this.historyError = 'Não foi possível consultar o histórico.'; this.loadingHistory = false;
                this.cdr.markForCheck();
            }
        });
    }
    closeHistory() { ++this.historyLookup; this.historyMachine = null; }
    movementLabel(action: string) { return ({TRANSFERENCIA:'Transferência entre setores', ALOCACAO:'Alocação na linha', REMOCAO:'Retirada da linha', DESMONTAGEM:'Desmontagem da linha'} as Record<string,string>)[action] || action; }
    selectedEquipment = 0;
    errorValue = '';
    success = '';
    saving = false;
    showForm = false;
    /** Limpa os dados anteriores e abre o modal para uma máquina nova. */
    newEquipment() {
        this.cancelEdit();
        this.success = '';
        this.showForm = true;
    }
    currentEditId: number | null = null;
    chosenPhoto: File | null = null;
    photoError = '';
    chosenManual: File | null = null;
    chosenElectrical: File | null = null;
    editAttachments: EquipmentAttachment[] = [];
    loadingEditAttachments = false;
    editAttachmentsError = '';
    private editAttachmentLookup = 0;
    nomeAnexoSalvo(kindValue: AttachmentKind) {
        return this.editAttachments.find(anexo => anexo.kind === kindValue)?.filename;
    }
    /** Consulta os arquivos persistidos separadamente do seletor de novos arquivos do navegador. */
    private loadEditAttachments(id: number) {
        const lookup = ++this.editAttachmentLookup;
        this.editAttachments = [];
        this.editAttachmentsError = '';
        this.loadingEditAttachments = true;
        this.httpValue.get<EquipmentAttachment[]>(`/api/equipment/${id}/attachments`).subscribe({
            next: anexos => {
                if (lookup !== this.editAttachmentLookup || this.currentEditId !== id) return;
                this.editAttachments = anexos;
                this.loadingEditAttachments = false;
                this.cdr.markForCheck();
            },
            error: () => {
                if (lookup !== this.editAttachmentLookup || this.currentEditId !== id) return;
                this.editAttachmentsError = 'Não foi possível consultar os arquivos já salvos. Eles não serão removidos ao salvar o cadastro.';
                this.loadingEditAttachments = false;
                this.cdr.markForCheck();
            }
        });
    }
    form: any = {};
    technicalReference: TechnicalReference | null = null;
    referencePhotoFilename: string | null = null;
    loadingTechnicalReference = false;
    technicalReferenceError = '';
    private technicalReferenceLookup = 0;
    preventiveOptions = PREVENTIVE_FREQUENCIES;
    preventiveSelection: Record<string, boolean> = {};
    preventiveDates: Record<string, string> = {};
    referenceFrequencies: string[] = [];

    updateTechnicalReference() {
        if (this.currentEditId || this.saving) return;
        const lookup = ++this.technicalReferenceLookup;
        if (this.technicalReference) this.preventiveDates = {};
        this.technicalReference = null;
        this.referenceFrequencies = [];
        this.referencePhotoFilename = null;
        this.technicalReferenceError = '';
        const name = this.form.name?.trim();
        this.loadingTechnicalReference = !!name;
        if (!this.loadingTechnicalReference) return;

        this.httpValue.get<{ fields: TechnicalReference | null; frequencies: string[]; photoFilename: string | null }>('/api/equipment-reference', {
            params: { name, equipmentTypeId: this.form.equipmentTypeId ?? '' },
        }).subscribe({
            next: response => {
                if (lookup !== this.technicalReferenceLookup) return;
                this.technicalReference = response.fields;
                this.referenceFrequencies = response.frequencies;
                this.referencePhotoFilename = response.photoFilename;
                this.loadingTechnicalReference = false;
                this.cdr.markForCheck();
            },
            error: () => {
                if (lookup !== this.technicalReferenceLookup) return;
                this.technicalReferenceError = 'Não foi possível exibir a referência. Ao salvar, o sistema consulta o primeiro cadastro.';
                this.loadingTechnicalReference = false;
                this.cdr.markForCheck();
            },
        });
    }

    technicalValue(key: string) {
        return (this.technicalReference ? this.technicalReference[key] : this.form[key]) ?? '';
    }

    preventiveSelected(frequency: string): boolean {
        return this.technicalReference ? this.referenceFrequencies.includes(frequency) : !!this.preventiveSelection[frequency];
    }

    camposTexto = [
        {
            key: 'modelNumber', label: 'Nº MODEL'
        }, {
            key: 'model', label: 'MODEL'
        },
        {
            key: 'serial', label: 'SERIAL'
        }, {
            key: 'manufacturer', label: 'FABRICANTE'
        },
        {
            key: 'assetNumber', label: 'Nº ATIVO'
        }
    ];
    technicalFields = [
        {
            key: 'lengthMm', label: 'Comprimento (mm)'
        }, {
            key: 'widthMm', label: 'Largura (mm)'
        },
        {
            key: 'heightMm', label: 'Altura (mm)'
        }, {
            key: 'weightKg', label: 'Peso (kg)'
        },
        {
            key: 'voltageV', label: 'Tensão (V)', example: 'Ex.: 220 ou 220 - 230 Trifásico'
        },
        {
            key: 'currentA', label: 'Corrente (A)'
        }, {
            key: 'powerW', label: 'Potência (W)'
        }
    ];
    /** Carrega tipos e setores, lê o setor da rota e busca seu repositório de equipamentos. */
    ngOnInit() {
        this.api.typesValue().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: typesValue => {
                this.typesValue = typesValue;
            },
            error: () => {
                this.errorValue = 'Erro ao carregar tipos de equipamentos.';
            }
        });
        this.routeValue.paramMap.pipe(finalize(() => this.cdr.markForCheck())).subscribe(paramsValue => {
            const id = Number(paramsValue.get('id') ??
                this.routeValue.snapshot.queryParamMap.get('sectorId'));
            this.sectorIdValue = Number.isInteger(id) && id > 0 ? id : null;
            this.cancelEdit();
            this.loadData();
        });
        this.api.sectors().pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: sectors => {
                this.sectors = sectors;
                if (this.sectorIdValue !== null &&
                    !sectors.some(s => Number(s.id) === this.sectorIdValue)) {
                    this.errorValue = 'O setor selecionado não foi encontrado.';
                }
            },
            error: () => {
                this.errorValue = 'Não foi possível carregar os setores.';
            }
        });
    }
    /** GET /api/equipment?sectorId=...: recarrega as máquinas do setor após cadastro, edição ou desativação. */
    loadData() {
        if (!this.sectorIdValue) {
            this.machinesValue = [];
            return;
        }
        this.httpValue.get<EquipmentData[]>('/api/equipment?sectorId=' + this.sectorIdValue).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: x => this.machinesValue = x, error: () => this.errorValue = 'Falha ao carregar repositório'
        });
    }
    /** Recebe o arquivo escolhido e confere tipo e tamanho no navegador; o servidor repetirá as verificações. */
    selectFile(event: Event, kindValue: AttachmentKind) {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0] || null;
        // Uma seleção inválida não pode deixar um arquivo anterior pendente de envio.
        if (kindValue === 'PHOTO') {
            this.chosenPhoto = null;
            this.photoError = '';
        }
        else if (kindValue === 'MANUAL') this.chosenManual = null;
        else this.chosenElectrical = null;
        if (file) {
            const allowed = kindValue === 'PHOTO' ? ['image/jpeg', 'image/png'] : ['application/pdf'];
            const limit = (kindValue === 'PHOTO' ? 3 : 25) * 1024 * 1024;
            if (!allowed.includes(file.type) || file.size > limit) {
                if (kindValue === 'PHOTO') this.photoError = 'Escolha uma foto JPG ou PNG de até 3 MB.';
                else this.errorValue = 'O documento precisa ser PDF de até 25 MB';
                input.value = '';
                return;
            }
        }
        this.errorValue = '';
        if (kindValue === 'PHOTO')
            this.chosenPhoto = file;
        else if (kindValue === 'MANUAL')
            this.chosenManual = file;
        else
            this.chosenElectrical = file;
    }
    /** Envia o arquivo diretamente para evitar a expansão causada pela codificação em base64. */
    async uploadFile(id: number, kindValue: AttachmentKind, file: File): Promise<void> {
        const body = new FormData();
        body.append('file', file);
        await firstValueFrom(this.httpValue.post(`/api/equipment/${id}/attachments/${kindValue}`, body));
    }
    // Normaliza números e data parcial; a API repete a validação antes de persistir.
    /** Converte os campos numéricos e valida o formato da data parcial antes de montar o JSON de envio. */
    normalizedData() {
        const payload: any = {
            ...this.form,
            ...this.technicalReference,
        };
        payload.preventiveSchedules = this.preventiveOptions.filter(option => this.preventiveSelected(option.value))
            .map(option => ({frequency: option.value, nextDue: this.preventiveDates[option.value] || null}));
        for (const f of this.technicalFields) {
            const raw = payload[f.key];
            if (f.example) {
                payload[f.key] = String(raw ?? '').trim() || null;
                continue;
            }
            if (raw === undefined || raw === null || String(raw).trim() === '') {
                payload[f.key] = null;
                continue;
            }
            const cleaned = String(raw).trim().replace(',', '.');
            if (!/^\d+(?:\.\d+)?$/.test(cleaned))
                throw new Error('Número inválido em ' + f.label);
            payload[f.key] = Number(cleaned);
        }
        payload.frequencyHz = String(payload.frequencyHz ?? '').trim() || null;
        payload.pneumaticPressureBar = String(payload.pneumaticPressureBar ?? '').trim() || null;
        payload.manufacturingDateText = String(payload.manufacturingDateText || '').trim();
        return payload;
    }
    // O cadastro é salvo antes dos anexos; uma falha de upload não desfaz a máquina já criada.
    /** Usa POST para criar ou PATCH para editar a máquina; depois envia foto e manual. Falha no anexo não desfaz o cadastro já salvo. */
    async save() {
        if (!this.sectorIdValue || !this.form.equipmentTypeId || this.saving || this.loadingTechnicalReference)
            return;
        this.errorValue = '';
        this.success = '';
        this.saving = true;
        let id: number | null = null;
        let masterSaved = false;
        const creating = this.currentEditId === null;
        const photoValue = this.chosenPhoto, manual = this.chosenManual, electrical = this.chosenElectrical;
        try {
            const payload = this.normalizedData();
            if (this.currentEditId) {
                id = this.currentEditId;
                await firstValueFrom(this.httpValue.patch(`/api/equipment/${id}`, payload, {
                    context: new HttpContext().set(SUPPRESS_EDIT_DIALOG, true),
                }));
            }
            else {
                const saved = await firstValueFrom(this.httpValue.post<EquipmentData>('/api/equipment', {
                    ...payload,
                    sectorId: this.sectorIdValue,
                    useReferencePhoto: !photoValue,
                }));
                id = saved.id;
                Object.assign(this.form, this.technicalFormValues(saved));
                this.fillPreventiveForm(saved);
            }
            masterSaved = true;
            this.technicalReference = null;
            // Em caso de falha de anexo, repetir o envio edita a mesma máquina, sem duplicar o cadastro.
            this.currentEditId = id;
            if (photoValue)
                await this.uploadFile(id, 'PHOTO', photoValue);
            if (manual)
                await this.uploadFile(id, 'MANUAL', manual);
            if (electrical)
                await this.uploadFile(id, 'ELECTRICAL', electrical);
            this.selectedEquipment = 0;
            this.cancelEdit();
            if (creating) this.registrationFeedback.created('Equipamento cadastrado com sucesso', payload.name);
            else this.registrationFeedback.show('Equipamento atualizado com sucesso', payload.name, 'OK');
            this.loadData();
        }
        catch (e: any) {
            this.errorValue = (masterSaved ? 'Equipamento salvo, mas houve falha em algum anexo. Edite o cadastro para reenviar. ' : '') +
                (e?.error?.error || e?.message || 'Não foi possível salvar equipamento.');
            this.loadData();
        }
        finally {
            this.saving = false;
            this.cdr.markForCheck();
        }
    }
    /** Copia a máquina retornada pela API para o formulário, convertendo nomes snake_case em campos camelCase. */
    edit(e: EquipmentData) {
        if (!this.isAdmin())
            return;
        const row = e as any;
        this.currentEditId = e.id;
        this.form = {
            name: row.name || '',
            equipmentTypeId: row.equipment_type_id,
            serial: row.serial || '', assetNumber: row.asset_number || '',
            manufacturingDateText: row.manufacturing_date_text || (row.manufacturing_date ? String(row.manufacturing_date).slice(0, 10).split('-').reverse().join('/') : ''),
            ...this.technicalFormValues(e),
        };
        this.fillPreventiveForm(e);
        this.chosenPhoto = null;
        this.chosenManual = null;
        this.chosenElectrical = null;
        this.errorValue = '';
        this.success = '';
        this.showForm = true;
        this.loadEditAttachments(e.id);
    }
    private technicalFormValues(equipment: EquipmentData) {
        return {
            modelNumber: equipment.model_number ?? '',
            model: equipment.model ?? '',
            manufacturer: equipment.manufacturer ?? '',
            lengthMm: equipment.length_mm ?? '',
            widthMm: equipment.width_mm ?? '',
            heightMm: equipment.height_mm ?? '',
            weightKg: equipment.weight_kg ?? '',
            voltageV: equipment.voltage_v ?? '',
            currentA: equipment.current_a ?? '',
            powerW: equipment.power_w ?? '',
            frequencyHz: equipment.frequency_hz ?? '',
            pneumaticPressureBar: equipment.pneumatic_pressure_bar ?? '',
            description: equipment.description ?? '',
            processDescription: equipment.process_description ?? '',
        };
    }

    private fillPreventiveForm(equipment: EquipmentData) {
        this.preventiveSelection = {};
        this.preventiveDates = {};
        for (const schedule of equipment.preventive_schedules || []) {
            this.preventiveSelection[schedule.frequency] = true;
            this.preventiveDates[schedule.frequency] = schedule.next_due;
        }
    }

    /** Fecha o modal e descarta somente os valores locais e os arquivos ainda não enviados. */
    cancelEdit() {
        ++this.editAttachmentLookup;
        this.editAttachments = [];
        this.loadingEditAttachments = false;
        this.editAttachmentsError = '';
        this.showForm = false;
        this.currentEditId = null;
        this.form = {};
        ++this.technicalReferenceLookup;
        this.technicalReference = null;
        this.referencePhotoFilename = null;
        this.loadingTechnicalReference = false;
        this.technicalReferenceError = '';
        this.referenceFrequencies = [];
        this.preventiveSelection = {};
        this.preventiveDates = {};
        this.chosenPhoto = null;
        this.chosenManual = null;
        this.chosenElectrical = null;
        this.photoError = '';
        this.errorValue = '';
    }
    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE /api/equipment/:id solicita desativação lógica; a API verifica perfil e vínculos antes de preservar o histórico. */
    async deactivate(e: EquipmentData) {
        if (!this.isAdmin() || e.line_id)
            return;
        if (!window.confirm('Desativar este equipamento? O histórico será preservado.'))
            return;
        try {
            await firstValueFrom(this.httpValue.delete(`/api/equipment/${e.id}`));
            this.success = 'Equipamento desativado.';
            this.errorValue = '';
            this.loadData();
        }
        catch (err: any) {
            this.errorValue = err?.error?.error || 'Não foi possível excluir o equipamento.';
        }
        finally {
            this.cdr.markForCheck();
        }
    }
    showDocuments(id: number) {
        this.selectedEquipment = this.selectedEquipment === id ? 0 : id;
    }
}
