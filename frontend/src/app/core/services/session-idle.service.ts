import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';
import { Auth } from './auth.service';

const storageKey = 'mantis.idleMinutes';
const validMinutes = (value: number) => Number.isInteger(value) && value >= 0 && value <= 480;

@Injectable({ providedIn: 'root' })
export class SessionIdle {
    private readonly auth = inject(Auth);
    private readonly router = inject(Router);
    private readonly browser = inject(DOCUMENT).defaultView;
    private readonly destroyRef = inject(DestroyRef);
    private readonly configuredMinutes = signal(this.readMinutes());
    readonly minutes = this.configuredMinutes.asReadonly();

    constructor() {
        const browser = this.browser;
        if (!browser) return;
        const route = signal(this.router.url);
        this.router.events.pipe(
            filter(event => event instanceof NavigationEnd),
            takeUntilDestroyed(this.destroyRef),
        ).subscribe(event => route.set(event.urlAfterRedirects));

        const onStorage = (event: StorageEvent) => {
            if (event.key === storageKey || event.key === null) this.configuredMinutes.set(this.readMinutes());
        };
        browser.addEventListener('storage', onStorage);
        this.destroyRef.onDestroy(() => browser.removeEventListener('storage', onStorage));

        effect(onCleanup => {
            const minutes = this.minutes();
            const user = this.auth.userValue();
            const currentRoute = route().split(/[?#;]/, 1)[0];
            if (!minutes || !user || currentRoute === '/totem' || currentRoute === '/login') return;

            const timeout = minutes * 60_000;
            let lastActivity = Date.now();
            let timer: number;
            const check = () => {
                const remaining = timeout - (Date.now() - lastActivity);
                if (remaining <= 0) {
                    this.auth.signOut();
                    return;
                }
                browser.clearTimeout(timer);
                timer = browser.setTimeout(check, remaining);
            };
            const activity = (event: Event) => {
                if (!event.isTrusted) return;
                if (Date.now() - lastActivity >= timeout) check();
                else lastActivity = Date.now();
            };
            const events = ['pointerdown', 'pointermove', 'keydown', 'wheel'];
            for (const name of events) browser.addEventListener(name, activity, { passive: true });
            browser.addEventListener('focus', check);
            timer = browser.setTimeout(check, timeout);
            onCleanup(() => {
                browser.clearTimeout(timer);
                for (const name of events) browser.removeEventListener(name, activity);
                browser.removeEventListener('focus', check);
            });
        });
    }

    save(minutes: number): boolean {
        if (!validMinutes(minutes) || this.auth.userValue()?.role !== 'ADMINISTRADOR') return false;
        try {
            this.browser?.localStorage.setItem(storageKey, String(minutes));
            this.configuredMinutes.set(minutes);
            return true;
        } catch {
            return false;
        }
    }

    private readMinutes(): number {
        try {
            const minutes = Number(this.browser?.localStorage.getItem(storageKey) ?? 0);
            return validMinutes(minutes) ? minutes : 0;
        } catch {
            return 0;
        }
    }
}
