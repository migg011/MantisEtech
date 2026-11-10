/** Entrada do Angular: bootstrapApplication monta App e registra os providers definidos em appConfig. */
import { bootstrapApplication } from '@angular/platform-browser';
import { App } from './app/app';
import { appConfig } from './app/app.config';
bootstrapApplication(App, appConfig).catch((failure) => console.error(failure));
