/** Integração transversal: adiciona Authorization Bearer às URLs /api/ e encaminha erros de sessão ao login. */
import { HttpContextToken, HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, tap, throwError } from 'rxjs';
import { Auth } from '../services/auth.service';
import { RegistrationFeedback } from '../../shared/registration-feedback';

export const SUPPRESS_EDIT_DIALOG = new HttpContextToken(() => false);

/** Intercepta a chamada antes do envio, acrescenta Bearer somente à API local e trata 401 como fim da sessão. */
export const authInterceptor: HttpInterceptorFn = (req, nextValue) => {
    const authValue = inject(Auth);
    const token = sessionStorage.getItem('mantisToken');
    const apiRequest = req.url.startsWith('/api/');
    const showEdit = apiRequest && ['PATCH', 'PUT'].includes(req.method) && !req.context.get(SUPPRESS_EDIT_DIALOG);
    const feedback = showEdit ? inject(RegistrationFeedback) : null;
    // Anexa a credencial somente às chamadas locais da API, preservando requisições a outros endereços.
    return nextValue(apiRequest && token ? req.clone({
        setHeaders: {
            Authorization: `Bearer ${token}`
        }
    }) : req).pipe(tap(event => {
        if (feedback && event instanceof HttpResponse && event.ok) {
            // Deixa o formulário concluir seu retorno de sucesso antes de abrir o diálogo.
            queueMicrotask(() => feedback.show('Alterações salvas com sucesso', '', 'OK'));
        }
    }), catchError(failure => {
        if (apiRequest && failure.status === 401 && !req.url.endsWith('/auth/login')) {
            // Token inválido, expirado ou conta desativada exigem novo login; erro no próprio login fica na tela.
            authValue.signOut();
        }
        // O componente recebe o erro original para apresentar a mensagem devolvida pelo Django.
        return throwError(() => failure);
    }));
};
