/** Integração transversal: adiciona Authorization Bearer às URLs /api/ e encaminha erros de sessão ao login. */
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { Authentication } from '../services/authentication.service';
/** Intercepta a chamada antes do envio, acrescenta Bearer somente à API local e trata 401 como fim da sessão. */
export const authenticationInterceptor: HttpInterceptorFn = (request, next) => {
    const authentication = inject(Authentication);
    const token = sessionStorage.getItem('mantisToken');
    const isApiRequest = request.url.startsWith('/api/');
    // Anexa a credencial somente às chamadas locais da API, preservando requisições a outros endereços.
    return next(
        isApiRequest && token
            ? request.clone({
                  setHeaders: {
                      Authorization: `Bearer ${token}`,
                  },
              })
            : request
    ).pipe(
        catchError((failure) => {
            if (
                isApiRequest &&
                failure.status === 401 &&
                !request.url.endsWith('/auth/login')
            ) {
                // An invalid or expired token or a disabled account requires a new login; an error in login itself stays on screen.
                authentication.logout();
            }
            // The component receives the original error to present the message returned by Django.
            return throwError(() => failure);
        })
    );
};
