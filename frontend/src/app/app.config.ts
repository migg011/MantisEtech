/** Configura injeção de dependências, HttpClient com interceptor de autenticação, rotas e componentes Material. */
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { MAT_FORM_FIELD_DEFAULT_OPTIONS } from '@angular/material/form-field';
import { authenticationInterceptor } from './services';
import { routes } from './app.routes';
export const appConfig: ApplicationConfig = {
    providers: [
        provideHttpClient(withInterceptors([authenticationInterceptor])),
        provideRouter(routes),
        provideAnimationsAsync(),
        {
            provide: MAT_FORM_FIELD_DEFAULT_OPTIONS,
            useValue: {
                appearance: 'outline',
                floatLabel: 'always',
                subscriptSizing: 'dynamic',
            },
        },
    ],
};
