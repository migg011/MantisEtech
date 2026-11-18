/** Serviço de sessão da aba: integra login HTTP, token Bearer, usuário reativo e navegação de saída. */
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { User } from '../models/user.model';
@Injectable({
    providedIn: 'root'
})
/** Mantém o usuário da interface e o token emitido pelo Django durante esta sessão da aba. */
export class Auth {
    private httpValue = inject(HttpClient);
    private router = inject(Router);
    userValue = signal<User | null>(this.restoreSession());
    // Ponte temporária para módulos ainda não traduzidos; os dois nomes usam o mesmo signal.
    user = this.userValue;
    /** Lê o usuário salvo na aba para reconstruir o menu após recarregar. Não valida o token no servidor. */
    private restoreSession(): User | null {
        // Restaura a navegação após recarregar a página. A API ainda valida token e conta em cada chamada.
        try {
            return JSON.parse(sessionStorage.getItem('mantisUser') || 'null');
        }
        catch {
            return null;
        }
    }
    /** POST /api/auth/login: envia matrícula e senha; no sucesso, guarda token e usuário e atualiza o signal da sessão. */
    signIn(registrationValue: string, passwordValue: string) {
        // O token é tratado como uma credencial opaca: o Angular não verifica assinatura nem decide permissões da API.
        return this.httpValue.post<{
            token: string;
            user: User;
        }>('/api/auth/login', {
            // As chaves em inglês são o contrato HTTP existente, não os nomes do banco.
            registration: registrationValue,
            password: passwordValue
        }).pipe(tap(response => {
            // Atualiza o armazenamento da aba e o signal usado pelo menu e pelas proteções de rota.
            sessionStorage.setItem('mantisToken', response.token);
            sessionStorage.setItem('mantisUser', JSON.stringify(response.user));
            this.userValue.set(response.user);
        }));
    }
    /** Apaga as credenciais desta aba e navega ao login. Não revoga uma cópia externa do token no servidor. */
    signOut() {
        // Encerra a sessão local. A validade de uma cópia do token continua limitada pelas regras do Django.
        sessionStorage.removeItem('mantisToken');
        sessionStorage.removeItem('mantisUser');
        this.userValue.set(null);
        this.router.navigateByUrl('/login');
    }
    /** Compatibilidade: telas ainda não traduzidas continuam chamando login/logout. */
    login(registrationValue: string, passwordValue: string) { return this.signIn(registrationValue, passwordValue); }
    logout() { this.signOut(); }
}
