/** Moldura da aplicação: menu, usuário conectado e router-outlet. O modo exposição usa uma rota externa a esta moldura. */
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatDialogModule } from '@angular/material/dialog';
import { MatCardModule } from '@angular/material/card';
import { Authentication } from '../../services';
const UI_MODULES = [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule,
    MatSelectModule,
    MatToolbarModule,
    MatDialogModule,
    MatCardModule,
    RouterLink,
];
@Component({
    standalone: true,
    imports: [...UI_MODULES, RouterOutlet, RouterLinkActive],
    templateUrl: './layout.component.html',
    styleUrl: './layout.component.scss',
})
/** Estrutura compartilhada de navegação; exibe o usuário autenticado e as telas carregadas pelo roteador. */
export class MainLayout {
    authentication = inject(Authentication);
}
