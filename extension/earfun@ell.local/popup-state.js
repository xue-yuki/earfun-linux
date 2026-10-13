// No GNOME imports: connection transitions can be tested without a desktop.
export class ConnectionGate {
    constructor() {
        this.connected = false;
        this.pending = false;
    }

    update(state) {
        if (!state || state.connection_checked === false)
            return {show: false, hide: false};
        const connected = Boolean(state.connected);
        const hide = this.connected && !connected;
        if (connected && !this.connected)
            this.pending = true;
        this.connected = connected;
        if (!connected) {
            this.pending = false;
            return {show: false, hide};
        }
        // Wait for the first completed status instead of displaying cached batteries.
        const ready = !state.busy && state.updated_at !== null && state.updated_at !== undefined;
        const show = this.pending && ready;
        if (show)
            this.pending = false;
        return {show, hide: false};
    }
}

export function popupBattery(state, key) {
    if (!state?.connected)
        return null;
    const data = key === 'case' ? state.values?.case?.data : state.values?.earbuds?.data?.[key];
    const value = data?.percent;
    return data?.known && typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
}
