/** Modal compartilhado: recebe conteúdo/ações do componente pai e devolve o evento de fechamento. */
import {
    AfterViewInit,
    Component,
    EventEmitter,
    Input,
    OnDestroy,
    Output,
    TemplateRef,
    ViewChild,
    inject,
} from '@angular/core';
import {
    MatDialog,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
/** Estrutura compartilhada dos cadastros; mantém foco, rolagem e bloqueio durante o envio. */
@Component({
    selector: 'app-form-modal',
    standalone: true,
    imports: [MatDialogModule, MatIconModule],
    template: `
        <ng-template #content>
            <div class="mantis-modal">
                <header class="mantis-modal-header">
                    <div class="mantis-modal-icon"
                        ><mat-icon>{{ icon }}</mat-icon></div
                    >
                    <div
                        ><h2 mat-dialog-title>{{ title }}</h2
                        ><p>{{ subtitle }}</p></div
                    >
                    <button
                        type="button"
                        class="mantis-modal-close"
                        aria-label="Fechar modal"
                        [disabled]="busy"
                        (click)="close()"
                        ><mat-icon>close</mat-icon></button
                    >
                </header>
                <mat-dialog-content class="mantis-modal-body">
                    <fieldset [disabled]="busy"><ng-content /></fieldset>
                </mat-dialog-content>
                <footer class="mantis-modal-footer"
                    ><ng-content select="[modalActions]"
                /></footer>
            </div>
        </ng-template>
    `,
})
export class FormModal implements AfterViewInit, OnDestroy {
    @Input()
    title = '';
    @Input()
    subtitle = '';
    @Input()
    icon = 'edit_note';
    @Input()
    busy = false;
    @Input()
    wide = false;
    @Output()
    closed = new EventEmitter<void>();
    @ViewChild('content')
    content!: TemplateRef<unknown>;
    private dialogs = inject(MatDialog);
    private dialogReference?: MatDialogRef<unknown>;
    private destroyed = false;
    /** Após o template existir, abre o MatDialog com conteúdo projetado, foco e bloqueio de fechamento durante gravação. */
    ngAfterViewInit() {
        this.dialogReference = this.dialogs.open(this.content, {
            width: this.wide ? '920px' : '680px',
            maxWidth: 'calc(100vw - 32px)',
            maxHeight: 'calc(100dvh - 32px)',
            panelClass: 'mantis-form-dialog',
            backdropClass: 'sector-dialog-backdrop',
            autoFocus: 'input, textarea, select',
            closePredicate: () => this.destroyed || !this.busy,
        });
        this.dialogReference.afterClosed().subscribe(() => {
            if (!this.destroyed) this.closed.emit();
        });
    }
    /** Fecha o modal apenas quando o componente pai não informou busy. */
    close() {
        if (!this.busy) this.dialogReference?.close();
    }
    /** Marca a destruição e fecha o diálogo evitando emitir cancelamento para um componente já removido. */
    ngOnDestroy() {
        this.destroyed = true;
        this.dialogReference?.close();
    }
}
