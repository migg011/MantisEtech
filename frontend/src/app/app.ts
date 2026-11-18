/** Mostra a tela escolhida pela rota atual. */
import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SessionIdle } from './core/services/session-idle.service';
@Component({
    selector: 'app-root', standalone: true, imports: [RouterOutlet], template: '<router-outlet />'
})
export class App {
    private readonly sessionIdle = inject(SessionIdle);
}
