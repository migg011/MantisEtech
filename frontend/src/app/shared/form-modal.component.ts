/** Modal compartilhado: recebe conteúdo/ações do componente pai e devolve o evento de fechamento. */
import { AfterViewInit, Component, EventEmitter, Input, OnDestroy, Output, TemplateRef, ViewChild, inject } from '@angular/core';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
/** Estrutura compartilhada dos cadastros; mantém foco, rolagem e bloqueio durante o envio. */
@Component({
    selector: 'app-modal-formulario',
    standalone: true,
    imports: [MatDialogModule, MatIconModule],
    template: `
        <ng-template #content>
            <div class="mantis-modal">
                <header class="mantis-modal-header">
                    <div class="mantis-modal-icon"><mat-icon>{{ iconValue }}</mat-icon></div>
                    <div><h2 mat-dialog-title>{{ titleValue }}</h2><p>{{ subtitle }}</p></div>
                    <button type="button" class="mantis-modal-close" aria-label="Fechar modal" [disabled]="busy" (click)="closeValue()"><mat-icon>close</mat-icon></button>
                </header>
                <mat-dialog-content class="mantis-modal-body">
                    <fieldset [disabled]="busy"><ng-content /></fieldset>
                </mat-dialog-content>
                <footer class="mantis-modal-footer"><ng-content select="[modalActions]" /></footer>
            </div>
        </ng-template>
    `
})
export class FormModal implements AfterViewInit, OnDestroy {
    @Input()
    titleValue = '';
    @Input()
    subtitle = '';
    @Input()
    iconValue = 'edit_note';
    @Input()
    busy = false;
    @Input()
    wide = false;
    @Output()
    closedValue = new EventEmitter<void>();
    @ViewChild('content')
    content!: TemplateRef<unknown>;
    private dialog = inject(MatDialog);
    private dialogRefValue?: MatDialogRef<unknown>;
    private destroyedValue = false;
    /** Após o template existir, abre o MatDialog com conteúdo projetado, foco e bloqueio de fechamento durante gravação. */
    ngAfterViewInit() {
        this.dialogRefValue = this.dialog.open(this.content, {
            width: this.wide ? '920px' : '680px',
            maxWidth: 'calc(100vw - 32px)',
            maxHeight: 'calc(100dvh - 32px)',
            panelClass: 'mantis-form-dialog',
            backdropClass: 'sector-dialog-backdrop',
            autoFocus: 'input, textarea, select',
            closePredicate: () => this.destroyedValue || !this.busy
        });
        this.dialogRefValue.afterClosed().subscribe(() => {
            if (!this.destroyedValue)
                this.closedValue.emit();
        });
    }
    /** Fecha a janela quando o salvamento termina. */
    closeValue() {
        if (!this.busy)
            this.dialogRefValue?.close();
    }
    /** Marca a destruição e fecha o diálogo evitando emitir cancelamento para um componente já removido. */
    ngOnDestroy() {
        this.destroyedValue = true;
        this.dialogRefValue?.close();
    }
}
