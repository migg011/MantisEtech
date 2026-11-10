/** Módulo equipamentos: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { FormModal } from '../../shared/form-modal.component';
import { finalize } from 'rxjs';
import {
    Component,
    inject,
    OnInit,
    signal,
    ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
    Router,
    RouterLink,
    RouterOutlet,
    ActivatedRoute,
} from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import {
    MatDialog,
    MatDialogModule,
    MatDialogRef,
    MAT_DIALOG_DATA,
} from '@angular/material/dialog';
import { MatCardModule } from '@angular/material/card';
import {
    Authentication,
    Api,
    Line,
    Equipment as EquipmentData,
} from '../../services';
import { PREVENTIVE_PERIODICITIES } from '../../core/models/preventive.model';
const UI_MODULES = [
    FormModal,
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatSelectModule,
    MatToolbarModule,
    MatDialogModule,
    MatCardModule,
    RouterLink,
];
@Component({
    standalone: true,
    imports: UI_MODULES,
    templateUrl: './equipment.component.html',
    styleUrl: './equipment.component.scss',
})
/** Controla cadastro técnico e anexos; o Django valida dados, permissões e conteúdo dos arquivos. */
export class EquipmentRegistration implements OnInit {
    // markForCheck informa ao Angular que respostas assíncronas alteraram campos exibidos.
    private changeDetector = inject(ChangeDetectorRef);
    api = inject(Api);
    authentication = inject(Authentication);
    route = inject(ActivatedRoute);
    httpClient = inject(HttpClient);
    idSector: number | null = null;
    sectors: {
        id: number;
        name: string;
    }[] = [];
    /** Resolve o nome do setor selecionado a partir da lista carregada da API. */
    nameSector(): string {
        if (this.idSector === null) {
            return 'Nenhum setor selecionado';
        }
        const sector = this.sectors.find(
            (s) => Number(s.id) === Number(this.idSector)
        );
        return sector?.name || 'Setor não encontrado';
    }
    /** Controla a exibição das ações administrativas de máquinas pelo perfil local. */
    administrator() {
        return this.authentication.user()?.role === 'ADMINISTRADOR';
    }
    types: {
        id: number;
        name: string;
    }[] = [];
    equipment: EquipmentData[] = [];
    machineTransfer: EquipmentData | null = null;
    sectorDestination: number | null = null;
    reasonTransfer = '';
    transferring = false;
    errorTransfer = '';
    messageTransfer = '';
    machineHistory: EquipmentData | null = null;
    history: {
        action: string;
        from_sector_name: string | null;
        to_sector_name: string | null;
        from_line: string | null;
        to_line: string | null;
        performed_by_name: string;
        created_at: string;
        reason: string;
    }[] = [];
    loadingHistory = false;
    errorHistory = '';
    private queryHistory = 0;
    get sectorsDestination() {
        return this.sectors.filter((sector) => sector.id !== this.idSector);
    }
    openTransfer(machine: EquipmentData) {
        if (!this.administrator() || machine.line_id || this.transferring)
            return;
        this.machineTransfer = machine;
        this.sectorDestination = null;
        this.reasonTransfer = this.errorTransfer = this.messageTransfer = '';
    }
    closeTransfer() {
        if (!this.transferring) this.machineTransfer = null;
    }
    /** A API trava a máquina e confere o setor de origem novamente antes de gravar. */
    async transfer() {
        if (
            !this.machineTransfer ||
            !this.idSector ||
            !this.sectorDestination ||
            this.transferring ||
            this.reasonTransfer.trim().length < 3
        )
            return;
        this.transferring = true;
        this.errorTransfer = '';
        const machine = this.machineTransfer;
        const destination =
            this.sectors.find((sector) => sector.id === this.sectorDestination)
                ?.name || '';
        try {
            await firstValueFrom(
                this.httpClient.post(`/api/equipment/${machine.id}/transfer`, {
                    originSectorId: this.idSector,
                    destinationSectorId: this.sectorDestination,
                    reason: this.reasonTransfer.trim(),
                })
            );
            this.machineTransfer = null;
            this.messageTransfer = `${machine.name || machine.model || machine.type_name} transferido para ${destination}. Cadastro, anexos e histórico preservados.`;
            this.files = [];
            this.equipmentSelected = 0;
            this.loadData();
        } catch (error: any) {
            this.errorTransfer =
                error.error?.error ||
                'Não foi possível transferir o equipamento.';
        } finally {
            this.transferring = false;
            this.changeDetector.markForCheck();
        }
    }
    /** Histórico pertence ao equipamento, mesmo depois de mudar de repositório. */
    openHistory(machine: EquipmentData) {
        const query = ++this.queryHistory;
        this.machineHistory = machine;
        this.history = [];
        this.errorHistory = '';
        this.loadingHistory = true;
        this.httpClient
            .get<typeof this.history>(`/api/equipment/${machine.id}/movements`)
            .subscribe({
                next: (items) => {
                    if (query !== this.queryHistory) return;
                    this.history = items;
                    this.loadingHistory = false;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    if (query !== this.queryHistory) return;
                    this.errorHistory =
                        'Não foi possível consultar o histórico.';
                    this.loadingHistory = false;
                    this.changeDetector.markForCheck();
                },
            });
    }
    closeHistory() {
        ++this.queryHistory;
        this.machineHistory = null;
    }
    labelMovement(action: string) {
        return (
            (
                {
                    TRANSFERENCIA: 'Transferência entre setores',
                    ALOCACAO: 'Alocação na linha',
                    REMOCAO: 'Retirada da linha',
                    DESMONTAGEM: 'Desmontagem da linha',
                } as Record<string, string>
            )[action] || action
        );
    }
    files: {
        kind: 'PHOTO' | 'MANUAL';
        filename: string;
    }[] = [];
    equipmentSelected = 0;
    messageAttachments = '';
    error = '';
    successMessage = '';
    saving = false;
    formOpen = false;
    /** Limpa os dados anteriores e abre o modal para uma máquina nova. */
    newEquipment() {
        this.cancelEditing();
        this.successMessage = '';
        this.formOpen = true;
    }
    editingId: number | null = null;
    photoSelected: File | null = null;
    manualSelected: File | null = null;
    attachmentsEditing: { kind: 'PHOTO' | 'MANUAL'; filename: string }[] = [];
    loadingAttachmentsEditing = false;
    errorAttachmentsEditing = '';
    private queryAttachmentsEditing = 0;
    nameAttachmentSaved(category: 'PHOTO' | 'MANUAL') {
        return this.attachmentsEditing.find(
            (attachment) => attachment.kind === category
        )?.filename;
    }
    /** Consulta os arquivos persistidos separadamente do seletor de novos arquivos do navegador. */
    private loadAttachmentsEditing(id: number) {
        const query = ++this.queryAttachmentsEditing;
        this.attachmentsEditing = [];
        this.errorAttachmentsEditing = '';
        this.loadingAttachmentsEditing = true;
        this.httpClient
            .get<
                { kind: 'PHOTO' | 'MANUAL'; filename: string }[]
            >(`/api/equipment/${id}/attachments`)
            .subscribe({
                next: (attachments) => {
                    if (
                        query !== this.queryAttachmentsEditing ||
                        this.editingId !== id
                    )
                        return;
                    this.attachmentsEditing = attachments;
                    this.loadingAttachmentsEditing = false;
                    this.changeDetector.markForCheck();
                },
                error: () => {
                    if (
                        query !== this.queryAttachmentsEditing ||
                        this.editingId !== id
                    )
                        return;
                    this.errorAttachmentsEditing =
                        'Não foi possível consultar os arquivos já salvos. Eles não serão removidos ao salvar o cadastro.';
                    this.loadingAttachmentsEditing = false;
                    this.changeDetector.markForCheck();
                },
            });
    }
    form: any = {};
    optionsPreventive = PREVENTIVE_PERIODICITIES;
    selectionPreventive: Record<string, boolean> = {};
    datesPreventive: Record<string, string> = {};
    fieldsText = [
        {
            key: 'modelNumber',
            label: 'Nº MODEL',
        },
        {
            key: 'model',
            label: 'MODEL',
        },
        {
            key: 'serial',
            label: 'SERIAL',
        },
        {
            key: 'manufacturer',
            label: 'FABRICANTE',
        },
        {
            key: 'assetNumber',
            label: 'Nº ATIVO',
        },
    ];
    fieldsNumeric = [
        {
            key: 'lengthMm',
            label: 'Comprimento (mm)',
        },
        {
            key: 'widthMm',
            label: 'Largura (mm)',
        },
        {
            key: 'heightMm',
            label: 'Altura (mm)',
        },
        {
            key: 'weightKg',
            label: 'Peso (kg)',
        },
        {
            key: 'voltageV',
            label: 'Tensão (V)',
        },
        {
            key: 'frequencyHz',
            label: 'Frequência (Hz)',
        },
        {
            key: 'currentA',
            label: 'Corrente (A)',
        },
        {
            key: 'powerW',
            label: 'Potência (W)',
        },
        {
            key: 'pneumaticPressureBar',
            label: 'Pressão pneumática (bar)',
        },
    ];
    /** Carrega tipos e setores, lê o setor da rota e busca seu repositório de equipamentos. */
    ngOnInit() {
        this.api
            .types()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (types) => {
                    this.types = types;
                },
                error: () => {
                    this.error = 'Erro ao carregar tipos de equipamentos.';
                },
            });
        this.route.paramMap
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe((parameters) => {
                const id = Number(
                    parameters.get('id') ??
                        this.route.snapshot.queryParamMap.get('sectorId')
                );
                this.idSector = Number.isInteger(id) && id > 0 ? id : null;
                this.cancelEditing();
                this.loadData();
            });
        this.api
            .sectors()
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (sectors) => {
                    this.sectors = sectors;
                    if (
                        this.idSector !== null &&
                        !sectors.some((s) => Number(s.id) === this.idSector)
                    ) {
                        this.error = 'O setor selecionado não foi encontrado.';
                    }
                },
                error: () => {
                    this.error = 'Não foi possível carregar os setores.';
                },
            });
    }
    /** GET /api/equipment?sectorId=...: recarrega as máquinas do setor após cadastro, edição ou desativação. */
    loadData() {
        if (!this.idSector) {
            this.equipment = [];
            return;
        }
        this.httpClient
            .get<EquipmentData[]>('/api/equipment?sectorId=' + this.idSector)
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => (this.equipment = x),
                error: () => (this.error = 'Falha ao carregar repositório'),
            });
    }
    /** Recebe o arquivo escolhido e confere tipo e tamanho no navegador; o servidor repetirá as verificações. */
    selectFile(event: Event, category: 'PHOTO' | 'MANUAL') {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0] || null;
        // Uma seleção inválida não pode deixar um arquivo anterior pendente de envio.
        if (category === 'PHOTO') this.photoSelected = null;
        else this.manualSelected = null;
        if (file) {
            const allowed =
                category === 'PHOTO'
                    ? ['image/jpeg', 'image/png']
                    : ['application/pdf'];
            const limit =
                category === 'PHOTO' ? 3 * 1024 * 1024 : 5 * 1024 * 1024;
            if (!allowed.includes(file.type) || file.size > limit) {
                this.error =
                    category === 'PHOTO'
                        ? 'Foto precisa ser JPG/PNG de até 3 MB'
                        : 'Manual precisa ser PDF de até 5 MB';
                input.value = '';
                return;
            }
        }
        this.error = '';
        if (category === 'PHOTO') this.photoSelected = file;
        else this.manualSelected = file;
    }
    // Converte para base64; o Django confere tamanho, assinatura e tipo antes de armazenar.
    /** Lê o arquivo como base64 e faz PUT no endpoint de anexos da máquina. A máquina já deve ter ID no banco. */
    async sendFile(
        id: number,
        category: 'PHOTO' | 'MANUAL',
        file: File
    ): Promise<void> {
        const base64 = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(',')[1]);
            reader.onerror = () =>
                reject(new Error('Falha ao ler arquivo: ' + file.name));
            reader.readAsDataURL(file);
        });
        await firstValueFrom(
            this.httpClient.put(
                `/api/equipment/${id}/attachments/${category}`,
                {
                    filename: file.name,
                    mimeType: file.type,
                    base64,
                }
            )
        );
    }
    // Normaliza números e data parcial; a API repete a validação antes de persistir.
    /** Converte os campos numéricos e valida o formato da data parcial antes de montar o JSON de envio. */
    dataNormalized() {
        const dataSubmission: any = {
            ...this.form,
        };
        dataSubmission.preventiveSchedules = this.optionsPreventive
            .filter((option) => this.selectionPreventive[option.value])
            .map((option) => ({
                frequency: option.value,
                nextDue: this.datesPreventive[option.value] || null,
            }));
        for (const f of this.fieldsNumeric) {
            const raw = dataSubmission[f.key];
            if (
                raw === undefined ||
                raw === null ||
                String(raw).trim() === ''
            ) {
                dataSubmission[f.key] = null;
                continue;
            }
            const cleaned = String(raw).trim().replace(',', '.');
            if (!/^\d+(?:\.\d+)?$/.test(cleaned))
                throw new Error('Número inválido em ' + f.label);
            dataSubmission[f.key] = Number(cleaned);
        }
        dataSubmission.manufacturingDateText = String(
            dataSubmission.manufacturingDateText || ''
        ).trim();
        if (
            dataSubmission.manufacturingDateText &&
            !/^(?:\d{4}|(?:0?[1-9]|1[0-2])\/\d{4}|(?:0?[1-9]|[12]\d|3[01])\/(?:0?[1-9]|1[0-2])\/\d{4})$/.test(
                dataSubmission.manufacturingDateText
            )
        ) {
            throw new Error(
                'Data de fabricação: informe ano, mês/ano ou dia/mês/ano.'
            );
        }
        return dataSubmission;
    }
    // O cadastro é salvo antes dos anexos; uma falha de upload não desfaz a máquina já criada.
    /** Usa POST para criar ou PATCH para editar a máquina; depois envia foto e manual. Falha no anexo não desfaz o cadastro já salvo. */
    async save() {
        if (!this.idSector || !this.form.equipmentTypeId || this.saving) return;
        this.error = '';
        this.successMessage = '';
        this.saving = true;
        let id: number | null = null;
        let masterSaved = false;
        const photo = this.photoSelected,
            manual = this.manualSelected;
        try {
            const dataSubmission = this.dataNormalized();
            if (this.editingId) {
                id = this.editingId;
                await firstValueFrom(
                    this.httpClient.patch(
                        `/api/equipment/${id}`,
                        dataSubmission
                    )
                );
            } else {
                const saved = await firstValueFrom(
                    this.httpClient.post<{
                        id: number;
                    }>('/api/equipment', {
                        ...dataSubmission,
                        sectorId: this.idSector,
                    })
                );
                id = saved.id;
            }
            masterSaved = true;
            // Em caso de falha de anexo, repetir o envio edita a mesma máquina, sem duplicar o cadastro.
            this.editingId = id;
            if (photo) await this.sendFile(id, 'PHOTO', photo);
            if (manual) await this.sendFile(id, 'MANUAL', manual);
            this.cancelEditing();
            this.successMessage = 'Equipamento e arquivos selecionados salvos.';
            this.loadData();
        } catch (e: any) {
            this.error =
                (masterSaved
                    ? 'Equipamento salvo, mas houve falha em algum anexo. Edite o cadastro para reenviar. '
                    : '') +
                (e?.error?.error ||
                    e?.message ||
                    'Não foi possível salvar equipamento.');
            this.loadData();
        } finally {
            this.saving = false;
            this.changeDetector.markForCheck();
        }
    }
    /** Copia a máquina retornada pela API para o formulário, convertendo nomes snake_case em campos camelCase. */
    edit(e: EquipmentData) {
        if (!this.administrator()) return;
        const row = e as any;
        this.editingId = e.id;
        this.form = {
            name: row.name || '',
            equipmentTypeId: row.equipment_type_id,
            modelNumber: row.model_number || '',
            model: row.model || '',
            serial: row.serial || '',
            manufacturer: row.manufacturer || '',
            assetNumber: row.asset_number || '',
            manufacturingDateText:
                row.manufacturing_date_text ||
                (row.manufacturing_date
                    ? String(row.manufacturing_date)
                          .slice(0, 10)
                          .split('-')
                          .reverse()
                          .join('/')
                    : ''),
            description: row.description || '',
            processDescription: row.process_description || '',
        };
        this.selectionPreventive = {};
        this.datesPreventive = {};
        for (const schedule of e.preventive_schedules || []) {
            this.selectionPreventive[schedule.frequency] = true;
            this.datesPreventive[schedule.frequency] = schedule.next_due;
        }
        const map: any = {
            lengthMm: 'length_mm',
            widthMm: 'width_mm',
            heightMm: 'height_mm',
            weightKg: 'weight_kg',
            voltageV: 'voltage_v',
            frequencyHz: 'frequency_hz',
            currentA: 'current_a',
            powerW: 'power_w',
            pneumaticPressureBar: 'pneumatic_pressure_bar',
        };
        for (const f of this.fieldsNumeric)
            this.form[f.key] = row[map[f.key]] ?? '';
        this.photoSelected = null;
        this.manualSelected = null;
        this.error = '';
        this.successMessage = '';
        this.formOpen = true;
        this.loadAttachmentsEditing(e.id);
    }
    /** Fecha o modal e descarta somente os valores locais e os arquivos ainda não enviados. */
    cancelEditing() {
        ++this.queryAttachmentsEditing;
        this.attachmentsEditing = [];
        this.loadingAttachmentsEditing = false;
        this.errorAttachmentsEditing = '';
        this.formOpen = false;
        this.editingId = null;
        this.form = {};
        this.selectionPreventive = {};
        this.datesPreventive = {};
        this.photoSelected = null;
        this.manualSelected = null;
        this.error = '';
    }
    // Solicita desativação lógica; o servidor preserva históricos e bloqueia vínculos que impedem a operação.
    /** DELETE /api/equipment/:id solicita desativação lógica; a API verifica perfil e vínculos antes de preservar o histórico. */
    async deactivate(e: EquipmentData) {
        if (!this.administrator() || e.line_id) return;
        if (
            !window.confirm(
                'Desativar este equipamento? O histórico será preservado.'
            )
        )
            return;
        try {
            await firstValueFrom(
                this.httpClient.delete(`/api/equipment/${e.id}`)
            );
            this.successMessage = 'Equipamento desativado.';
            this.error = '';
            this.loadData();
        } catch (err: any) {
            this.error =
                err?.error?.error || 'Não foi possível excluir o equipamento.';
        } finally {
            this.changeDetector.markForCheck();
        }
    }
    // Busca metadados sem baixar todo o conteúdo binário dos arquivos.
    /** GET dos anexos consulta apenas nomes e categorias; o conteúdo binário é baixado separadamente. */
    attachments(id: number) {
        this.equipmentSelected = id;
        this.files = [];
        this.messageAttachments = '';
        this.httpClient
            .get<
                {
                    kind: 'PHOTO' | 'MANUAL';
                    filename: string;
                }[]
            >(`/api/equipment/${id}/attachments`)
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (x) => {
                    this.files = x;
                    if (!x.length)
                        this.messageAttachments =
                            'Este equipamento ainda não tem anexos.';
                },
                error: () =>
                    (this.messageAttachments = 'Falha ao listar anexos'),
            });
    }
    /** Busca o anexo como Blob autenticado, cria um link temporário para download e libera sua URL depois. */
    download(id: number, category: 'PHOTO' | 'MANUAL', nameFile: string) {
        this.httpClient
            .get(`/api/equipment/${id}/attachments/${category}/download`, {
                responseType: 'blob',
            })
            .pipe(finalize(() => this.changeDetector.markForCheck()))
            .subscribe({
                next: (contentFile) => {
                    const address = URL.createObjectURL(contentFile);
                    const a = document.createElement('a');
                    a.href = address;
                    a.download = nameFile;
                    a.click();
                    setTimeout(() => URL.revokeObjectURL(address), 1000);
                },
                error: () => (this.messageAttachments = 'Erro ao baixar anexo'),
            });
    }
}
