/** Componente raiz: router-outlet recebe a tela escolhida pelas rotas; não contém regras de manutenção. */
import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
@Component({
    selector: 'app-root',
    standalone: true,
    imports: [RouterOutlet],
    template: '<router-outlet />',
})
export class App {}
