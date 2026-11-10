/** Tab session service: integrates HTTP login, Bearer token, reactive user, and logout navigation. */
import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { User } from '../models/user.model';
@Injectable({
    providedIn: 'root',
})
/** Keeps the interface user and the token issued by Django during this tab session. */
export class Authentication {
    private httpClient = inject(HttpClient);
    private router = inject(Router);
    user = signal<User | null>(this.restoreSession());
    /** Reads the user saved in the tab to rebuild the menu after a reload. It does not validate the token on the server. */
    private restoreSession(): User | null {
        // Restores navigation after reloading the page. The API still validates token and account on every call.
        try {
            return JSON.parse(sessionStorage.getItem('mantisUser') || 'null');
        } catch {
            return null;
        }
    }
    /** POST /api/auth/login: sends registration and password; on success, stores token and user and updates the session signal. */
    login(registration: string, password: string) {
        // The token is treated as an opaque credential: Angular does not verify signatures or decide API permissions.
        return this.httpClient
            .post<{
                token: string;
                user: User;
            }>('/api/auth/login', {
                // The English keys are the existing HTTP contract, not the database names.
                registration: registration,
                password: password,
            })
            .pipe(
                tap((response) => {
                    // Updates tab storage and the signal used by the menu and route protections.
                    sessionStorage.setItem('mantisToken', response.token);
                    sessionStorage.setItem(
                        'mantisUser',
                        JSON.stringify(response.user)
                    );
                    this.user.set(response.user);
                })
            );
    }
    /** Clears the credentials of this tab and navigates to login. It does not revoke an external copy of the token on the server. */
    logout() {
        // Ends the local session. The validity of a token copy remains limited by Django rules.
        sessionStorage.removeItem('mantisToken');
        sessionStorage.removeItem('mantisUser');
        this.user.set(null);
        this.router.navigateByUrl('/login');
    }
}
