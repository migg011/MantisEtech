/** Módulo login: os campos da classe alimentam o template; ações do usuário chamam os métodos documentados abaixo. */
import { finalize } from 'rxjs';
import { Component, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { Auth } from '../../services';
@Component({
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatInputModule,
        MatIconModule
    ],
    templateUrl: './login.component.html',
    styleUrl: './login.component.scss'
})
/** Controla o formulário de entrada; envia matrícula e senha ao Django e redireciona conforme o perfil. */
export class Login {
    // markForCheck avisa ao Angular que respostas assíncronas alteraram os campos exibidos.
    private cdr = inject(ChangeDetectorRef);
    authValue = inject(Auth);
    router = inject(Router);
    registrationValue = '';
    passwordValue = '';
    showPassword = false;
    errorValue = '';
    loading = false;
    // Aguarda a autenticação da API e apresenta a mensagem do servidor quando as credenciais são recusadas.
    /** Envia matrícula e senha por entrar(); o Django valida a conta antes da navegação. */
    signIn() {
        this.errorValue = '';
        this.loading = true;
        this.authValue.signIn(this.registrationValue, this.passwordValue).pipe(finalize(() => this.cdr.markForCheck())).subscribe({
            next: response => this.router.navigateByUrl(response.user.role === 'OPERADOR' ? '/totem' : '/dashboard'),
            error: failure => {
                this.errorValue = failure.error?.error || 'Não foi possível entrar';
                this.loading = false;
            }
        });
    }
}
