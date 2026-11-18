import {Component, Injectable, inject} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialog, MatDialogModule} from '@angular/material/dialog';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';

@Component({
    imports: [MatDialogModule, MatButtonModule, MatIconModule],
    template: `
        <h2 mat-dialog-title><mat-icon aria-hidden="true">check_circle</mat-icon>{{ data.title }}</h2>
        @if (data.name) { <mat-dialog-content>{{ data.name }}</mat-dialog-content> }
        <mat-dialog-actions align="end">
            <button mat-flat-button mat-dialog-close cdkFocusInitial>{{ data.action }}</button>
        </mat-dialog-actions>
    `,
    styles: [`
        h2 {display: flex; align-items: center; gap: 10px;}
        mat-icon {color: #217549; flex-shrink: 0;}
        mat-dialog-content {overflow-wrap: anywhere;}
    `],
})
class RegistrationSuccessDialog {
    readonly data: {title: string; name: string; action: string} = inject(MAT_DIALOG_DATA);
}

@Injectable({providedIn: 'root'})
export class RegistrationFeedback {
    private readonly dialog = inject(MatDialog);

    created(title: string, name: string) {
        this.show(title, name, 'Voltar à lista');
    }

    show(title: string, name: string, action: string) {
        this.dialog.open(RegistrationSuccessDialog, {
            data: {title, name, action},
            width: '460px',
            maxWidth: 'calc(100vw - 32px)',
        });
    }
}
