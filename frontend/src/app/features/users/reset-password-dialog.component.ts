/** Módulo reset-password-dialog: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
    MAT_DIALOG_DATA,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
@Component({
    selector: 'app-dialogo-redefinir-senha',
    standalone: true,
    imports: [
        FormsModule,
        MatDialogModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule,
        MatButtonModule,
    ],
    template: `
        <div class="mantis-modal"
            ><header class="mantis-modal-header"
                ><div class="mantis-modal-icon"
                    ><mat-icon>lock_reset</mat-icon></div
                ><div
                    ><h2 mat-dialog-title>Redefinir senha</h2
                    ><p>Atualize a senha de acesso do usuário.</p></div
                ><button
                    class="mantis-modal-close"
                    type="button"
                    aria-label="Fechar modal"
                    (click)="cancel()"
                    ><mat-icon>close</mat-icon></button
                ></header
            >

            <mat-dialog-content class="mantis-modal-body">
                <p>
                    Informe uma nova senha para
                    <strong>{{ data.name }}</strong
                    >.
                </p>

                <label class="modal-field"
                    ><span>Nova senha</span
                    ><div class="modal-password">
                        <input
                            [type]="showPassword ? 'text' : 'password'"
                            name="newPassword"
                            autocomplete="new-password"
                            [(ngModel)]="password"
                        />

                        <button
                            mat-icon-button
                            type="button"
                            [attr.aria-label]="
                                showPassword ? 'Ocultar senha' : 'Mostrar senha'
                            "
                            (click)="showPassword = !showPassword"
                        >
                            <mat-icon>
                                {{
                                    showPassword
                                        ? 'visibility_off'
                                        : 'visibility'
                                }}
                            </mat-icon>
                        </button>
                    </div></label
                >

                <label class="modal-field"
                    ><span>Confirmar nova senha</span
                    ><div class="modal-password">
                        <input
                            [type]="showConfirmation ? 'text' : 'password'"
                            name="confirmPassword"
                            autocomplete="new-password"
                            [(ngModel)]="confirmation"
                        />

                        <button
                            mat-icon-button
                            type="button"
                            [attr.aria-label]="
                                showConfirmation
                                    ? 'Ocultar confirmação'
                                    : 'Mostrar confirmação'
                            "
                            (click)="showConfirmation = !showConfirmation"
                        >
                            <mat-icon>
                                {{
                                    showConfirmation
                                        ? 'visibility_off'
                                        : 'visibility'
                                }}
                            </mat-icon>
                        </button>
                    </div></label
                >

                @if (password.length > 0 && password.length < 12) {
                    <p class="validation-error">
                        A senha deve conter no mínimo 12 caracteres.
                    </p>
                }

                @if (confirmation.length > 0 && password !== confirmation) {
                    <p class="validation-error"> As senhas não coincidem. </p>
                }

                @if (password.length >= 12 && password === confirmation) {
                    <p class="validation-success"> As senhas coincidem. </p>
                }
            </mat-dialog-content>

            <mat-dialog-actions align="end" class="mantis-modal-footer">
                <button mat-stroked-button type="button" (click)="cancel()">
                    Cancelar
                </button>

                <button
                    mat-flat-button
                    type="button"
                    class="primary"
                    [disabled]="
                        password.length < 12 || password !== confirmation
                    "
                    (click)="confirm()"
                >
                    <mat-icon>lock_reset</mat-icon>
                    Confirmar
                </button>
            </mat-dialog-actions></div
        >
    `,
    styles: [
        `
            :host {
                display: block;
            }

            .validation-error {
                color: #c62828;
                font-size: 13px;
                margin: 0 0 12px;
            }

            .validation-success {
                color: #2e7d32;
                font-size: 13px;
                margin: 0 0 12px;
            }

            .confirm-button {
                background: #c62828 !important;
                color: white !important;
                border-radius: 8px;
            }

            .confirm-button:disabled {
                background: #dddddd !important;
                color: #777777 !important;
            }
        `,
    ],
})
/** Coleta a nova senha para a tela de usuários; somente a API pode validar e gravar a alteração. */
export class ResetPasswordDialog {
    private dialogReference = inject(MatDialogRef<ResetPasswordDialog, string>);
    data = inject<{
        name: string;
    }>(MAT_DIALOG_DATA);
    password = '';
    confirmation = '';
    showPassword = false;
    showConfirmation = false;
    /** Fecha o diálogo sem devolver senha ou enviar requisição. */
    cancel(): void {
        this.dialogReference.close();
    }
    /** Confere tamanho e coincidência e devolve a senha à tela de usuários, que fará a chamada HTTP. */
    confirm(): void {
        if (this.password.length < 12 || this.password !== this.confirmation) {
            return;
        }
        this.dialogReference.close(this.password);
    }
}
