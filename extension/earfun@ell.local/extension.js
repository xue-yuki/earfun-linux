import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {EarFunPopup} from './popup.js';
import {ConnectionGate} from './popup-state.js';

const NAME = 'io.github.ell.EarFun';
const PATH = '/io/github/ell/EarFun';
const MODES = {
    noise: ['Mode suara', [['normal', 'Normal'], ['ambient', 'Ambient'], ['anc', 'ANC']]],
    'anc-level': ['Level ANC', [['strong', 'Strong'], ['balanced', 'Balanced'], ['wind', 'Wind'], ['adaptive', 'Adaptive']]],
};

export default class EarFunExtension extends Extension {
    enable() {
        const generation = this._generation = (this._generation ?? 0) + 1;
        this._alive = true;
        this._busy = false;
        this._state = null;
        this._connectionGate = new ConnectionGate();
        this._welcome = null;
        this._cancellable = new Gio.Cancellable();
        this._button = new PanelMenu.Button(0.0, 'EarFun', false);
        const box = new St.BoxLayout();
        box.add_child(new St.Icon({icon_name: 'audio-headphones-symbolic', style_class: 'system-status-icon'}));
        this._panelLabel = new St.Label({text: '—', y_align: Clutter.ActorAlign.CENTER, style_class: 'earfun-panel-label'});
        box.add_child(this._panelLabel);
        this._button.add_child(box);
        this._buildMenu();
        Main.panel.addToStatusArea(this.uuid, this._button);
        this._button.menu.connect('open-state-changed', (_menu, open) => {
            if (open && this._proxy?.get_name_owner() && !this._busy)
                this._request('status', '');
        });
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            null, NAME, PATH, NAME, this._cancellable, (_source, result) => {
                if (!this._alive || this._generation !== generation)
                    return;
                try {
                    this._proxy = Gio.DBusProxy.new_for_bus_finish(result);
                    this._signalId = this._proxy.connect('g-signal', (_proxy, _sender, name, params) => {
                        if (name === 'StateChanged')
                            this._receive(params.deep_unpack()[0]);
                    });
                    this._ownerId = this._proxy.connect('notify::g-name-owner', () => this._fetchState());
                    this._fetchState();
                } catch (error) {
                    this._message.label.text = `Service tidak tersedia: ${error.message}`;
                }
            });
    }

    _buildMenu() {
        const menu = this._button.menu;
        this._controls = [];
        this._title = new PopupMenu.PopupMenuItem('EarFun Air Pro 4i', {reactive: false});
        this._title.label.add_style_class_name('earfun-title');
        menu.addMenuItem(this._title);
        this._connection = new PopupMenu.PopupMenuItem('Menghubungi service…', {reactive: false});
        this._connection.label.add_style_class_name('earfun-detail');
        menu.addMenuItem(this._connection);
        const batteryRow = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        const batteryBox = new St.BoxLayout({style_class: 'earfun-batteries'});
        this._batteries = {};
        for (const [key, label] of [['left', 'Kiri'], ['right', 'Kanan'], ['case', 'Casing']]) {
            const column = new St.BoxLayout({vertical: true, style_class: 'earfun-battery'});
            column.add_child(new St.Label({text: label, style_class: 'earfun-detail'}));
            const value = new St.Label({text: '—', style_class: 'earfun-battery-value'});
            column.add_child(value);
            this._batteries[key] = value;
            batteryBox.add_child(column);
        }
        batteryRow.add_child(batteryBox);
        menu.addMenuItem(batteryRow);
        menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._choices = {};
        this._submenus = {};
        for (const [command, [title, options]] of Object.entries(MODES)) {
            const sub = new PopupMenu.PopupSubMenuMenuItem(title);
            this._controls.push(sub);
            this._submenus[command] = {item: sub, title};
            this._choices[command] = {};
            for (const [value, label] of options) {
                const item = new PopupMenu.PopupMenuItem(label);
                item.connect('activate', () => this._request(command, value));
                this._choices[command][value] = item;
                sub.menu.addMenuItem(item);
            }
            menu.addMenuItem(sub);
        }
        this._toggles = {};
        this._toggleLabels = {};
        for (const [command, label] of [['game', 'Game mode'], ['spatial', 'Spatial audio'], ['multipoint', 'Multipoint']]) {
            const item = new PopupMenu.PopupSwitchMenuItem(label, false);
            item.connect('toggled', (_item, enabled) => {
                if (!this._rendering)
                    this._request(command, enabled ? 'on' : 'off');
            });
            this._toggles[command] = item;
            this._toggleLabels[command] = label;
            this._controls.push(item);
            menu.addMenuItem(item);
        }
        const eq = new PopupMenu.PopupSubMenuMenuItem('Preset EQ');
        this._controls.push(eq);
        for (const [value, label] of [['flat', 'Flat'], ['bass', 'Bass +3 dB'], ['vocal', 'Vocal']]) {
            const item = new PopupMenu.PopupMenuItem(label);
            item.connect('activate', () => this._request('eq', value));
            eq.menu.addMenuItem(item);
        }
        menu.addMenuItem(eq);
        menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._message = new PopupMenu.PopupMenuItem('Menunggu service lokal', {reactive: false});
        this._message.label.add_style_class_name('earfun-message');
        this._message.label.clutter_text.set_line_wrap(true);
        menu.addMenuItem(this._message);
        this._refresh = new PopupMenu.PopupMenuItem('Refresh status');
        this._refresh.connect('activate', () => this._request('status', ''));
        menu.addMenuItem(this._refresh);
        this._testPopup = new PopupMenu.PopupMenuItem('Tes popup');
        this._testPopup.connect('activate', () => {
            this._button.menu.close();
            this._showPopup();
        });
        menu.addMenuItem(this._testPopup);
        this._setSensitive(false);
    }

    _setSensitive(available) {
        for (const item of this._controls)
            item.setSensitive(available);
        this._refresh.setSensitive(Boolean(this._proxy?.get_name_owner()) && !this._busy);
        this._testPopup.setSensitive(Boolean(this._state?.connected));
    }

    _fetchState() {
        if (!this._proxy?.get_name_owner()) {
            this._welcome?.destroy();
            this._welcome = null;
            this._state = null;
            this._busy = false;
            this._render(null);
            this._message.label.text = 'Service mati. Jalankan: systemctl --user restart earfun.service';
            return;
        }
        this._call('GetState', null, text => this._receive(text));
    }

    _call(method, parameters, callback) {
        const generation = this._generation;
        this._proxy.call(method, parameters, Gio.DBusCallFlags.NONE, 30000,
            this._cancellable, (proxy, result) => {
                if (!this._alive || this._generation !== generation)
                    return;
                try {
                    callback(proxy.call_finish(result).deep_unpack()[0]);
                } catch (error) {
                    this._busy = false;
                    this._message.label.text = error.message;
                    this._setSensitive(false);
                }
            });
    }

    _request(command, value) {
        if (this._busy || !this._proxy?.get_name_owner())
            return;
        this._busy = true;
        this._setSensitive(false);
        this._message.label.text = 'Memproses…';
        this._call('Request', new GLib.Variant('(ss)', [command, value]), text => {
            const result = JSON.parse(text);
            this._busy = false;
            if (!result.ok)
                this._message.label.text = result.error ?? 'Perubahan belum terverifikasi';
            this._fetchState();
        });
    }

    _receive(text) {
        try {
            this._state = JSON.parse(text);
            this._busy = Boolean(this._state.busy);
            this._render(this._state);
            const transition = this._connectionGate.update(this._state);
            if (transition.hide) {
                this._welcome?.destroy();
                this._welcome = null;
            } else if (transition.show) {
                this._showPopup();
            } else {
                this._welcome?.update(this._state);
            }
        } catch (error) {
            console.error(`EarFun: ${error.message}`);
        }
    }

    _showPopup() {
        if (!this._state?.connected || Main.sessionMode.isLocked || Main.sessionMode.currentMode !== 'user')
            return;
        this._welcome?.destroy();
        this._welcome = null;
        try {
            this._welcome = new EarFunPopup(this, this._state, () => {
                if (this._alive)
                    this._button.menu.open();
            });
        } catch (error) {
            console.error(`EarFun popup: ${error.stack ?? error.message}`);
            this._message.label.text = `Popup gagal: ${error.message}`;
        }
    }

    _render(state) {
        const connected = Boolean(state?.connected);
        this._title.label.text = state?.name ?? 'EarFun Air Pro 4i';
        this._connection.label.text = connected ? (state.busy ? 'Tersambung · memproses…' : 'Tersambung') : 'Tidak tersambung';
        const values = connected ? (state.values ?? {}) : {};
        const battery = (key) => key === 'case' ? values.case?.data : values.earbuds?.data?.[key];
        for (const key of ['left', 'right', 'case']) {
            const data = battery(key);
            this._batteries[key].text = data?.known ? `${data.percent}%` : '—';
        }
        const known = ['left', 'right'].map(key => battery(key)).filter(data => data?.known);
        this._panelLabel.text = connected ? (known.length ? `${Math.min(...known.map(data => data.percent))}%` : '…') : '—';
        this._rendering = true;
        try {
            for (const [command, choices] of Object.entries(this._choices)) {
                const data = values[command]?.data;
                for (const [value, item] of Object.entries(choices))
                    item.setOrnament(data?.known && data.value === value ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.NONE);
                const sub = this._submenus[command];
                sub.item.label.text = `${sub.title}: ${data?.known ? data.value : '—'}`;
            }
            for (const [command, item] of Object.entries(this._toggles)) {
                const data = values[command]?.data;
                item.setToggleState(data?.known && data.value === 'on');
                item.label.text = this._toggleLabels[command] + (data?.known ? '' : ': —');
            }
        } finally {
            this._rendering = false;
        }
        const result = state?.last_result;
        if (state?.busy)
            this._message.label.text = 'Memproses…';
        else if (state?.error)
            this._message.label.text = state.error;
        else if (result?.command === 'eq')
            this._message.label.text = 'EQ terkirim · cek perubahan lewat suara';
        else if (result?.verified)
            this._message.label.text = 'Perubahan terverifikasi';
        else
            this._message.label.text = connected ? 'Status diperbarui setiap 30 detik' : 'Sambungkan EarFun lewat Bluetooth';
        this._setSensitive(connected && !this._busy);
    }

    disable() {
        this._generation = (this._generation ?? 0) + 1;
        this._alive = false;
        this._welcome?.destroy();
        this._welcome = null;
        this._connectionGate = null;
        this._cancellable?.cancel();
        if (this._proxy && this._signalId)
            this._proxy.disconnect(this._signalId);
        if (this._proxy && this._ownerId)
            this._proxy.disconnect(this._ownerId);
        this._proxy = null;
        this._signalId = this._ownerId = null;
        this._button?.destroy();
        this._button = null;
        this._state = null;
        this._cancellable = null;
    }
}
