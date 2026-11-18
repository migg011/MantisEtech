/** Moldura da aplicação: menu, usuário conectado e router-outlet. O modo exposição usa uma rota externa a esta moldura. */
import { Component, inject, OnInit, signal, ChangeDetectorRef, TemplateRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
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
import { SessionIdle } from '../../core/services/session-idle.service';
const UI = [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatIconModule, MatSelectModule, MatToolbarModule, MatDialogModule, MatCardModule, RouterLink];
@Component({
    standalone: true,
    imports: [...UI, RouterOutlet, RouterLinkActive],
    templateUrl: './shell.component.html',
    styleUrl: './shell.component.scss'
})
/** Estrutura compartilhada de navegação; exibe o usuário autenticado e as telas carregadas pelo roteador. */
export class Shell {
    authValue = inject(Auth);
    private idle = inject(SessionIdle);
    private dialogs = inject(MatDialog);
    idleMinutes: number | null = 0;
    settingsError = '';

    openSettings(template: TemplateRef<unknown>) {
        this.idleMinutes = this.idle.minutes();
        this.settingsError = '';
        this.dialogs.open(template, { width: '460px' });
    }

    saveSettings(dialog: MatDialogRef<unknown>) {
        if (this.idleMinutes === null || !Number.isInteger(this.idleMinutes) || this.idleMinutes < 0 || this.idleMinutes > 480) {
            this.settingsError = 'Informe um número inteiro de 0 a 480 minutos.';
            return;
        }
        if (!this.idle.save(this.idleMinutes)) {
            this.settingsError = 'Não foi possível salvar a configuração neste navegador.';
            return;
        }
        dialog.close();
    }
}
